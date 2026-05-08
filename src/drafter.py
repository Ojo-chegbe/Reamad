from __future__ import annotations

import time
from typing import List

from google import genai

from src.config import Settings
from src.models import Opportunity


class DraftGenerationError(RuntimeError):
    pass


def _extract_drafts(text: str) -> List[str]:
    drafts: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        cleaned = line
        if len(cleaned) > 2 and cleaned[0].isdigit() and cleaned[1] in (".", ")", ":"):
            cleaned = cleaned[2:].strip()
        elif cleaned.startswith(("-", "*")):
            cleaned = cleaned[1:].strip()

        if cleaned:
            drafts.append(cleaned)

    deduped: List[str] = []
    seen = set()
    for draft in drafts:
        key = draft.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(draft)
    return deduped


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
    base = ""
    output_contract = (
        "Output contract:\n"
        "- Return exactly 3 drafts.\n"
        "- Use numbered lines in this exact format: 1. ..., 2. ..., 3. ...\n"
        "- Each draft must be tailored to the specific post context provided.\n"
        "- No extra headers or notes."
    )

    if platform == "twitter":
        base = (settings.twitter_prompt_template or "").strip()
        knowledge_block = (settings.twitter_knowledge_block or "").strip()
        if not base:
            raise DraftGenerationError(f"empty prompt template for platform={platform}")
        if not knowledge_block:
            raise DraftGenerationError(f"empty knowledge block for platform={platform}")
        tweet_context = (
            f"Tweet text context:\n"
            f"Title: {opportunity.title}\n"
            f"Body: {(opportunity.body or '')[:2000]}\n"
            f"Age in minutes: {opportunity.age_minutes}"
        )
        twitter_marketing_context = (
            "Twitter-specific marketing posture:\n"
            "- Twitter/X is more tolerant of direct product mentions than Reddit.\n"
            "- If the tweet is a clear fit for SoloaAI, at least 2 of the 3 drafts should mention SoloaAI or a specific SoloaAI capability naturally.\n"
            "- The reply can be a marketing reply, not only a problem-solving answer, but it must still feel like a normal human in-thread response.\n"
            "- Match the exact opportunity: creator content, ecommerce assets, product photos, UGC ads, Shorts repurposing, YouTube growth, music, voice, audio, scheduling, or AI text cleanup.\n"
            "- Do not use hard CTAs like buy now, sign up, or DM me."
        )
        return f"{base}\n\n{twitter_marketing_context}\n\n{knowledge_block}\n\n{tweet_context}\n\n{output_contract}".strip()
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
    return f"{base}\n\n{context_block}\n\n{output_contract}".strip()


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

    def _generate(prompt_text: str) -> str:
        response = None
        last_error = None
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=settings.google_model,
                    contents=prompt_text,
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
        return (response.text or "").strip()

    initial_text = _generate(prompt)
    drafts = _extract_drafts(initial_text)[:3]

    if len(drafts) < 3:
        missing = 3 - len(drafts)
        repair_prompt = (
            f"{prompt}\n\n"
            "Your previous output did not satisfy the output contract.\n"
            f"Already accepted drafts: {drafts}\n"
            f"Generate exactly {missing} additional drafts that are distinct from those accepted drafts.\n"
            "Return only numbered lines."
        )
        repair_text = _generate(repair_prompt)
        drafts.extend(_extract_drafts(repair_text))
        drafts = _extract_drafts("\n".join(drafts))[:3]

    if len(drafts) < 3:
        raise DraftGenerationError(
            f"could not produce 3 drafts for {opportunity.thing_id} "
            f"(model={settings.google_model}, platform={platform})"
        )
    return drafts
