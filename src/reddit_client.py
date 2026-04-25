from __future__ import annotations

import praw

from src.config import Settings


def make_reddit(settings: Settings) -> praw.Reddit:
    required = [
        settings.reddit_client_id,
        settings.reddit_client_secret,
        settings.reddit_username,
        settings.reddit_password,
        settings.reddit_user_agent,
    ]
    if any(not item for item in required):
        raise ValueError("Missing Reddit credentials in .env")

    return praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        username=settings.reddit_username,
        password=settings.reddit_password,
        user_agent=settings.reddit_user_agent,
        check_for_async=False,
    )

