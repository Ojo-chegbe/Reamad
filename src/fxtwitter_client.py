"""FxTwitter API client — free, no auth, returns real x.com links.

Uses https://api.fxtwitter.com (FxEmbed project, MIT licensed, 4.5k stars).
Rate limit: 1000 req/min per IP. Docs: https://docs.fxembed.com/api/introduction

This replaces the old Nitter RSS and paid Twitter API v2 approaches.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from src.twitter_client import TweetPost


FXTWITTER_API_BASE = "https://api.fxtwitter.com"


class FxTwitterClient:
    """Lightweight client for the FxTwitter public JSON API."""

    def __init__(self, timeout_seconds: int = 15) -> None:
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})
        self._timeout = timeout_seconds

    # ---- internal ----

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        url = f"{FXTWITTER_API_BASE}{path}"
        resp = self._session.get(url, params=params or {}, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code", 200) not in (200, 204):
            raise RuntimeError(f"FxTwitter API error {data.get('code')}: {url}")
        return data

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Ensure all links point to x.com (some may say twitter.com)."""
        return url.replace("https://twitter.com/", "https://x.com/")

    @staticmethod
    def _parse_status(item: dict) -> TweetPost | None:
        """Convert a single FxTwitter status object into our TweetPost."""
        if not isinstance(item, dict) or item.get("type") != "status":
            return None

        tweet_id = str(item.get("id", "")).strip()
        text = str(item.get("text", "") or "").strip()
        if not tweet_id or not text:
            return None

        # Author info
        author_data = item.get("author") or {}
        screen_name = str(author_data.get("screen_name", "") or "").strip()

        # Permalink — FxTwitter already gives real x.com/twitter.com URLs
        raw_url = str(item.get("url", "")).strip()
        permalink = FxTwitterClient._normalize_url(raw_url) if raw_url else f"https://x.com/{screen_name or 'i'}/status/{tweet_id}"

        # Timestamp
        created_ts = float(item.get("created_timestamp", 0) or 0)

        return TweetPost(
            thing_id=f"tw_{tweet_id}",
            author=screen_name or "unknown",
            body=text,
            permalink=permalink,
            created_at_ts=created_ts,
        )

    # ---- public API ----

    def search(self, query: str, max_results: int = 30) -> list[TweetPost]:
        """Search recent tweets by keyword.

        Endpoint: GET /2/search?q=...&feed=latest&count=N
        """
        data = self._get("/2/search", {
            "q": query,
            "feed": "latest",
            "count": min(max_results, 30),  # API max per page
        })
        posts: list[TweetPost] = []
        for item in data.get("results", []):
            tp = self._parse_status(item)
            if tp:
                posts.append(tp)
        return posts

    def user_timeline(self, handle: str, count: int = 20) -> list[TweetPost]:
        """Get recent tweets from a specific user.

        Endpoint: GET /2/profile/{handle}/statuses?count=N
        """
        data = self._get(f"/2/profile/{handle}/statuses", {"count": min(count, 20)})
        posts: list[TweetPost] = []
        for item in data.get("results", []):
            tp = self._parse_status(item)
            if tp:
                posts.append(tp)
        return posts
