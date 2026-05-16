from __future__ import annotations

import re
import time


def _extract_knowledge_terms(knowledge_block: str) -> list[str]:
    lines = [ln.strip("- ").strip().lower() for ln in (knowledge_block or "").splitlines()]
    ignored_exact = {
        "campaign/product knowledge",
        "product knowledge",
        "company/product knowledge",
        "features",
        "tools",
        "overview",
    }
    terms: list[str] = []
    for ln in lines:
        if not ln:
            continue
        # Keep compact capability phrases from knowledge bullets.
        parts = [p.strip() for p in re.split(r"[,:;]", ln) if p.strip()]
        for p in parts:
            if p in ignored_exact:
                continue
            if len(p) >= 4 and len(p.split()) <= 6:
                terms.append(p)
    # Deduplicate while preserving order.
    unique: list[str] = []
    seen: set[str] = set()
    for t in terms:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique[:80]


def score_post(
    title: str,
    body: str,
    subreddit_rules_text: str,
    keywords: list[str],
    pain_keywords: list[str],
    knowledge_block: str,
    created_utc: float,
    early_reply_window_minutes: int,
    platform: str = "reddit",
) -> tuple[int, list[str]]:
    text = f"{title}\n{body}".lower()
    score = 0
    reasons: list[str] = []

    # Primary signal: does this map to what the company can solve?
    knowledge_terms = _extract_knowledge_terms(knowledge_block)
    fit_hits = [term for term in knowledge_terms if term and term in text]
    is_twitter = platform.strip().lower() == "twitter"

    if fit_hits:
        score += min(45, 9 * len(fit_hits))
        reasons.append(f"Solution-fit match: {', '.join(fit_hits[:4])}")
    else:
        score -= 8 if is_twitter else 20
        reasons.append("Low solution fit to configured company knowledge")

    # Strong intent: user is asking for a fix/tool/process.
    intent_regex = (
        r"\b(help|how|tool|recommend|looking for|best way|workflow|process|stuck|struggling|fix|any suggestions)\b"
    )
    if is_twitter:
        # On X, constrain intent to genuine ask patterns to avoid promo tweets scoring as intent.
        solution_intent = bool(
            ("?" in text)
            or re.search(r"\b(can anyone|anyone know|what is the best|how do i|how to)\b", text)
        ) and bool(re.search(intent_regex, text))
    else:
        solution_intent = bool(re.search(intent_regex, text))
    if solution_intent:
        score += 22
        reasons.append("Explicit solution-seeking intent detected")

    kw_hits = [kw for kw in keywords if kw in text]
    if kw_hits:
        score += min(20, 5 * len(kw_hits))
        reasons.append(f"Keyword match: {', '.join(kw_hits[:4])}")

    pain_hits = [kw for kw in pain_keywords if kw in text]
    if pain_hits:
        score += min(20, 6 * len(pain_hits))
        reasons.append(f"Pain signal match: {', '.join(pain_hits[:3])}")

    # Penalize common noise buckets on X that are rarely product-solution fit.
    noise_patterns = [
        r"\b(football|arsenal|chelsea|barcelona|real madrid)\b",
        r"\b(anime|star wars|movie|music stan|fandom)\b",
        r"\b(politics|election|senate|president)\b",
    ]
    if any(re.search(pat, text) for pat in noise_patterns):
        score -= 18
        reasons.append("Looks like off-domain conversation/noise")

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

    # On Twitter, hard-gate on knowledge fit so unrelated tweets never pass on freshness alone.
    if is_twitter and not fit_hits:
        score = min(score, 5)
        reasons.append("Rejected for Twitter: no direct knowledge-box relevance")

    # Require some minimal fit+intent quality to pass meaningful thresholds.
    if not fit_hits and not solution_intent and not kw_hits and not pain_hits:
        score -= 15
        reasons.append("No clear fit+intent combination")

    score = max(0, min(100, score))
    return score, reasons
