from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

from google import genai


@dataclass(frozen=True)
class TwitterRelevanceDecision:
    relevant: bool
    score: int
    reason: str
    matched_product_area: str


def _extract_json_object(text: str) -> dict:
    raw = (text or "").strip()
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


class TwitterRelevanceJudge:
    def __init__(self, api_key: str, model: str, min_score: int = 75) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self.min_score = min_score

    def judge(self, tweet_text: str, knowledge_block: str, platform: str = "twitter") -> TwitterRelevanceDecision:
        if platform == "youtube":
            platform_label = "YouTube comment"
            source_label = "YouTube context and comment"
            marketing_note = "YouTube comments are public, slower, and more sensitive to spam. Accept only when a concise helpful reply can naturally address the commenter."
        elif platform == "reddit":
            platform_label = "Reddit thread reply"
            source_label = "Reddit post context"
            marketing_note = (
                "Reddit is highly anti-marketing. Accept only when there is a genuine problem-solving angle, "
                "and a product mention could be subtle and natural after useful advice."
            )
        else:
            platform_label = "X/Twitter reply"
            source_label = "Tweet"
            marketing_note = "X/Twitter is less anti-marketing than Reddit, so a clear marketing opportunity is enough."
        prompt = f"""
You are a practical lead-quality judge for {platform_label} and marketing opportunities.

Company/product knowledge:
{knowledge_block[:6000]}

{source_label}:
{tweet_text[:1800]}

Decide whether this content is a good opportunity to reply in a way that can naturally market the business described in the company/product knowledge.

Accept when BOTH are true:
1. The author, topic, or conversation matches the target audience, market, use case, or problem space described in the company/product knowledge.
2. There is a natural opening to mention, recommend, or demonstrate one relevant capability from the company/product knowledge without sounding random or forced. This can be a problem, request, workflow, plan, milestone, business discussion, product launch, or someone showing work that the configured business could improve or speed up.

{marketing_note}

Reject generic news, memes, politics, sports, entertainment, job posts, celebrity bait, pure engagement bait, and posts where a reply for this configured business would feel unrelated or forced. Also reject people only promoting their own unrelated product/event unless the configured business has a clear contextual angle.

Scoring rubric:
- 90-100: explicit request, buying/search intent, or strong workflow pain directly solved by a named configured capability.
- 80-89: clear marketing opening in a served audience, even if the author is not asking for help.
- 70-79: relevant audience/topic with a plausible but weaker product angle.
- 50-69: relevant topic but generic, vague, or hard to reply to without forcing the product.
- 1-49: broad topic mention, commentary, casual chatter, or weak fit.
- 0: spam, promo, news, entertainment, politics, celebrity bait, or unrelated.

Important consistency rule:
- If "relevant" is true, "score" must be {self.min_score} or higher.
- If "score" is below {self.min_score}, "relevant" must be false.

Return ONLY valid JSON in this shape:
{{
  "relevant": boolean,
  "score": integer_from_0_to_100,
  "reason": "short reason",
  "matched_product_area": "specific capability or none"
}}
""".strip()

        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                )
                data = _extract_json_object(response.text or "")
                score = int(data.get("score", 0))
                score = max(0, min(100, score))
                raw_relevant = bool(data.get("relevant"))
                if raw_relevant and score < self.min_score:
                    score = self.min_score
                relevant = raw_relevant and score >= self.min_score
                return TwitterRelevanceDecision(
                    relevant=relevant,
                    score=score,
                    reason=str(data.get("reason", "")).strip()[:240] or "No reason returned",
                    matched_product_area=str(data.get("matched_product_area", "")).strip()[:120] or "none",
                )
            except Exception as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(0.6)

        return TwitterRelevanceDecision(
            relevant=False,
            score=0,
            reason=f"Relevance judge failed: {last_error}",
            matched_product_area="none",
        )
