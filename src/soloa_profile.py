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

def get_profile() -> dict:
    if _PROFILE_PATH.exists():
        try:
            with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "subreddits": DEFAULT_PAIN_SUBREDDITS,
        "keywords": DEFAULT_PAIN_KEYWORDS,
        "knowledge_block": DEFAULT_SOLOA_KNOWLEDGE_BLOCK,
    }

def save_profile(data: dict):
    with open(_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def get_knowledge_block() -> str:
    return get_profile().get("knowledge_block", DEFAULT_SOLOA_KNOWLEDGE_BLOCK)
