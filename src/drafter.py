from __future__ import annotations

from typing import List

from google import genai

from src.config import Settings
from src.models import Opportunity
from src.soloa_profile import SOLOA_KNOWLEDGE_BLOCK


def _fallback_drafts(opportunity: Opportunity) -> List[str]:
    return [
        (
            "honestly the fastest fix is just having one repeatable flow. most time gets lost just switching between 5 different tools."
        ),
        (
            "i'd try a 7-day test using just one dashboard and prompt pack. measure how long it actually takes to get a final video instead of testing random tools all day."
        ),
    ]


def draft_comments(
    settings: Settings,
    opportunity: Opportunity,
    subreddit_rules: str,
) -> List[str]:
    if not settings.google_api_key:
        return _fallback_drafts(opportunity)

    client = genai.Client(api_key=settings.google_api_key)
    prompt = f"""
You are writing Reddit comment drafts for manual review.
Goal: Write exactly like a normal Reddit user. It must be very simple, casual, and conversational. Flow like a human wrote it off the cuff from their phone.
Community rules context:
{subreddit_rules or "No rules loaded."}

Soloa context to use when relevant:
{SOLOA_KNOWLEDGE_BLOCK}

Post title: {opportunity.title}
Post body: {opportunity.body[:2000]}
Post age in minutes: {opportunity.age_minutes}

Write exactly 3 short comment drafts.
Constraints:
- No direct CTA like "buy now", "sign up", "DM me"
- Zero AI-speak: do not use words like "crucial", "delve", "furthermore", "in conclusion", or "I understand your frustration"
- Write in a conversational, human tone (use natural pacing, avoid overly structured bullet points, occasional lowercase is fine)
- Helpful, specific, and extremely simple
- Use pain-first framing: acknowledge frustration, give a quick practical tip, then optional subtle mention
- Mention Soloa in at most one draft, and only naturally (e.g., "i ended up just using soloa to stop switching tabs so much")
- Prefer comments that fit early-thread replies (very concise and actionable)
Output as plain text with numbered lines 1..3.
""".strip()

    try:
        response = client.models.generate_content(
            model=settings.google_model,
            contents=prompt,
        )
    except Exception:
        return _fallback_drafts(opportunity)

    text = (response.text or "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    drafts = [
        line.split(". ", 1)[-1].strip()
        for line in lines
        if line and line[0].isdigit()
    ]
    return drafts[:3] if drafts else _fallback_drafts(opportunity)
