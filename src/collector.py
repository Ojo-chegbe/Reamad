from __future__ import annotations

import time
from typing import Iterable

from src.models import Opportunity
from src.reddit_client import RedditClient, RedditPost
from src.scorer import score_post
from src.store import Store


def _build_opportunity(
    submission: RedditPost,
    rules_text: str,
    keywords: list[str],
    pain_keywords: list[str],
    knowledge_block: str,
    early_reply_window_minutes: int,
) -> Opportunity:
    body = submission.body or ""
    score, reasons = score_post(
        title=submission.title,
        body=body,
        subreddit_rules_text=rules_text,
        keywords=keywords,
        pain_keywords=pain_keywords,
        knowledge_block=knowledge_block,
        created_utc=submission.created_utc,
        early_reply_window_minutes=early_reply_window_minutes,
    )
    age_minutes = max(0, int((time.time() - submission.created_utc) / 60)) if submission.created_utc > 0 else 0
    return Opportunity(
        thing_id=submission.thing_id,
        subreddit=submission.subreddit,
        title=submission.title,
        body=body,
        author=submission.author or "[deleted]",
        permalink=submission.permalink,
        score=score,
        created_utc=submission.created_utc,
        age_minutes=age_minutes,
        reasons=reasons,
    )


def collect_opportunities(
    reddit: RedditClient,
    store: Store,
    subreddits: list[str],
    keywords: list[str],
    pain_keywords: list[str],
    knowledge_block: str,
    early_reply_window_minutes: int,
    max_items_per_subreddit: int,
    min_score: int,
) -> Iterable[Opportunity]:
    reddit_blocked = False
    for sub_name in subreddits:
        if reddit_blocked:
            break
        rules_text = store.get_rules(sub_name)
        try:
            submissions = reddit.get_new_posts(sub_name, limit=max_items_per_subreddit)
        except Exception as exc:
            error_text = str(exc)
            if "403" in error_text and "Blocked" in error_text:
                print("Collect blocked by Reddit (HTTP 403). Pausing subreddit checks for this cycle.")
                reddit_blocked = True
                continue
            print(f"Collect failed for r/{sub_name}: {exc}")
            continue

        for submission in submissions:
            if store.is_seen(submission.thing_id):
                continue
            opp = _build_opportunity(
                submission=submission,
                rules_text=rules_text,
                keywords=keywords,
                pain_keywords=pain_keywords,
                knowledge_block=knowledge_block,
                early_reply_window_minutes=early_reply_window_minutes,
            )
            if opp.score >= min_score:
                store.mark_seen(submission.thing_id)
                yield opp
