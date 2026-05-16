from __future__ import annotations

import time
from typing import Iterable

from src.models import Opportunity
from src.reddit_client import RedditClient, RedditPost
from src.reddit_relevance import RedditRelevanceDecision, RedditRelevanceJudge
from src.scorer import score_post
from src.store import Store


_REDDIT_AI_DISABLED_UNTIL = 0.0


def _build_opportunity(
    submission: RedditPost,
    rules_text: str,
    keywords: list[str],
    pain_keywords: list[str],
    knowledge_block: str,
    early_reply_window_minutes: int,
    relevance: RedditRelevanceDecision | None = None,
) -> Opportunity:
    body = submission.body or ""
    score, reasons = score_post(
        title=submission.title,
        body=body,
        subreddit_rules_text=rules_text,
        keywords=keywords,
        pain_keywords=pain_keywords,
        knowledge_block=knowledge_block,
        created_utc=submission.created_utc,
        early_reply_window_minutes=early_reply_window_minutes,
        platform="reddit",
    )
    if relevance:
        score = max(score, relevance.score)
        reasons.insert(
            0,
            f"Reddit relevance {relevance.score}/100: {relevance.reason} ({relevance.matched_product_area})",
        )
    age_minutes = max(0, int((time.time() - submission.created_utc) / 60)) if submission.created_utc > 0 else 0
    return Opportunity(
        thing_id=submission.thing_id,
        subreddit=submission.subreddit,
        title=submission.title,
        body=body,
        author=submission.author or "[deleted]",
        permalink=submission.permalink,
        score=score,
        created_utc=submission.created_utc,
        age_minutes=age_minutes,
        reasons=reasons,
    )


def collect_opportunities(
    reddit: RedditClient,
    store: Store,
    subreddits: list[str],
    prompt_template: str,
    keywords: list[str],
    pain_keywords: list[str],
    knowledge_block: str,
    early_reply_window_minutes: int,
    max_items_per_subreddit: int,
    min_score: int,
    google_api_key: str | None = None,
    google_model: str = "gemma-3-27b-it",
    relevance_min_score: int = 70,
    local_fallback_min_score: int = 85,
    use_llm_relevance: bool = False,
    ai_batch_size: int = 5,
) -> Iterable[Opportunity]:
    global _REDDIT_AI_DISABLED_UNTIL

    reddit_blocked = False
    now = time.time()
    judge = (
        RedditRelevanceJudge(
            api_key=google_api_key,
            model=google_model,
            min_score=relevance_min_score,
            timeout_seconds=25,
        )
        if use_llm_relevance and google_api_key and now >= _REDDIT_AI_DISABLED_UNTIL
        else None
    )
    if use_llm_relevance and google_api_key and now < _REDDIT_AI_DISABLED_UNTIL:
        remaining = int((_REDDIT_AI_DISABLED_UNTIL - now) / 60) + 1
        print(f"  [Reddit] AI relevance cooldown active for about {remaining}m; skipping AI qualification until ready.")
    del local_fallback_min_score

    collected = 0
    rejected = 0
    for sub_name in subreddits:
        if reddit_blocked:
            break
        print(f"  [Reddit] Checking r/{sub_name}...")
        rules_text = store.get_rules(sub_name)
        try:
            submissions = reddit.get_new_posts(sub_name, limit=max_items_per_subreddit)
        except Exception as exc:
            error_text = str(exc)
            if "403" in error_text and "Blocked" in error_text:
                print("Collect blocked by Reddit (HTTP 403). Pausing subreddit checks for this cycle.")
                reddit_blocked = True
                continue
            print(f"Collect failed for r/{sub_name}: {exc}")
            continue

        print(f"  [Reddit] Pulled {len(submissions)} posts from r/{sub_name}")
        unseen_posts = [submission for submission in submissions if not store.is_seen(submission.thing_id)]
        ranked_posts: list[tuple[int, RedditPost]] = []
        for submission in unseen_posts:
            fallback_score, fallback_reasons = score_post(
                title=submission.title,
                body=submission.body or "",
                subreddit_rules_text=rules_text,
                keywords=keywords,
                pain_keywords=pain_keywords,
                knowledge_block=knowledge_block,
                created_utc=submission.created_utc,
                early_reply_window_minutes=early_reply_window_minutes,
                platform="reddit",
            )
            ranked_posts.append((fallback_score, submission))

        ranked_posts.sort(key=lambda item: item[0], reverse=True)
        candidate_posts = [post for _, post in ranked_posts[:max(1, ai_batch_size)]]
        ai_paused = False
        judged_count = 0
        if judge and candidate_posts:
            print(f"  [Reddit] Prefilter kept {len(candidate_posts)}/{len(unseen_posts)} candidates for r/{sub_name}")
            for candidate in candidate_posts:
                try:
                    local_score = next((score for score, post in ranked_posts if post.thing_id == candidate.thing_id), 0)
                    print(f"  [Reddit] AI judging {candidate.thing_id} local_score={local_score} r/{sub_name}")
                    decision = judge.judge_one(
                        post=candidate,
                        knowledge_block=knowledge_block,
                        prompt_template=prompt_template,
                    )
                    judged_count += 1
                    verdict = "accepted" if decision.relevant else "rejected"
                    print(
                        f"  [Reddit] AI {verdict} {candidate.thing_id} "
                        f"score={decision.score} reason={decision.reason}"
                    )
                    if decision.relevant:
                        opp = _build_opportunity(
                            submission=candidate,
                            rules_text=rules_text,
                            keywords=keywords,
                            pain_keywords=pain_keywords,
                            knowledge_block=knowledge_block,
                            early_reply_window_minutes=early_reply_window_minutes,
                            relevance=decision,
                        )
                        if opp.score >= min_score:
                            collected += 1
                            yield opp
                except Exception as exc:
                    error_str = str(exc)
                    if "HTTP 429" in error_str:
                        _REDDIT_AI_DISABLED_UNTIL = time.time() + (15 * 60)
                        judge = None
                        ai_paused = True
                        print(f"  [Reddit] AI relevance hit rate limit: {exc}. Cooling down 15m and skipping fallback.")
                        break
                    if "HTTP 500" in error_str or "INTERNAL" in error_str:
                        _REDDIT_AI_DISABLED_UNTIL = time.time() + (5 * 60)
                        judge = None
                        ai_paused = True
                        print(f"  [Reddit] AI relevance transient failure: {exc}. Cooling down 5m and skipping fallback.")
                        break
                    print(f"  [Reddit] AI relevance failed for {candidate.thing_id}: {exc}. Skipping this candidate.")
        rejected += max(0, len(unseen_posts) - collected)
        if ai_paused:
            print("  [Reddit] Stopping collection until AI relevance cooldown expires.")
            break
    print(f"Reddit collected {collected} opportunities this cycle; rejected {rejected} as irrelevant")
