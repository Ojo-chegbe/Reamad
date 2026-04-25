from __future__ import annotations

import time

from src.collector import collect_opportunities
from src.config import load_settings
from src.drafter import draft_comments
from src.notifier import notify
from src.playbook import refresh_subreddit_rules
from src.reddit_client import make_reddit
from src.store import Store


def run() -> None:
    settings = load_settings()
    reddit = make_reddit(settings)
    store = Store()

    if not settings.target_subreddits:
        raise ValueError("TARGET_SUBREDDITS is empty in .env")
    if not settings.keywords:
        raise ValueError("KEYWORDS is empty in .env")

    print("Refreshing subreddit rules...")
    refresh_subreddit_rules(reddit, store, settings.target_subreddits)

    print("Starting poll loop...")
    while True:
        try:
            opportunities = collect_opportunities(
                reddit=reddit,
                store=store,
                subreddits=settings.target_subreddits,
                keywords=settings.keywords,
                max_items_per_subreddit=settings.max_items_per_subreddit,
                min_score=settings.min_score,
            )
            for opp in opportunities:
                rules = store.get_rules(opp.subreddit)
                drafts = draft_comments(settings, opp, rules)
                notify(opp, drafts)
        except Exception as exc:
            print(f"Loop error: {exc}")

        time.sleep(settings.poll_seconds)


if __name__ == "__main__":
    run()

