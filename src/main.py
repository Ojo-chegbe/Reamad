from __future__ import annotations

import time

from src.collector import collect_opportunities
from src.config import load_settings
from src.drafter import DraftGenerationError, draft_comments
from src.fxtwitter_client import FxTwitterClient
from src.notifier import notify
from src.playbook import refresh_subreddit_rules
from src.reddit_client import make_reddit
from src.store import Store
from src.twitter_collector import collect_fxtwitter_opportunities
from ui.state import init_db as init_ui_db
from ui.state import upsert_opportunity, upsert_playbook


def run() -> None:
    settings = load_settings()
    reddit = make_reddit(settings)
    store = Store()
    init_ui_db()

    # --- Reddit setup ---
    effective_subreddits = settings.target_subreddits or settings.pain_subreddits
    if not effective_subreddits:
        raise ValueError("Set TARGET_SUBREDDITS or PAIN_SUBREDDITS in .env")

    reddit_keywords = list(dict.fromkeys(settings.keywords + settings.reddit_pain_keywords))
    twitter_keywords = list(dict.fromkeys(settings.keywords + settings.twitter_pain_keywords))
    if not reddit_keywords and not twitter_keywords:
        raise ValueError("Set KEYWORDS and/or platform keyword lists in profile configuration")

    print("Refreshing subreddit rules...")
    refresh_subreddit_rules(reddit, store, effective_subreddits)
    for sub_name in effective_subreddits:
        upsert_playbook(sub_name, store.get_rules(sub_name))

    # --- Twitter / FxTwitter setup ---
    fxtwitter = None
    if settings.twitter_enabled:
        fxtwitter = FxTwitterClient()
        print(f"Twitter enabled via FxTwitter API (handles: {len(settings.twitter_target_handles)}, queries: {len(settings.twitter_queries)})")
    else:
        print("Twitter disabled (set TWITTER_ENABLED=1 in .env to enable)")

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
                keywords=reddit_keywords,
                pain_keywords=settings.reddit_pain_keywords,
                early_reply_window_minutes=settings.early_reply_window_minutes,
                max_items_per_subreddit=settings.max_items_per_subreddit,
                min_score=settings.min_score,
            ))
            print(f"Cycle {cycle}: found {len(opportunities)} Reddit opportunities")
            for opp in opportunities:
                rules = store.get_rules(opp.subreddit)
                try:
                    drafts = draft_comments(settings, opp, rules, "reddit")
                except DraftGenerationError as exc:
                    print(f"[drafter] skipped {opp.thing_id}: {exc}")
                    continue
                notify(opp, drafts)
                upsert_opportunity(
                    opportunity_id=opp.thing_id,
                    platform="reddit",
                    subreddit=opp.subreddit,
                    title=opp.title,
                    body=opp.body,
                    url=opp.permalink,
                    score=opp.score,
                    reasons=opp.reasons,
                    drafts=drafts,
                )
        except Exception as exc:
            print(f"Reddit loop error: {exc}")

        # --- Twitter collection via FxTwitter ---
        if fxtwitter:
            print(f"Cycle {cycle}: checking Twitter...")
            try:
                twitter_opps = list(collect_fxtwitter_opportunities(
                    fxtwitter=fxtwitter,
                    store=store,
                    target_handles=settings.twitter_target_handles,
                    query_terms=settings.twitter_queries,
                    keywords=twitter_keywords,
                    pain_keywords=settings.twitter_pain_keywords,
                    early_reply_window_minutes=settings.early_reply_window_minutes,
                    max_items=settings.twitter_max_items,
                    min_score=settings.min_score,
                ))
                print(f"Cycle {cycle}: found {len(twitter_opps)} Twitter opportunities")
                for opp in twitter_opps:
                    try:
                        drafts = draft_comments(settings, opp, "", "twitter")
                    except DraftGenerationError as exc:
                        print(f"[drafter] skipped {opp.thing_id}: {exc}")
                        continue
                    notify(opp, drafts)
                    upsert_opportunity(
                        opportunity_id=opp.thing_id,
                        platform="twitter",
                        subreddit=f"@{opp.author}",
                        title=opp.title,
                        body=opp.body,
                        url=opp.permalink,
                        score=opp.score,
                        reasons=opp.reasons,
                        drafts=drafts,
                    )
            except Exception as exc:
                print(f"Twitter loop error: {exc}")

        print(f"Cycle {cycle}: sleeping {settings.poll_seconds}s")
        time.sleep(settings.poll_seconds)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nStopped by user.")
