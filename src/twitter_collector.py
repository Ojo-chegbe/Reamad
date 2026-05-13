from __future__ import annotations

import re
import time
from typing import Iterable
from urllib.parse import urlparse

import feedparser

from src.models import Opportunity
from src.scorer import score_post
from src.store import Store
from src.twitter_client import TweetPost, TwitterClient
from src.twitter_relevance import TwitterRelevanceDecision, TwitterRelevanceJudge


def _derive_search_queries(prompt_template: str, knowledge_block: str) -> list[str]:
    del prompt_template
    source = knowledge_block or ""

    # These are buyer-problem searches derived from the knowledge-box capabilities,
    # not generic keywords like "AI" or "content".
    query_groups = [
        ["need product photos", "amazon listing photos", "shopify product photos", "product photo background"],
        ["repurpose long video into shorts", "youtube shorts from long video", "turn podcast into clips", "make reels from long video"],
        ["ugc ads for product", "make ugc ads", "need video ads for product", "product demo video"],
        ["youtube thumbnail tool", "youtube seo tool", "video ideas for youtube", "validate video ideas"],
        ["voice clone for videos", "ai narration tool", "remove background noise audio", "clean up audio recording"],
        ["write amazon listing copy", "seo product descriptions", "amazon bullet points", "shopify product descriptions"],
        ["schedule tiktok instagram posts", "social media scheduler", "post to tiktok and instagram", "content distribution workflow"],
        ["ai music generator", "generate original music", "make music without instruments", "song ideas generator"],
        ["standardize product photos", "batch edit product photos", "bulk product editing", "multi product editor"],
        ["humanize ai text", "make ai text sound natural", "ai text too robotic", "rewrite ai generated text"],
    ]
    lower_source = source.lower()

    queries: list[str] = []
    for group in query_groups:
        for query in group:
            words = [w for w in query.split() if len(w) > 3]
            if any(word in lower_source for word in words):
                queries.append(query)

    unique: list[str] = []
    seen = set()
    for query in queries:
        key = query.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(query.strip())
    return unique[:30]


def _chunked_queries(queries: list[str], chunk_size: int = 4) -> list[str]:
    chunks: list[str] = []
    for idx in range(0, len(queries), chunk_size):
        chunk = queries[idx:idx + chunk_size]
        if not chunk:
            continue
        chunks.append(" OR ".join(f'"{term}"' for term in chunk))
    return chunks


def _fallback_decision(tweet: TweetPost, knowledge_block: str, min_score: int) -> TwitterRelevanceDecision:
    score, reasons = score_post(
        title=tweet.body[:120],
        body=tweet.body,
        subreddit_rules_text="",
        keywords=[],
        pain_keywords=[],
        knowledge_block=knowledge_block,
        created_utc=tweet.created_at_ts,
        early_reply_window_minutes=0,
        platform="twitter",
    )
    return TwitterRelevanceDecision(
        relevant=score >= min_score,
        score=score,
        reason="; ".join(reasons[:3]) or "Fallback scorer decision",
        matched_product_area="lexical knowledge match",
    )


def _tweet_to_opportunity(
    tweet: TweetPost,
    knowledge_block: str,
    early_reply_window_minutes: int,
    relevance: TwitterRelevanceDecision | None = None,
) -> Opportunity:
    title = tweet.body[:120]
    score, reasons = score_post(
        title=title,
        body=tweet.body,
        subreddit_rules_text="",
        keywords=[],
        pain_keywords=[],
        knowledge_block=knowledge_block,
        created_utc=tweet.created_at_ts,
        early_reply_window_minutes=early_reply_window_minutes,
        platform="twitter",
    )
    if relevance:
        score = max(score, relevance.score)
        reasons.insert(
            0,
            f"Twitter relevance {relevance.score}/100: {relevance.reason} ({relevance.matched_product_area})",
        )
    age_minutes = max(0, int((time.time() - tweet.created_at_ts) / 60)) if tweet.created_at_ts > 0 else 0
    return Opportunity(
        thing_id=tweet.thing_id,
        subreddit=tweet.author,
        title=title,
        body=tweet.body,
        author=tweet.author,
        permalink=tweet.permalink,
        score=score,
        created_utc=tweet.created_at_ts,
        age_minutes=age_minutes,
        reasons=reasons,
    )


# ============================================================================
# ACTIVE: FxTwitter API collection (free, no auth, real x.com links)
# Uses https://api.fxtwitter.com — see src/fxtwitter_client.py
# ============================================================================

def collect_fxtwitter_opportunities(
    fxtwitter,  # FxTwitterClient instance
    store: Store,
    target_handles: list[str],
    query_terms: list[str],
    prompt_template: str,
    knowledge_block: str,
    early_reply_window_minutes: int,
    max_items: int,
    min_score: int,
    google_api_key: str | None = None,
    google_model: str = "gemma-3-27b-it",
    relevance_min_score: int = 75,
) -> Iterable[Opportunity]:
    """Collect Twitter opportunities via the free FxTwitter JSON API.

    Two-pronged approach (mirrors Reddit's subreddit polling):
      1. Search by terms derived from prompt template + knowledge block
      2. Poll each target handle's timeline (like Reddit /r/sub/new.json)
    """
    collected = 0
    rejected = 0
    judge = (
        TwitterRelevanceJudge(
            api_key=google_api_key,
            model=google_model,
            min_score=relevance_min_score,
        )
        if google_api_key
        else None
    )

    def qualify(tweet: TweetPost, source: str) -> Opportunity | None:
        nonlocal rejected
        if judge:
            decision = judge.judge(tweet_text=tweet.body, knowledge_block=knowledge_block)
        else:
            decision = _fallback_decision(tweet, knowledge_block, relevance_min_score)

        if not decision.relevant:
            rejected += 1
            print(
                f"  [FxTwitter] REJECTED {source} @{tweet.author} "
                f"score={decision.score} reason={decision.reason}"
            )
            return None

        print(
            f"  [FxTwitter] PASSED {source} @{tweet.author} "
            f"score={decision.score} area={decision.matched_product_area}"
        )
        return _tweet_to_opportunity(
            tweet=tweet,
            knowledge_block=knowledge_block,
            early_reply_window_minutes=early_reply_window_minutes,
            relevance=decision,
        )

    # --- Prong 1: profile-driven search ---
    profile_queries = [q.strip() for q in query_terms if q.strip()]
    derived_queries = _derive_search_queries(prompt_template, knowledge_block)
    search_queries = _chunked_queries(list(dict.fromkeys(profile_queries + derived_queries)))
    if search_queries:
        try:
            per_query_limit = max(3, min(10, max_items // max(1, len(search_queries))))
            for query in search_queries:
                print(f"  [FxTwitter] Search query: {query}")
                tweets = fxtwitter.search(query=query, max_results=per_query_limit)
                for tweet in tweets:
                    if store.is_seen(tweet.thing_id):
                        continue
                    opp = qualify(tweet, "search")
                    if not opp:
                        continue
                    if opp.score >= min_score:
                        collected += 1
                        yield opp
        except Exception as exc:
            print(f"  [FxTwitter] Search failed: {exc}")

    # --- Prong 2: per-handle timeline polling ---
    for handle in (target_handles or []):
        try:
            tweets = fxtwitter.user_timeline(handle=handle, count=min(max_items, 20))
            for tweet in tweets:
                if store.is_seen(tweet.thing_id):
                    continue
                opp = qualify(tweet, f"timeline:{handle}")
                if not opp:
                    continue
                if opp.score >= min_score:
                    collected += 1
                    yield opp
        except Exception as exc:
            print(f"  [FxTwitter] Timeline @{handle} failed: {exc}")

    print(f"  [FxTwitter] Collected {collected} opportunities this cycle; rejected {rejected}")


# ============================================================================
# DORMANT: Official Twitter API v2 collection (requires paid Bearer Token)
# Kept for future use if you subscribe to the paid Twitter API.
# To re-enable: call collect_twitter_opportunities() from main.py
# ============================================================================

def _build_query(handles: list[str], query_terms: list[str], pain_keywords: list[str]) -> str:
    parts: list[str] = []
    if handles:
        handle_query = " OR ".join([f"@{h}" for h in handles if h])
        if handle_query:
            parts.append(f"({handle_query})")

    terms = [t for t in (query_terms + pain_keywords) if t]
    if terms:
        term_query = " OR ".join([f"\"{t}\"" if " " in t else t for t in terms[:20]])
        parts.append(f"({term_query})")

    if not parts:
        parts.append("lang:en")
    parts.append("-is:retweet")
    return " ".join(parts)


def collect_twitter_opportunities(
    twitter: TwitterClient,
    store: Store,
    target_handles: list[str],
    query_terms: list[str],
    keywords: list[str],
    pain_keywords: list[str],
    knowledge_block: str,
    early_reply_window_minutes: int,
    max_items: int,
    min_score: int,
) -> Iterable[Opportunity]:
    """DORMANT — Official Twitter API v2 (paid). Not called from main.py."""
    query = _build_query(target_handles, query_terms, pain_keywords)
    try:
        tweets = twitter.search_recent(query=query, max_results=max_items)
    except Exception as exc:
        print(f"Collect failed for twitter query: {exc}")
        return

    for tweet in tweets:
        if store.is_seen(tweet.thing_id):
            continue
        opp = _tweet_to_opportunity(
            tweet=tweet,
            knowledge_block=knowledge_block,
            early_reply_window_minutes=early_reply_window_minutes,
        )
        if opp.score >= min_score:
            store.mark_seen(tweet.thing_id)
            yield opp


# ============================================================================
# DORMANT: Nitter RSS collection (fragile, Nitter is dying)
# Kept for reference. Not called from main.py.
# ============================================================================

def _strip_html(raw: str) -> str:
    return re.sub(r"<[^>]+>", " ", raw or "").replace("\n", " ").strip()


def _status_id_from_link(link: str) -> str:
    m = re.search(r"/status/(\d+)", link)
    if m:
        return m.group(1)
    return str(abs(hash(link)))


def collect_twitter_rss_opportunities(
    rss_base_url: str,
    store: Store,
    target_handles: list[str],
    keywords: list[str],
    pain_keywords: list[str],
    knowledge_block: str,
    early_reply_window_minutes: int,
    max_items: int,
    min_score: int,
) -> Iterable[Opportunity]:
    """DORMANT — Nitter RSS scraping. Not called from main.py."""
    if not target_handles:
        return

    for handle in target_handles:
        feed_url = f"{rss_base_url}/{handle}/rss"
        try:
            feed = feedparser.parse(feed_url)
        except Exception as exc:
            print(f"Collect failed for twitter rss @{handle}: {exc}")
            continue

        entries = getattr(feed, "entries", [])[:max_items]
        for entry in entries:
            link = str(getattr(entry, "link", "") or "").strip()
            if not link:
                continue
            status_id = _status_id_from_link(link)
            thing_id = f"tw_{status_id}"
            if store.is_seen(thing_id):
                continue

            published_struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
            created_ts = float(time.mktime(published_struct)) if published_struct else 0.0
            title = str(getattr(entry, "title", "") or "").strip()
            summary = _strip_html(str(getattr(entry, "summary", "") or ""))
            body = summary or title

            author_raw = str(getattr(entry, "author", "") or "").strip()
            if not author_raw:
                parsed = urlparse(link)
                path_parts = [p for p in parsed.path.split("/") if p]
                author_raw = path_parts[0] if path_parts else handle
            author = author_raw.lstrip("@").strip().lower()

            tweet = TweetPost(
                thing_id=thing_id,
                author=author,
                body=body,
                permalink=link,
                created_at_ts=created_ts,
            )
            opp = _tweet_to_opportunity(
                tweet=tweet,
                knowledge_block=knowledge_block,
                early_reply_window_minutes=early_reply_window_minutes,
            )
            if opp.score >= min_score:
                store.mark_seen(thing_id)
                yield opp
