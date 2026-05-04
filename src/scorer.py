from __future__ import annotations

import re
import time


def score_post(
    title: str,
    body: str,
    subreddit_rules_text: str,
    keywords: list[str],
    pain_keywords: list[str],
    created_utc: float,
    early_reply_window_minutes: int,
) -> tuple[int, list[str]]:
    text = f"{title}\n{body}".lower()
    score = 0
    reasons: list[str] = []

    kw_hits = [kw for kw in keywords if kw in text]
    if kw_hits:
        score += min(30, 8 * len(kw_hits))
        reasons.append(f"Keyword match: {', '.join(kw_hits[:4])}")

    pain_hits = [kw for kw in pain_keywords if kw in text]
    if pain_hits:
        score += min(45, 12 * len(pain_hits))
        reasons.append(f"Pain signal match: {', '.join(pain_hits[:3])}")

    question_like = bool(re.search(r"\b(help|how|tool|recommend|looking for|best|struggling|stuck)\b", text))
    if question_like:
        score += 20
        reasons.append("Looks like a request where a helpful comment can add value")

    if created_utc > 0:
        age_minutes = max(0, int((time.time() - created_utc) / 60))
        if age_minutes <= early_reply_window_minutes:
            score += 20
            reasons.append(f"Fresh thread ({age_minutes}m old): early reply advantage")
        elif age_minutes <= (early_reply_window_minutes * 3):
            score += 8
            reasons.append(f"Still recent ({age_minutes}m old)")

    promo_penalty_terms = ["buy now", "coupon", "discount", "affiliate", "dm me"]
    if any(term in text for term in promo_penalty_terms):
        score -= 20
        reasons.append("Looks highly promotional already")

    rules_text = subreddit_rules_text.lower()
    if "no self-promotion" in rules_text or "no promotion" in rules_text:
        score -= 15
        reasons.append("Subreddit rules appear strict on promotion")
    if "weekly promo thread" in rules_text:
        score += 10
        reasons.append("Community may allow promo in designated thread")

    score = max(0, min(100, score))
    return score, reasons
