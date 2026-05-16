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
from src.youtube_client import YouTubeClient
from src.youtube_collector import collect_youtube_opportunities
from ui.state import init_db as init_ui_db
from ui.state import upsert_opportunity, upsert_playbook


def _is_rate_limited_error(message: str) -> bool:
    text = (message or "").lower()
    markers = (
        "429",
        "rate limit",
        "quota",
        "resource_exhausted",
        "too many requests",
    )
    return any(marker in text for marker in markers)


def _is_transient_ai_error(message: str) -> bool:
    text = (message or "").lower()
    markers = (
        "500",
        "internal",
        "unavailable",
        "deadline_exceeded",
        "timeout",
    )
    return any(marker in text for marker in markers)


def run() -> None:
    account_id = os.getenv("SOLOA_ACCOUNT_ID", "soloa-ai").strip() or "soloa-ai"
    settings = load_settings(account_id=account_id)
    store = Store(account_id=account_id)
    init_ui_db()
    engine_mode = os.getenv("ENGINE_MODE", "both").strip().lower()
    run_reddit = engine_mode in ("both", "reddit")
    run_twitter = engine_mode in ("both", "twitter")
    run_youtube = engine_mode in ("both", "youtube")

    if not run_reddit and not run_twitter and not run_youtube:
        raise ValueError("ENGINE_MODE must be one of: both, reddit, twitter, youtube")

    print(
        "Model config: "
        f"draft={settings.google_model}, "
        f"reddit_relevance={settings.reddit_relevance_model}, "
        f"twitter/youtube_relevance={settings.google_model}"
    )

    # --- Reddit setup ---
    reddit = None
    effective_subreddits: list[str] = []
    if run_reddit:
        reddit = make_reddit(settings)
        effective_subreddits = settings.target_subreddits or settings.pain_subreddits
        if not effective_subreddits:
            raise ValueError("Add target subreddits in the active account profile configuration")

        print("Refreshing subreddit rules...")
        refresh_subreddit_rules(reddit, store, effective_subreddits)
        for sub_name in effective_subreddits:
            upsert_playbook(sub_name, store.get_rules(sub_name), account_id=account_id)

    # --- Twitter / FxTwitter setup ---
    fxtwitter = None
    if run_twitter and settings.twitter_enabled:
        fxtwitter = FxTwitterClient()
        print(f"Twitter enabled via FxTwitter API (handles: {len(settings.twitter_target_handles)}, queries: {len(settings.twitter_queries)})")
    elif run_twitter:
        print("Twitter disabled (set TWITTER_ENABLED=1 in .env to enable)")
    else:
        print("Twitter engine not selected for this process")

    youtube = None
    if run_youtube and settings.youtube_enabled and settings.youtube_api_key:
        youtube = YouTubeClient(api_key=settings.youtube_api_key)
        print(f"YouTube enabled (queries: {len(settings.youtube_queries)}, max videos: {settings.youtube_max_videos})")
    elif run_youtube and settings.youtube_enabled:
        print("YouTube disabled for this cycle: YOUTUBE_API_KEY is missing")
    elif run_youtube:
        print("YouTube disabled (set YOUTUBE_ENABLED=1 in .env to enable)")
    else:
        print("YouTube engine not selected for this process")

    if not run_reddit:
        print("Reddit engine not selected for this process")

    print("Starting poll loop...")
    cycle = 0
    reddit_draft_cooldown_until = 0.0
    reddit_pending_opp = None
    reddit_after_save_pause_seconds = max(0, int(os.getenv("REDDIT_AFTER_SAVE_PAUSE_SECONDS", "8")))
    while True:
        cycle += 1
        if run_reddit and reddit is not None:
            now = time.time()
            if now < reddit_draft_cooldown_until:
                remaining = int((reddit_draft_cooldown_until - now) / 60) + 1
                print(f"Cycle {cycle}: Reddit cooldown active for about {remaining}m before retrying")
            else:
                print(f"Cycle {cycle}: checking subreddits...")
                try:
                    reddit_found = 0
                    if reddit_pending_opp is not None:
                        reddit_iterable = [reddit_pending_opp]
                        print(f"Cycle {cycle}: retrying pending Reddit opportunity ({reddit_pending_opp.thing_id}) before searching")
                    else:
                        reddit_iterable = collect_opportunities(
                            reddit=reddit,
                            store=store,
                            subreddits=effective_subreddits,
                            prompt_template=settings.reddit_prompt_template,
                            keywords=settings.reddit_pain_keywords,
                            pain_keywords=settings.reddit_pain_keywords,
                            knowledge_block=settings.reddit_knowledge_block,
                            early_reply_window_minutes=settings.early_reply_window_minutes,
                            max_items_per_subreddit=settings.max_items_per_subreddit,
                            min_score=settings.min_score,
                            google_api_key=settings.google_api_key,
                            google_model=settings.reddit_relevance_model,
                            relevance_min_score=settings.reddit_relevance_min_score,
                            local_fallback_min_score=settings.reddit_local_fallback_min_score,
                            use_llm_relevance=settings.reddit_llm_relevance_enabled,
                            ai_batch_size=settings.reddit_ai_batch_size,
                        )

                    for opp in reddit_iterable:
                        reddit_found += 1
                        print(f"Cycle {cycle}: drafting Reddit opportunity {reddit_found} ({opp.thing_id})")
                        rules = store.get_rules(opp.subreddit)
                        try:
                            drafts = draft_comments(settings, opp, rules, "reddit")
                        except DraftGenerationError as exc:
                            error_text = str(exc)
                            if _is_rate_limited_error(error_text):
                                reddit_pending_opp = opp
                                reddit_draft_cooldown_until = time.time() + (15 * 60)
                                print(
                                    f"[drafter] Reddit rate limited on {opp.thing_id}: {exc}. "
                                    "Pausing Reddit drafting/search for 15m."
                                )
                                break
                            if _is_transient_ai_error(error_text):
                                reddit_pending_opp = opp
                                reddit_draft_cooldown_until = time.time() + (5 * 60)
                                print(
                                    f"[drafter] Reddit transient model failure on {opp.thing_id}: {exc}. "
                                    "Pausing Reddit drafting/search for 5m."
                                )
                                break
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
                            account_id=account_id,
                        )
                        store.mark_seen(opp.thing_id)
                        reddit_pending_opp = None
                        print(f"Cycle {cycle}: saved Reddit drafts for {opp.thing_id}")
                        if reddit_after_save_pause_seconds:
                            print(f"Cycle {cycle}: resting {reddit_after_save_pause_seconds}s after saving Reddit drafts")
                            time.sleep(reddit_after_save_pause_seconds)
                    print(f"Cycle {cycle}: found {reddit_found} Reddit opportunities")
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
                        account_id=account_id,
                    )
                    store.mark_seen(opp.thing_id)
                    print(f"Cycle {cycle}: saved Twitter drafts for {opp.thing_id}")
                print(f"Cycle {cycle}: found {twitter_found} Twitter opportunities")
            except Exception as exc:
                print(f"Twitter loop error: {exc}")

        if run_youtube and youtube:
            print(f"Cycle {cycle}: checking YouTube...")
            try:
                youtube_found = 0
                for opp in collect_youtube_opportunities(
                    youtube=youtube,
                    store=store,
                    query_terms=settings.youtube_queries,
                    target_channels=settings.youtube_target_channels,
                    prompt_template=settings.youtube_prompt_template,
                    knowledge_block=settings.youtube_knowledge_block,
                    pain_keywords=settings.youtube_pain_keywords,
                    early_reply_window_minutes=settings.early_reply_window_minutes,
                    max_videos=settings.youtube_max_videos,
                    max_comments_per_video=settings.youtube_max_comments_per_video,
                    min_score=settings.youtube_min_score,
                    relevance_min_score=settings.youtube_relevance_min_score,
                    local_fallback_min_score=settings.youtube_local_fallback_min_score,
                    published_after_days=settings.youtube_published_after_days,
                    max_search_queries=settings.youtube_max_search_queries,
                    ai_candidates_per_video=settings.youtube_ai_candidates_per_video,
                    google_api_key=settings.google_api_key,
                    google_model=settings.google_model,
                ):
                    youtube_found += 1
                    print(f"Cycle {cycle}: drafting YouTube opportunity {youtube_found} ({opp.thing_id})")
                    try:
                        drafts = draft_comments(settings, opp, "", "youtube")
                    except DraftGenerationError as exc:
                        print(f"[drafter] skipped {opp.thing_id}: {exc}")
                        continue
                    notify(opp, drafts)
                    upsert_opportunity(
                        opportunity_id=opp.thing_id,
                        platform="youtube",
                        subreddit=opp.subreddit,
                        title=opp.title,
                        body=opp.body,
                        url=opp.permalink,
                        score=opp.score,
                        reasons=opp.reasons,
                        drafts=drafts,
                        account_id=account_id,
                    )
                    store.mark_seen(opp.thing_id)
                    print(f"Cycle {cycle}: saved YouTube drafts for {opp.thing_id}")
                print(f"Cycle {cycle}: found {youtube_found} YouTube opportunities")
            except Exception as exc:
                print(f"YouTube loop error: {exc}")

        print(f"Cycle {cycle}: sleeping {settings.poll_seconds}s")
        time.sleep(settings.poll_seconds)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nStopped by user.")
