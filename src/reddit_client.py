from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from src.config import Settings


@dataclass(frozen=True)
class RedditPost:
    thing_id: str
    subreddit: str
    title: str
    body: str
    author: str
    permalink: str
    link_url: str
    created_utc: float


class RedditClient:
    def __init__(self, user_agent: str, timeout_seconds: int = 15) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "application/json",
            }
        )
        self._timeout_seconds = timeout_seconds

    def _get_json(self, url: str) -> Any:
        response = self._session.get(url, timeout=self._timeout_seconds)
        response.raise_for_status()
        return response.json()

    def get_new_posts(self, subreddit: str, limit: int) -> list[RedditPost]:
        url = f"https://www.reddit.com/r/{subreddit}/new.json?limit={limit}&raw_json=1"
        payload = self._get_json(url)
        children = payload.get("data", {}).get("children", []) if isinstance(payload, dict) else []
        posts: list[RedditPost] = []
        for child in children[:limit]:
            data = child.get("data", {}) if isinstance(child, dict) else {}
            if not isinstance(data, dict):
                continue
            thing_id = str(data.get("name", "")).strip()
            if not thing_id:
                continue
            title = str(data.get("title", "")).strip()
            body = str(data.get("selftext", "") or "").strip()
            author = str(data.get("author", "") or "[deleted]").strip()
            post_subreddit = str(data.get("subreddit", subreddit)).strip()
            reddit_permalink = str(data.get("permalink", "") or "").strip()
            canonical = f"https://reddit.com{reddit_permalink}" if reddit_permalink else ""
            link_url = str(data.get("url", canonical)).strip()
            created_utc_raw = data.get("created_utc", 0)
            try:
                created_utc = float(created_utc_raw)
            except (TypeError, ValueError):
                created_utc = 0.0
            posts.append(
                RedditPost(
                    thing_id=thing_id,
                    subreddit=post_subreddit,
                    title=title,
                    body=body,
                    author=author,
                    permalink=canonical,
                    link_url=link_url,
                    created_utc=created_utc,
                )
            )
        return posts

    def get_subreddit_rules(self, subreddit: str) -> list[str]:
        rules_url = f"https://www.reddit.com/r/{subreddit}/about/rules.json?raw_json=1"
        payload = self._get_json(rules_url)
        raw_rules = payload.get("rules", []) if isinstance(payload, dict) else []
        lines: list[str] = []
        for rule in raw_rules:
            if not isinstance(rule, dict):
                continue
            short = str(rule.get("short_name", "") or "").strip()
            desc = str(rule.get("description", "") or "").strip()
            if short and desc:
                lines.append(f"{short}: {desc}")
            elif short:
                lines.append(short)
            elif desc:
                lines.append(desc)
        return lines


def make_reddit(settings: Settings) -> RedditClient:
    if not settings.reddit_user_agent:
        raise ValueError("REDDIT_USER_AGENT is required in .env")
    return RedditClient(user_agent=settings.reddit_user_agent)
