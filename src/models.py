from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Opportunity:
    thing_id: str
    subreddit: str
    title: str
    body: str
    author: str
    permalink: str
    score: int
    created_utc: float
    age_minutes: int
    reasons: list[str]
