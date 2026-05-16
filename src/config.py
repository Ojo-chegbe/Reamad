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
    youtube_pain_keywords: list[str]
    youtube_knowledge_block: str
    youtube_prompt_template: str
    poll_seconds: int
    max_items_per_subreddit: int
    min_score: int
    early_reply_window_minutes: int
    google_api_key: str | None
    google_model: str
    reddit_relevance_model: str
    reddit_relevance_min_score: int
    reddit_local_fallback_min_score: int
    reddit_llm_relevance_enabled: bool
    reddit_ai_batch_size: int
    # Twitter / FxTwitter settings
    twitter_enabled: bool
    twitter_target_handles: list[str]
    twitter_queries: list[str]
    twitter_max_items: int
    twitter_min_score: int
    twitter_relevance_min_score: int
    # YouTube settings
    youtube_api_key: str | None
    youtube_enabled: bool
    youtube_target_channels: list[str]
    youtube_queries: list[str]
    youtube_max_videos: int
    youtube_max_comments_per_video: int
    youtube_min_score: int
    youtube_relevance_min_score: int
    youtube_local_fallback_min_score: int
    youtube_published_after_days: int
    youtube_max_search_queries: int
    youtube_ai_candidates_per_video: int


def load_settings(account_id: str | None = None) -> Settings:
    load_dotenv(override=True)
    profile = get_profile(account_id=account_id)
    profile_subreddits = profile.get("subreddits", [])

    return Settings(
        reddit_user_agent=os.getenv("REDDIT_USER_AGENT", "").strip(),
        target_subreddits=profile_subreddits,
        pain_subreddits=profile_subreddits,
        keywords=[],
        reddit_pain_keywords=[
            k.lower()
            for k in (
                profile.get("reddit_keywords", [])
                + profile.get("buying_signals", [])
                + profile.get("competitors", [])
            )
        ],
        twitter_pain_keywords=[
            k.lower()
            for k in (
                profile.get("twitter_keywords", [])
                + profile.get("buying_signals", [])
                + profile.get("competitors", [])
            )
        ],
        reddit_knowledge_block=profile.get("reddit_knowledge_block", ""),
        twitter_knowledge_block=profile.get("twitter_knowledge_block", ""),
        reddit_prompt_template=profile.get("reddit_prompt_template", "").strip(),
        twitter_prompt_template=profile.get("twitter_prompt_template", "").strip(),
        youtube_pain_keywords=[
            k.lower()
            for k in (
                profile.get("youtube_keywords", [])
                + profile.get("buying_signals", [])
                + profile.get("competitors", [])
            )
        ],
        youtube_knowledge_block=profile.get("youtube_knowledge_block", ""),
        youtube_prompt_template=profile.get("youtube_prompt_template", "").strip(),

        poll_seconds=int(os.getenv("POLL_SECONDS", "60")),
        max_items_per_subreddit=int(os.getenv("MAX_ITEMS_PER_SUBREDDIT", "50")),
        min_score=int(os.getenv("MIN_SCORE", "25")),
        early_reply_window_minutes=int(os.getenv("EARLY_REPLY_WINDOW_MINUTES", "90")),
        google_api_key=os.getenv("GOOGLE_API_KEY", "").strip() or None,
        google_model=os.getenv("GOOGLE_MODEL", "gemma-3-27b-it").strip(),
        reddit_relevance_model=os.getenv(
            "REDDIT_RELEVANCE_MODEL",
            os.getenv("GOOGLE_MODEL", "gemma-3-27b-it"),
        ).strip(),
        reddit_relevance_min_score=int(os.getenv("REDDIT_RELEVANCE_MIN_SCORE", "70")),
        reddit_local_fallback_min_score=int(os.getenv("REDDIT_LOCAL_FALLBACK_MIN_SCORE", "85")),
        reddit_llm_relevance_enabled=os.getenv("REDDIT_LLM_RELEVANCE_ENABLED", "1").strip().lower() in ("1", "true", "yes"),
        reddit_ai_batch_size=int(os.getenv("REDDIT_AI_BATCH_SIZE", "5")),
        # Twitter / FxTwitter
        twitter_enabled=os.getenv("TWITTER_ENABLED", "0").strip() in ("1", "true", "yes"),
        twitter_target_handles=profile.get("twitter_target_handles", []),
        twitter_queries=profile.get("twitter_queries", []),
        twitter_max_items=int(os.getenv("TWITTER_MAX_ITEMS", "25")),
        twitter_min_score=int(os.getenv("TWITTER_MIN_SCORE", "8")),
        twitter_relevance_min_score=int(os.getenv("TWITTER_RELEVANCE_MIN_SCORE", "25")),
        youtube_api_key=os.getenv("YOUTUBE_API_KEY", "").strip() or None,
        youtube_enabled=os.getenv("YOUTUBE_ENABLED", "0").strip() in ("1", "true", "yes"),
        youtube_target_channels=profile.get("youtube_target_channels", []),
        youtube_queries=profile.get("youtube_queries", []),
        youtube_max_videos=int(os.getenv("YOUTUBE_MAX_VIDEOS", "10")),
        youtube_max_comments_per_video=int(os.getenv("YOUTUBE_MAX_COMMENTS_PER_VIDEO", "50")),
        youtube_min_score=int(os.getenv("YOUTUBE_MIN_SCORE", "25")),
        youtube_relevance_min_score=int(os.getenv("YOUTUBE_RELEVANCE_MIN_SCORE", "65")),
        youtube_local_fallback_min_score=int(os.getenv("YOUTUBE_LOCAL_FALLBACK_MIN_SCORE", "85")),
        youtube_published_after_days=int(os.getenv("YOUTUBE_PUBLISHED_AFTER_DAYS", "14")),
        youtube_max_search_queries=int(os.getenv("YOUTUBE_MAX_SEARCH_QUERIES", "5")),
        youtube_ai_candidates_per_video=int(os.getenv("YOUTUBE_AI_CANDIDATES_PER_VIDEO", "5")),
    )
