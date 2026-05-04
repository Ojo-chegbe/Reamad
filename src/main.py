from __future__ import annotations

import time

from src.collector import collect_opportunities
from src.config import load_settings
from src.drafter import draft_comments
from src.notifier import notify
from src.playbook import refresh_subreddit_rules
from src.reddit_client import make_reddit
from src.store import Store
from ui.state import init_db as init_ui_db
from ui.state import upsert_opportunity, upsert_playbook


def run() -> None:
    settings = load_settings()
    reddit = make_reddit(settings)
    store = Store()
    init_ui_db()

    effective_subreddits = settings.target_subreddits or settings.pain_subreddits
    if not effective_subreddits:
        raise ValueError("Set TARGET_SUBREDDITS or PAIN_SUBREDDITS in .env")

    effective_keywords = list(dict.fromkeys(settings.keywords + settings.pain_keywords))
    if not effective_keywords:
        raise ValueError("Set KEYWORDS or PAIN_KEYWORDS in .env")

    print("Refreshing subreddit rules...")
    refresh_subreddit_rules(reddit, store, effective_subreddits)
    for sub_name in effective_subreddits:
        upsert_playbook(sub_name, store.get_rules(sub_name))

    print("Starting poll loop...")
    cycle = 0
    while True:
        cycle += 1
        print(f"Cycle {cycle}: checking subreddits...")
        try:
            opportunities = list(collect_opportunities(
                reddit=reddit,
                store=store,
                subreddits=effective_subreddits,
                keywords=effective_keywords,
                pain_keywords=settings.pain_keywords,
                early_reply_window_minutes=settings.early_reply_window_minutes,
                max_items_per_subreddit=settings.max_items_per_subreddit,
                min_score=settings.min_score,
            ))
            print(f"Cycle {cycle}: found {len(opportunities)} opportunities")
            for opp in opportunities:
                rules = store.get_rules(opp.subreddit)
                drafts = draft_comments(settings, opp, rules)
                notify(opp, drafts)
                upsert_opportunity(
                    opportunity_id=opp.thing_id,
                    subreddit=opp.subreddit,
                    title=opp.title,
                    body=opp.body,
                    url=opp.permalink,
                    score=opp.score,
                    reasons=opp.reasons,
                    drafts=drafts,
                )
        except Exception as exc:
            print(f"Loop error: {exc}")

        print(f"Cycle {cycle}: sleeping {settings.poll_seconds}s")
        time.sleep(settings.poll_seconds)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nStopped by user.")
