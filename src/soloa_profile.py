from __future__ import annotations

from textwrap import dedent


DEFAULT_PAIN_SUBREDDITS: list[str] = [
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


DEFAULT_PAIN_KEYWORDS: list[str] = [
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


SOLOA_KNOWLEDGE_BLOCK = dedent(
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
