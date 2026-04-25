from __future__ import annotations

from typing import Iterable

import praw

from src.models import Opportunity
from src.scorer import score_post
from src.store import Store


def _build_opportunity(
    submission,
    rules_text: str,
    keywords: list[str],
) -> Opportunity:
    body = submission.selftext or ""
    score, reasons = score_post(
        title=submission.title or "",
        body=body,
        subreddit_rules_text=rules_text,
        keywords=keywords,
    )
    return Opportunity(
        thing_id=submission.fullname,
        subreddit=str(submission.subreddit),
        title=submission.title or "",
        body=body,
        author=str(submission.author) if submission.author else "[deleted]",
        permalink=f"https://reddit.com{submission.permalink}",
        score=score,
        reasons=reasons,
    )


def collect_opportunities(
    reddit: praw.Reddit,
    store: Store,
    subreddits: list[str],
    keywords: list[str],
    max_items_per_subreddit: int,
    min_score: int,
) -> Iterable[Opportunity]:
    for sub_name in subreddits:
        subreddit = reddit.subreddit(sub_name)
        rules_text = store.get_rules(sub_name)
        for submission in subreddit.new(limit=max_items_per_subreddit):
            if store.is_seen(submission.fullname):
                continue

            opp = _build_opportunity(submission, rules_text, keywords)
            store.mark_seen(submission.fullname)
            if opp.score >= min_score:
                yield opp

