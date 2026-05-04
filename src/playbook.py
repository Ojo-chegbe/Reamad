from __future__ import annotations

from src.reddit_client import RedditClient
from src.store import Store


def refresh_subreddit_rules(
    reddit: RedditClient,
    store: Store,
    subreddits: list[str],
) -> None:
    for sub_name in subreddits:
        try:
            lines = reddit.get_subreddit_rules(sub_name)
        except Exception as exc:
            print(f"Rules refresh failed for r/{sub_name}: {exc}")
            if store.get_rules(sub_name):
                continue
            lines = ["Rules temporarily unavailable. Will retry."]

        if not lines:
            if store.get_rules(sub_name):
                continue
            lines = ["No public rules found."]

        store.upsert_rules(sub_name, "\n".join(lines).strip())
