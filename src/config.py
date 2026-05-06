from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from src.soloa_profile import get_profile


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    reddit_user_agent: str
    target_subreddits: list[str]
    pain_subreddits: list[str]
    keywords: list[str]
    reddit_pain_keywords: list[str]
    twitter_pain_keywords: list[str]
    reddit_knowledge_block: str
    twitter_knowledge_block: str
    reddit_prompt_template: str
    twitter_prompt_template: str
    poll_seconds: int
    max_items_per_subreddit: int
    min_score: int
    early_reply_window_minutes: int
    google_api_key: str | None
    google_model: str
    # Twitter / FxTwitter settings
    twitter_enabled: bool
    twitter_target_handles: list[str]
    twitter_queries: list[str]
    twitter_max_items: int


def load_settings() -> Settings:
    load_dotenv(override=True)
    profile = get_profile()

    return Settings(
        reddit_user_agent=os.getenv("REDDIT_USER_AGENT", "").strip(),
        target_subreddits=_csv(os.getenv("TARGET_SUBREDDITS", "")),
        pain_subreddits=profile.get("subreddits", _csv(os.getenv("PAIN_SUBREDDITS", ""))),
        keywords=[k.lower() for k in _csv(os.getenv("KEYWORDS", ""))],
        reddit_pain_keywords=[k.lower() for k in profile.get("reddit_keywords", _csv(os.getenv("PAIN_KEYWORDS", "")))],
        twitter_pain_keywords=[k.lower() for k in profile.get("twitter_keywords", _csv(os.getenv("PAIN_KEYWORDS", "")))],
        reddit_knowledge_block=profile.get("reddit_knowledge_block", ""),
        twitter_knowledge_block=profile.get("twitter_knowledge_block", ""),
        reddit_prompt_template=profile.get("reddit_prompt_template", "").strip(),
        twitter_prompt_template=profile.get("twitter_prompt_template", "").strip(),

        poll_seconds=int(os.getenv("POLL_SECONDS", "60")),
        max_items_per_subreddit=int(os.getenv("MAX_ITEMS_PER_SUBREDDIT", "50")),
        min_score=int(os.getenv("MIN_SCORE", "25")),
        early_reply_window_minutes=int(os.getenv("EARLY_REPLY_WINDOW_MINUTES", "90")),
        google_api_key=os.getenv("GOOGLE_API_KEY", "").strip() or None,
        google_model=os.getenv("GOOGLE_MODEL", "gemma-3-27b-it").strip(),
        # Twitter / FxTwitter
        twitter_enabled=os.getenv("TWITTER_ENABLED", "0").strip() in ("1", "true", "yes"),
        twitter_target_handles=_csv(os.getenv("TWITTER_TARGET_HANDLES", "")),
        twitter_queries=_csv(os.getenv("TWITTER_QUERIES", "")),
        twitter_max_items=int(os.getenv("TWITTER_MAX_ITEMS", "25")),
    )
