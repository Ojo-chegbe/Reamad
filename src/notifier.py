from __future__ import annotations

from src.models import Opportunity


def notify(opportunity: Opportunity, drafts: list[str]) -> None:
    print("\n" + "=" * 80)
    print(f"Subreddit: r/{opportunity.subreddit}")
    print(f"Score: {opportunity.score}")
    print(f"Age: {opportunity.age_minutes} minutes")
    print(f"Title: {opportunity.title}")
    print(f"URL: {opportunity.permalink}")
    print("Why:")
    for reason in opportunity.reasons:
        print(f"- {reason}")
    print("Suggested comments:")
    for idx, draft in enumerate(drafts, start=1):
        print(f"{idx}. {draft}")
    print("=" * 80 + "\n")
