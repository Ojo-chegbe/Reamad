from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from src.soloa_profile import DEFAULT_PAIN_KEYWORDS, DEFAULT_PAIN_SUBREDDITS


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    reddit_user_agent: str
    target_subreddits: list[str]
    pain_subreddits: list[str]
    keywords: list[str]
    pain_keywords: list[str]
    poll_seconds: int
    max_items_per_subreddit: int
    min_score: int
    early_reply_window_minutes: int
    google_api_key: str | None
    google_model: str


def load_settings() -> Settings:
    load_dotenv(override=True)

    return Settings(
        reddit_user_agent=os.getenv("REDDIT_USER_AGENT", "").strip(),
        target_subreddits=_csv(os.getenv("TARGET_SUBREDDITS", "")),
        pain_subreddits=_csv(os.getenv("PAIN_SUBREDDITS", ",".join(DEFAULT_PAIN_SUBREDDITS))),
        keywords=[k.lower() for k in _csv(os.getenv("KEYWORDS", ""))],
        pain_keywords=[k.lower() for k in _csv(os.getenv("PAIN_KEYWORDS", ",".join(DEFAULT_PAIN_KEYWORDS)))],
        poll_seconds=int(os.getenv("POLL_SECONDS", "60")),
        max_items_per_subreddit=int(os.getenv("MAX_ITEMS_PER_SUBREDDIT", "50")),
        min_score=int(os.getenv("MIN_SCORE", "25")),
        early_reply_window_minutes=int(os.getenv("EARLY_REPLY_WINDOW_MINUTES", "90")),
        google_api_key=os.getenv("GOOGLE_API_KEY", "").strip() or None,
        google_model=os.getenv("GOOGLE_MODEL", "gemma-3-27b-it").strip(),
    )
