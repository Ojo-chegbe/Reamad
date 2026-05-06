from __future__ import annotations

import sys

from src.models import Opportunity


def _safe_print(message: str = "") -> None:
    """Print text without crashing on Windows legacy console encodings."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        sanitized = message.encode(encoding, errors="replace").decode(encoding, errors="replace")
    except Exception:
        sanitized = message.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    print(sanitized)


def notify(opportunity: Opportunity, drafts: list[str]) -> None:
    _safe_print("\n" + "=" * 80)
    _safe_print(f"Subreddit: r/{opportunity.subreddit}")
    _safe_print(f"Score: {opportunity.score}")
    _safe_print(f"Age: {opportunity.age_minutes} minutes")
    _safe_print(f"Title: {opportunity.title}")
    _safe_print(f"URL: {opportunity.permalink}")
    _safe_print("Why:")
    for reason in opportunity.reasons:
        _safe_print(f"- {reason}")
    _safe_print("Suggested comments:")
    for idx, draft in enumerate(drafts, start=1):
        _safe_print(f"{idx}. {draft}")
    _safe_print("=" * 80 + "\n")
