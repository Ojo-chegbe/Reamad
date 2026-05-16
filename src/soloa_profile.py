import json
import os
from pathlib import Path
from textwrap import dedent

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PROFILE_PATH = _PROJECT_ROOT / "bot_profile.json"

DEFAULT_PAIN_SUBREDDITS: list[str] = []

DEFAULT_PAIN_KEYWORDS: list[str] = []

DEFAULT_TWITTER_TARGET_HANDLES: list[str] = []
DEFAULT_TWITTER_QUERIES: list[str] = []
DEFAULT_YOUTUBE_TARGET_CHANNELS: list[str] = []
DEFAULT_YOUTUBE_QUERIES: list[str] = []
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
    Campaign/product knowledge:
    - Describe what this business sells or offers.
    - Describe the target audience and the problems they are likely trying to solve.
    - List the specific services, features, products, or workflows that are relevant to social replies.
    - Include common alternatives, competitors, objections, and buying triggers if known.
    - Preferred positioning: provide practical help first, then mention the business only when it fits naturally.
    - Do not lead with hard self-promotion.
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
    - Mention the configured business in at most one draft, and only naturally when it directly fits the post
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

DEFAULT_YOUTUBE_PROMPT_TEMPLATE = dedent(
    """
    You are writing YouTube comment reply drafts for manual review.
    Goal: reply like a normal helpful person under a YouTube video, not like a brand account.
    Write exactly 3 short reply drafts.
    Constraints:
    - Keep each reply under 80 words
    - No hard CTA like "buy now", "sign up", "DM me", or "check us out"
    - No hashtags
    - Useful first, product mention optional in at most one draft
    - If the configured business is relevant, mention the specific workflow it helps with, not a feature dump
    - Sound conversational and specific to the comment/video context
    Output as plain text with numbered lines 1..3.
    """
).strip()


def normalize_profile(profile: dict) -> dict:
    legacy_keywords = profile.get("keywords", DEFAULT_PAIN_KEYWORDS)
    legacy_knowledge = profile.get("knowledge_block", DEFAULT_SOLOA_KNOWLEDGE_BLOCK)
    return {
        "campaign_name": profile.get("campaign_name", "New marketing campaign"),
        "target_audience": profile.get("target_audience", ""),
        "product_area": profile.get("product_area", ""),
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
        "youtube_knowledge_block": profile.get("youtube_knowledge_block", legacy_knowledge),
        "youtube_prompt_template": profile.get("youtube_prompt_template", DEFAULT_YOUTUBE_PROMPT_TEMPLATE),
        "twitter_target_handles": profile.get("twitter_target_handles", DEFAULT_TWITTER_TARGET_HANDLES),
        "twitter_queries": profile.get("twitter_queries", DEFAULT_TWITTER_QUERIES),
        "youtube_target_channels": profile.get("youtube_target_channels", DEFAULT_YOUTUBE_TARGET_CHANNELS),
        "youtube_queries": profile.get("youtube_queries", DEFAULT_YOUTUBE_QUERIES),
        "youtube_keywords": profile.get("youtube_keywords", legacy_keywords),
    }


def default_profile() -> dict:
    return normalize_profile({})


def get_profile(account_id: str | None = None) -> dict:
    active_account_id = account_id or os.getenv("SOLOA_ACCOUNT_ID", "").strip()
    if active_account_id:
        try:
            from ui.state import get_account_profile

            return get_account_profile(active_account_id)
        except Exception:
            pass

    if _PROFILE_PATH.exists():
        try:
            with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    return normalize_profile(loaded)
        except Exception:
            pass
    return default_profile()

def save_profile(data: dict, account_id: str | None = None):
    active_account_id = account_id or os.getenv("SOLOA_ACCOUNT_ID", "").strip()
    if active_account_id:
        from ui.state import save_account_profile

        save_account_profile(active_account_id, data)
        return
    with open(_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(normalize_profile(data), f, indent=2)

def get_knowledge_block() -> str:
    return get_profile().get("reddit_knowledge_block", DEFAULT_SOLOA_KNOWLEDGE_BLOCK)
