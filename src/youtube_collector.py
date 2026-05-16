from __future__ import annotations

from datetime import datetime, timedelta, timezone
import time
from typing import Iterable

from src.models import Opportunity
from src.scorer import _extract_knowledge_terms, score_post
from src.store import Store
from src.twitter_relevance import TwitterRelevanceDecision, TwitterRelevanceJudge
from src.youtube_client import YouTubeClient, YouTubeComment, YouTubeVideo


def _published_after(days: int) -> str:
    since = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    return since.isoformat(timespec="seconds").replace("+00:00", "Z")


def _derive_youtube_queries(knowledge_block: str, pain_keywords: list[str]) -> list[str]:
    terms = _extract_knowledge_terms(knowledge_block)
    queries: list[str] = []
    for keyword in pain_keywords:
        cleaned = keyword.strip().lower()
        if cleaned and len(cleaned) >= 4:
            queries.append(cleaned)
    for term in terms:
        cleaned = term.strip().lower()
        if not cleaned or len(cleaned) < 4:
            continue
        queries.extend([
            cleaned,
            f"how to {cleaned}",
            f"{cleaned} tips",
        ])
    return queries


def _unique_queries(configured_queries: list[str], knowledge_block: str, pain_keywords: list[str], max_queries: int) -> list[str]:
    queries = list(configured_queries or []) + _derive_youtube_queries(knowledge_block, pain_keywords)
    unique: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = query.strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
        if len(unique) >= max(1, max_queries):
            break
    return unique


def _fallback_decision(
    comment: YouTubeComment,
    knowledge_block: str,
    pain_keywords: list[str],
    min_score: int,
) -> TwitterRelevanceDecision:
    score, reasons = score_post(
        title=comment.video_title,
        body=comment.text,
        subreddit_rules_text="",
        keywords=[],
        pain_keywords=pain_keywords,
        knowledge_block=knowledge_block,
        created_utc=comment.created_at_ts,
        early_reply_window_minutes=0,
        platform="youtube",
    )
    return TwitterRelevanceDecision(
        relevant=score >= min_score,
        score=score,
        reason="; ".join(reasons[:3]) or "Fallback scorer decision",
        matched_product_area="lexical knowledge match",
    )


def _comment_to_opportunity(
    comment: YouTubeComment,
    knowledge_block: str,
    pain_keywords: list[str],
    early_reply_window_minutes: int,
    relevance: TwitterRelevanceDecision | None = None,
) -> Opportunity:
    score, reasons = score_post(
        title=comment.video_title,
        body=comment.text,
        subreddit_rules_text="",
        keywords=[],
        pain_keywords=pain_keywords,
        knowledge_block=knowledge_block,
        created_utc=comment.created_at_ts,
        early_reply_window_minutes=early_reply_window_minutes,
        platform="youtube",
    )
    if relevance:
        score = max(score, relevance.score)
        reasons.insert(
            0,
            f"YouTube relevance {relevance.score}/100: {relevance.reason} ({relevance.matched_product_area})",
        )
    age_minutes = max(0, int((time.time() - comment.created_at_ts) / 60)) if comment.created_at_ts > 0 else 0
    return Opportunity(
        thing_id=f"yt_{comment.comment_id}",
        subreddit=comment.channel_title or "youtube",
        title=comment.video_title,
        body=comment.text,
        author=comment.author_display_name or "YouTube commenter",
        permalink=comment.permalink,
        score=score,
        created_utc=comment.created_at_ts,
        age_minutes=age_minutes,
        reasons=reasons,
    )


def collect_youtube_opportunities(
    youtube: YouTubeClient,
    store: Store,
    query_terms: list[str],
    target_channels: list[str],
    prompt_template: str,
    knowledge_block: str,
    pain_keywords: list[str],
    early_reply_window_minutes: int,
    max_videos: int,
    max_comments_per_video: int,
    min_score: int,
    relevance_min_score: int,
    local_fallback_min_score: int,
    published_after_days: int,
    max_search_queries: int,
    ai_candidates_per_video: int,
    google_api_key: str | None = None,
    google_model: str = "gemma-3-27b-it",
) -> Iterable[Opportunity]:
    del prompt_template
    judge = (
        TwitterRelevanceJudge(
            api_key=google_api_key,
            model=google_model,
            min_score=relevance_min_score,
        )
        if google_api_key
        else None
    )
    seen_video_ids: set[str] = set()
    videos: list[YouTubeVideo] = []
    published_after = _published_after(published_after_days)

    search_queries = _unique_queries(query_terms, knowledge_block, pain_keywords, max_search_queries)
    if not search_queries:
        print("  [YouTube] No search queries configured or derivable from account knowledge; skipping search")
        return

    for query in search_queries:
        if len(videos) >= max_videos:
            break
        try:
            print(f"  [YouTube] Search query: {query}")
            per_query = max(1, min(10, max_videos - len(videos)))
            for video in youtube.search_videos(query=query, max_results=per_query, published_after=published_after):
                if video.video_id in seen_video_ids:
                    continue
                seen_video_ids.add(video.video_id)
                videos.append(video)
                if len(videos) >= max_videos:
                    break
        except Exception as exc:
            print(f"  [YouTube] Search failed for {query}: {exc}")

    # Target channels are currently used as exact channel-title filters on search results.
    # This keeps the first release API-key only; channel-ID resolution can be added later.
    normalized_channels = {channel.strip().lower().lstrip("@") for channel in target_channels if channel.strip()}
    if normalized_channels:
        videos = [
            video for video in videos
            if video.channel_title.lower().lstrip("@") in normalized_channels
            or video.channel_id.lower() in normalized_channels
        ]

    collected = 0
    rejected = 0
    for video in videos[:max_videos]:
        try:
            comments = youtube.list_video_comments(video=video, max_results=max_comments_per_video)
        except Exception as exc:
            print(f"  [YouTube] Comments failed for {video.video_id}: {exc}")
            continue

        ranked_comments: list[tuple[int, YouTubeComment, TwitterRelevanceDecision]] = []
        for comment in comments:
            if store.is_seen(f"yt_comment_{comment.comment_id}") or store.is_seen(f"yt_{comment.comment_id}"):
                continue
            fallback = _fallback_decision(
                comment=comment,
                knowledge_block=knowledge_block,
                pain_keywords=pain_keywords,
                min_score=local_fallback_min_score,
            )
            ranked_comments.append((fallback.score, comment, fallback))

        ranked_comments.sort(key=lambda item: item[0], reverse=True)
        candidate_rows = ranked_comments[:max(1, ai_candidates_per_video)]
        print(f"  [YouTube] Prefilter kept {len(candidate_rows)}/{len(ranked_comments)} comments for {video.video_id}")

        candidate_ids = {comment.comment_id for _, comment, _ in candidate_rows}
        for _, comment, fallback in candidate_rows:
            if judge:
                try:
                    decision = judge.judge(
                        tweet_text=f"Video: {comment.video_title}\nComment: {comment.text}",
                        knowledge_block=knowledge_block,
                        platform="youtube",
                    )
                except Exception as exc:
                    print(f"  [YouTube] AI relevance failed for {comment.comment_id}: {exc}. Using local fallback.")
                    decision = fallback
            else:
                decision = fallback

            if not decision.relevant:
                rejected += 1
                store.mark_seen(f"yt_comment_{comment.comment_id}")
                continue

            opp = _comment_to_opportunity(
                comment=comment,
                knowledge_block=knowledge_block,
                pain_keywords=pain_keywords,
                early_reply_window_minutes=early_reply_window_minutes,
                relevance=decision,
            )
            if opp.score >= min_score:
                collected += 1
                yield opp
            else:
                rejected += 1
            store.mark_seen(f"yt_comment_{comment.comment_id}")

        for _, comment, _ in ranked_comments:
            if comment.comment_id not in candidate_ids:
                rejected += 1
                store.mark_seen(f"yt_comment_{comment.comment_id}")

    print(f"  [YouTube] Collected {collected} opportunities this cycle; rejected {rejected}")
