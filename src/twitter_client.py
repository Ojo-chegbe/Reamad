from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class TweetPost:
    thing_id: str
    author: str
    body: str
    permalink: str
    created_at_ts: float


class TwitterClient:
    def __init__(self, bearer_token: str, timeout_seconds: int = 15) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {bearer_token}",
                "Accept": "application/json",
            }
        )
        self._timeout_seconds = timeout_seconds

    def _get_json(self, url: str, params: dict[str, Any]) -> Any:
        response = self._session.get(url, params=params, timeout=self._timeout_seconds)
        response.raise_for_status()
        return response.json()

    def search_recent(self, query: str, max_results: int) -> list[TweetPost]:
        payload = self._get_json(
            "https://api.twitter.com/2/tweets/search/recent",
            {
                "query": query,
                "max_results": max(10, min(100, max_results)),
                "tweet.fields": "created_at,author_id",
                "expansions": "author_id",
                "user.fields": "username",
            },
        )
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        includes = payload.get("includes", {}) if isinstance(payload, dict) else {}
        users = includes.get("users", []) if isinstance(includes, dict) else []
        usernames_by_id = {
            str(u.get("id", "")): str(u.get("username", "")).strip()
            for u in users
            if isinstance(u, dict)
        }

        from datetime import datetime

        posts: list[TweetPost] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            tweet_id = str(row.get("id", "")).strip()
            text = str(row.get("text", "") or "").strip()
            author_id = str(row.get("author_id", "")).strip()
            author = usernames_by_id.get(author_id, "")
            created_at = str(row.get("created_at", "")).strip()
            if not tweet_id or not text:
                continue
            created_ts = 0.0
            if created_at:
                try:
                    created_ts = datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp()
                except ValueError:
                    created_ts = 0.0
            posts.append(
                TweetPost(
                    thing_id=f"tw_{tweet_id}",
                    author=author or "unknown",
                    body=text,
                    permalink=f"https://x.com/{author or 'i'}/status/{tweet_id}",
                    created_at_ts=created_ts,
                )
            )
        return posts
