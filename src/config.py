from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    reddit_client_id: str
    reddit_client_secret: str
    reddit_username: str
    reddit_password: str
    reddit_user_agent: str
    target_subreddits: list[str]
    keywords: list[str]
    poll_seconds: int
    max_items_per_subreddit: int
    min_score: int
    openai_api_key: str | None
    openai_model: str


def load_settings() -> Settings:
    load_dotenv()

    return Settings(
        reddit_client_id=os.getenv("REDDIT_CLIENT_ID", "").strip(),
        reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET", "").strip(),
        reddit_username=os.getenv("REDDIT_USERNAME", "").strip(),
        reddit_password=os.getenv("REDDIT_PASSWORD", "").strip(),
        reddit_user_agent=os.getenv("REDDIT_USER_AGENT", "").strip(),
        target_subreddits=_csv(os.getenv("TARGET_SUBREDDITS", "")),
        keywords=[k.lower() for k in _csv(os.getenv("KEYWORDS", ""))],
        poll_seconds=int(os.getenv("POLL_SECONDS", "180")),
        max_items_per_subreddit=int(os.getenv("MAX_ITEMS_PER_SUBREDDIT", "20")),
        min_score=int(os.getenv("MIN_SCORE", "55")),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip() or None,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
    )

