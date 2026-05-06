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


def _tweet_to_opportunity(
    tweet: TweetPost,
    keywords: list[str],
    pain_keywords: list[str],
    early_reply_window_minutes: int,
) -> Opportunity:
    title = tweet.body[:120]
    score, reasons = score_post(
        title=title,
        body=tweet.body,
        subreddit_rules_text="",
        keywords=keywords,
        pain_keywords=pain_keywords,
        created_utc=tweet.created_at_ts,
        early_reply_window_minutes=early_reply_window_minutes,
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
    keywords: list[str],
    pain_keywords: list[str],
    early_reply_window_minutes: int,
    max_items: int,
    min_score: int,
) -> Iterable[Opportunity]:
    """Collect Twitter opportunities via the free FxTwitter JSON API.

    Two-pronged approach (mirrors Reddit's subreddit polling):
      1. Search by keyword queries (like Reddit keyword matching)
      2. Poll each target handle's timeline (like Reddit /r/sub/new.json)
    """
    collected = 0

    # --- Prong 1: keyword search ---
    if query_terms or pain_keywords:
        search_terms = list(dict.fromkeys(query_terms + pain_keywords))[:10]
        # Combine into a single query string (FxTwitter uses Twitter search syntax)
        query = " OR ".join(
            f'"{t}"' if " " in t else t for t in search_terms
        )
        try:
            tweets = fxtwitter.search(query=query, max_results=min(max_items, 30))
            for tweet in tweets:
                if store.is_seen(tweet.thing_id):
                    continue
                opp = _tweet_to_opportunity(
                    tweet=tweet,
                    keywords=keywords,
                    pain_keywords=pain_keywords,
                    early_reply_window_minutes=early_reply_window_minutes,
                )
                if opp.score >= min_score:
                    store.mark_seen(tweet.thing_id)
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
                opp = _tweet_to_opportunity(
                    tweet=tweet,
                    keywords=keywords,
                    pain_keywords=pain_keywords,
                    early_reply_window_minutes=early_reply_window_minutes,
                )
                if opp.score >= min_score:
                    store.mark_seen(tweet.thing_id)
                    collected += 1
                    yield opp
        except Exception as exc:
            print(f"  [FxTwitter] Timeline @{handle} failed: {exc}")

    print(f"  [FxTwitter] Collected {collected} opportunities this cycle")


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
            keywords=keywords,
            pain_keywords=pain_keywords,
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
                keywords=keywords,
                pain_keywords=pain_keywords,
                early_reply_window_minutes=early_reply_window_minutes,
            )
            if opp.score >= min_score:
                store.mark_seen(thing_id)
                yield opp
