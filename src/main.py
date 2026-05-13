from __future__ import annotations

import os
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
    store = Store()
    init_ui_db()
    engine_mode = os.getenv("ENGINE_MODE", "both").strip().lower()
    run_reddit = engine_mode in ("both", "reddit")
    run_twitter = engine_mode in ("both", "twitter")

    if not run_reddit and not run_twitter:
        raise ValueError("ENGINE_MODE must be one of: both, reddit, twitter")

    # --- Reddit setup ---
    reddit = None
    effective_subreddits: list[str] = []
    reddit_keywords: list[str] = []
    if run_reddit:
        reddit = make_reddit(settings)
        effective_subreddits = settings.target_subreddits or settings.pain_subreddits
        if not effective_subreddits:
            raise ValueError("Set TARGET_SUBREDDITS or PAIN_SUBREDDITS in .env")

        reddit_keywords = list(dict.fromkeys(settings.keywords + settings.reddit_pain_keywords))
        if not reddit_keywords:
            raise ValueError("Set KEYWORDS and/or reddit keyword lists in profile configuration")

        print("Refreshing subreddit rules...")
        refresh_subreddit_rules(reddit, store, effective_subreddits)
        for sub_name in effective_subreddits:
            upsert_playbook(sub_name, store.get_rules(sub_name))

    # --- Twitter / FxTwitter setup ---
    fxtwitter = None
    if run_twitter and settings.twitter_enabled:
        fxtwitter = FxTwitterClient()
        print(f"Twitter enabled via FxTwitter API (handles: {len(settings.twitter_target_handles)}, queries: {len(settings.twitter_queries)})")
    elif run_twitter:
        print("Twitter disabled (set TWITTER_ENABLED=1 in .env to enable)")
    else:
        print("Twitter engine not selected for this process")

    if not run_reddit:
        print("Reddit engine not selected for this process")

    print("Starting poll loop...")
    cycle = 0
    while True:
        cycle += 1
        if run_reddit and reddit is not None:
            print(f"Cycle {cycle}: checking subreddits...")
            try:
                opportunities = list(collect_opportunities(
                    reddit=reddit,
                    store=store,
                    subreddits=effective_subreddits,
                    keywords=reddit_keywords,
                    pain_keywords=settings.reddit_pain_keywords,
                    knowledge_block=settings.reddit_knowledge_block,
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
                    store.mark_seen(opp.thing_id)
            except Exception as exc:
                print(f"Reddit loop error: {exc}")

        # --- Twitter collection via FxTwitter ---
        if run_twitter and fxtwitter:
            print(f"Cycle {cycle}: checking Twitter...")
            try:
                twitter_found = 0
                for opp in collect_fxtwitter_opportunities(
                    fxtwitter=fxtwitter,
                    store=store,
                    target_handles=settings.twitter_target_handles,
                    query_terms=settings.twitter_queries,
                    prompt_template=settings.twitter_prompt_template,
                    knowledge_block=settings.twitter_knowledge_block,
                    early_reply_window_minutes=settings.early_reply_window_minutes,
                    max_items=settings.twitter_max_items,
                    min_score=max(1, settings.twitter_min_score),
                    google_api_key=settings.google_api_key,
                    google_model=settings.google_model,
                    relevance_min_score=settings.twitter_relevance_min_score,
                ):
                    twitter_found += 1
                    print(f"Cycle {cycle}: drafting Twitter opportunity {twitter_found} ({opp.thing_id})")
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
                    store.mark_seen(opp.thing_id)
                    print(f"Cycle {cycle}: saved Twitter drafts for {opp.thing_id}")
                print(f"Cycle {cycle}: found {twitter_found} Twitter opportunities")
            except Exception as exc:
                print(f"Twitter loop error: {exc}")

        print(f"Cycle {cycle}: sleeping {settings.poll_seconds}s")
        time.sleep(settings.poll_seconds)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nStopped by user.")
