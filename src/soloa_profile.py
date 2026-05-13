import json
import os
from pathlib import Path
from textwrap import dedent

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PROFILE_PATH = _PROJECT_ROOT / "bot_profile.json"

DEFAULT_PAIN_SUBREDDITS = [
    "YouTubers",
    "digital_marketing",
    "productivity",
    "NewTubers",
    "VideoEditing",
    "ContentCreators",
    "podcasting",
    "marketing",
    "socialmedia",
    "Entrepreneur",
    "startups",
    "SaaS",
    "IndieHackers",
    "microsaas",
]

DEFAULT_PAIN_KEYWORDS = [
    "i'm tired of",
    "im tired of",
    "this is taking too long",
    "i cant keep up",
    "i can't keep up",
    "anyone else struggling with",
    "this workflow is killing me",
    "switching between tools",
    "too many tools",
    "overwhelmed with tools",
    "too many tabs",
    "content takes too long",
    "editing takes hours",
    "can't scale ad creatives",
]

DEFAULT_TWITTER_TARGET_HANDLES: list[str] = []
DEFAULT_TWITTER_QUERIES: list[str] = []
DEFAULT_BUYING_SIGNALS = [
    "looking for",
    "any tools for",
    "switching from",
    "too expensive",
    "how do i automate",
    "alternative to",
]
DEFAULT_FORBIDDEN_PHRASES = [
    "buy now",
    "sign up today",
    "limited time",
    "dm me",
]

DEFAULT_SOLOA_KNOWLEDGE_BLOCK = dedent(
    """
    Soloa.ai product knowledge:
    - Soloa AI is an all-in-one AI platform designed to replace fragmented AI stacks.
    - Core positioning: workflow consolidation over tool collection.
    - Core value: one dashboard, one subscription, multi-model access.
    - Multi-model chat includes GPT-family, Claude-family, Gemini-family, Grok-style options.
    - Image workflows: text-to-image, background removal, upscaling, restoration, batch edits.
    - Video workflows: script-to-video, text-to-video, lip-sync, upscaling, UGC ad generation.
    - Audio workflows: text-to-speech, voice cloning/changing, audio-to-video support.
    - Marketing workflows: YouTube titles/thumbnails/SEO, ad creatives, social content.
    - End-to-end creator pipeline: idea -> script -> image -> voice -> video.
    - Preferred Reddit positioning: "I solved this workflow problem by reducing tool-switching."
    - Do not lead with hard self-promo; provide practical help first.
    """
).strip()

DEFAULT_REDDIT_PROMPT_TEMPLATE = dedent(
    """
    You are writing Reddit comment drafts for manual review.
    Goal: Write exactly like a normal Reddit user. It must be very simple, casual, and conversational. Flow like a human wrote it off the cuff from their phone.
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
    """
).strip()

DEFAULT_TWITTER_PROMPT_TEMPLATE = dedent(
    """
    You are writing X/Twitter reply drafts for manual review.
    Goal: Write like a real X user replying naturally in-thread. Keep it concise, direct, and human.
    Platform context: X/Twitter public reply
    Write exactly 3 short reply drafts.
    Constraints:
    - No direct CTA like "buy now", "sign up", "DM me"
    - No hashtags unless absolutely necessary
    - No AI-speak or corporate tone
    - Keep each reply short enough for X and easy to post quickly
    - Useful first, subtle mention optional in at most one draft
    Output as plain text with numbered lines 1..3.
    """
).strip()


def get_profile() -> dict:
    def _normalize(profile: dict) -> dict:
        legacy_keywords = profile.get("keywords", DEFAULT_PAIN_KEYWORDS)
        legacy_knowledge = profile.get("knowledge_block", DEFAULT_SOLOA_KNOWLEDGE_BLOCK)
        return {
            "campaign_name": profile.get("campaign_name", "SoloaAI growth monitoring"),
            "target_audience": profile.get("target_audience", "creators, ecommerce sellers, marketers, founders, agencies"),
            "product_area": profile.get("product_area", "AI creative workflow consolidation"),
            "subreddits": profile.get("subreddits", DEFAULT_PAIN_SUBREDDITS),
            "reddit_keywords": profile.get("reddit_keywords", legacy_keywords),
            "twitter_keywords": profile.get("twitter_keywords", legacy_keywords),
            "competitors": profile.get("competitors", []),
            "buying_signals": profile.get("buying_signals", DEFAULT_BUYING_SIGNALS),
            "forbidden_phrases": profile.get("forbidden_phrases", DEFAULT_FORBIDDEN_PHRASES),
            "max_replies_per_community_per_day": profile.get("max_replies_per_community_per_day", 8),
            "disclosure_policy": profile.get(
                "disclosure_policy",
                "Be transparent when a relationship exists. Default to practical help before any product mention.",
            ),
            "reddit_knowledge_block": profile.get("reddit_knowledge_block", legacy_knowledge),
            "twitter_knowledge_block": profile.get("twitter_knowledge_block", legacy_knowledge),
            "reddit_prompt_template": profile.get("reddit_prompt_template", DEFAULT_REDDIT_PROMPT_TEMPLATE),
            "twitter_prompt_template": profile.get("twitter_prompt_template", DEFAULT_TWITTER_PROMPT_TEMPLATE),
            "twitter_target_handles": profile.get("twitter_target_handles", DEFAULT_TWITTER_TARGET_HANDLES),
            "twitter_queries": profile.get("twitter_queries", DEFAULT_TWITTER_QUERIES),
        }

    if _PROFILE_PATH.exists():
        try:
            with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    return _normalize(loaded)
        except Exception:
            pass
    return _normalize({})

def save_profile(data: dict):
    with open(_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_knowledge_block() -> str:
    return get_profile().get("reddit_knowledge_block", DEFAULT_SOLOA_KNOWLEDGE_BLOCK)
