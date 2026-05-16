from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

from google import genai

from src.reddit_client import RedditPost


@dataclass(frozen=True)
class RedditRelevanceDecision:
    thing_id: str
    relevant: bool
    score: int
    reason: str
    matched_product_area: str


def _extract_json_object(text: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty model response text")
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))

    if not isinstance(parsed, dict):
        raise ValueError("relevance response was not a JSON object")
    return parsed


class RedditRelevanceJudge:
    def __init__(self, api_key: str, model: str, min_score: int = 70, timeout_seconds: int = 25) -> None:
        del timeout_seconds
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self.min_score = min_score

    def judge_batch(
        self,
        posts: list[RedditPost],
        knowledge_block: str,
        prompt_template: str,
    ) -> dict[str, RedditRelevanceDecision]:
        decisions: dict[str, RedditRelevanceDecision] = {}
        for post in posts:
            decision = self.judge_one(post, knowledge_block, prompt_template)
            decisions[post.thing_id] = decision
        return decisions

    def judge_one(
        self,
        post: RedditPost,
        knowledge_block: str,
        prompt_template: str,
    ) -> RedditRelevanceDecision:
        del prompt_template
        body = (post.body or "").replace("\n", " ").strip()
        prompt = f"""
You are a practical lead-quality judge for a Reddit reply opportunity.

Company/product knowledge:
{knowledge_block[:6000]}

Reddit post:
Subreddit: r/{post.subreddit}
Title: {post.title[:300]}
Body: {body[:1600]}

Decide whether this Reddit post is a good opportunity to write a helpful reply for the configured business.

Accept only when BOTH are true:
1. The post matches the target audience, problem space, or use case described in the company/product knowledge.
2. A reply can naturally help the author and optionally mention a relevant configured capability without sounding forced or promotional.

Reject generic chatter, self-promotion, unrelated news/entertainment, broad discussion with no specific problem, job posts, memes, and posts where the configured business would feel random.

Scoring rubric:
- 90-100: explicit request, buying/search intent, or strong pain directly solved by a configured capability.
- 80-89: clear problem or workflow need in a served audience.
- 70-79: plausible but weaker fit where useful advice is still natural.
- 50-69: relevant topic but vague or hard to answer without forcing the product.
- 1-49: broad topic mention, casual chatter, or weak fit.
- 0: spam, promo, or unrelated.

Return ONLY valid JSON in this shape:
{{
  "relevant": boolean,
  "score": integer_from_0_to_100,
  "reason": "short reason",
  "matched_product_area": "specific configured capability or none"
}}
""".strip()

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                )
                text = response.text or ""
                if not text.strip():
                    raise RuntimeError("Gemini relevance returned empty text")
                data = _extract_json_object(text)
                score = max(0, min(100, int(data.get("score", 0) or 0)))
                raw_relevant = bool(data.get("relevant"))
                if raw_relevant and score < self.min_score:
                    score = self.min_score
                relevant = raw_relevant and score >= self.min_score
                return RedditRelevanceDecision(
                    thing_id=post.thing_id,
                    relevant=relevant,
                    score=score,
                    reason=str(data.get("reason", "")).strip()[:240] or "No reason returned",
                    matched_product_area=str(data.get("matched_product_area", "")).strip()[:120] or "none",
                )
            except Exception as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(0.6)

        raise RuntimeError(f"Gemini SDK relevance failed: {last_error}")

    def judge_with_split_retry(
        self,
        posts: list[RedditPost],
        knowledge_block: str,
        prompt_template: str,
    ) -> dict[str, RedditRelevanceDecision]:
        decisions: dict[str, RedditRelevanceDecision] = {}
        for post in posts:
            decisions[post.thing_id] = self.judge_one(post, knowledge_block, prompt_template)
        return decisions
