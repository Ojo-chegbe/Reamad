from __future__ import annotations

import time
from typing import List

from google import genai

from src.config import Settings
from src.models import Opportunity


class DraftGenerationError(RuntimeError):
    pass


def _immutable_context_block(
    opportunity: Opportunity,
    community_rules: str,
    knowledge_block: str,
) -> str:
    return (
        "Community rules context:\n"
        f"{community_rules}\n\n"
        "Soloa context to use when relevant:\n"
        f"{knowledge_block}\n\n"
        f"Post title: {opportunity.title}\n"
        f"Post body: {(opportunity.body or '')[:2000]}\n"
        f"Post age in minutes: {opportunity.age_minutes}"
    )


def _render_prompt(
    settings: Settings,
    opportunity: Opportunity,
    subreddit_rules: str,
    platform: str,
) -> str:
    if platform == "twitter":
        template = settings.twitter_prompt_template
        knowledge_block = settings.twitter_knowledge_block
        community_rules = "N/A (Twitter/X reply context)"
    else:
        template = settings.reddit_prompt_template
        knowledge_block = settings.reddit_knowledge_block
        community_rules = subreddit_rules or "No rules loaded."

    # Keep platform prompt instructions editable, but always inject immutable context.
    context_block = _immutable_context_block(
        opportunity=opportunity,
        community_rules=community_rules,
        knowledge_block=knowledge_block,
    )
    base = (template or "").strip()
    if not base:
        raise DraftGenerationError(f"empty prompt template for platform={platform}")
    return f"{base}\n\n{context_block}".strip()


def draft_comments(
    settings: Settings,
    opportunity: Opportunity,
    subreddit_rules: str,
    platform: str,
) -> List[str]:
    if not settings.google_api_key:
        raise DraftGenerationError("GOOGLE_API_KEY is missing.")

    client = genai.Client(api_key=settings.google_api_key)
    prompt = _render_prompt(
        settings=settings,
        opportunity=opportunity,
        subreddit_rules=subreddit_rules,
        platform=platform,
    )

    response = None
    last_error = None
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=settings.google_model,
                contents=prompt,
            )
            break
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(0.6)

    if response is None:
        raise DraftGenerationError(
            f"generation failed for {opportunity.thing_id} "
            f"(model={settings.google_model}, platform={platform}): {last_error}"
        )

    text = (response.text or "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    drafts = [
        line.split(". ", 1)[-1].strip()
        for line in lines
        if line and line[0].isdigit()
    ]
    if not drafts:
        raise DraftGenerationError(
            f"empty or unparsable model output for {opportunity.thing_id} "
            f"(model={settings.google_model}, platform={platform})"
        )
    return drafts[:3]
