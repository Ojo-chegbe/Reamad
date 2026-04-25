from __future__ import annotations

from typing import List

from openai import OpenAI

from src.config import Settings
from src.models import Opportunity


def _fallback_drafts(opportunity: Opportunity) -> List[str]:
    return [
        (
            "You might compare a few tools by use-case first (chat quality, image, video, and cost per output), "
            "then pick one stack for your core workflow. If helpful, I can share a simple evaluation checklist."
        ),
        (
            "A practical way to test this is a 7-day workflow trial: same prompt pack, same assets, then compare speed, "
            "quality consistency, and edit time. That usually shows what actually saves time."
        ),
    ]


def draft_comments(
    settings: Settings,
    opportunity: Opportunity,
    subreddit_rules: str,
) -> List[str]:
    if not settings.openai_api_key:
        return _fallback_drafts(opportunity)

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = f"""
You are writing Reddit comment drafts for manual review.
Goal: Be genuinely helpful. Avoid salesy tone, hype, or aggressive promotion.
Community rules context:
{subreddit_rules or "No rules loaded."}

Post title: {opportunity.title}
Post body: {opportunity.body[:2000]}

Write exactly 3 short comment drafts.
Constraints:
- No direct CTA like "buy now", "sign up", "DM me"
- No fake claims
- Helpful, specific, and conversational
- Mention Soloa only if naturally relevant and subtle
Output as plain text with numbered lines 1..3.
""".strip()

    response = client.responses.create(
        model=settings.openai_model,
        input=prompt,
    )
    text = response.output_text.strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    drafts = [line.split(". ", 1)[-1].strip() for line in lines if line[0].isdigit()]
    return drafts[:3] if drafts else _fallback_drafts(opportunity)

