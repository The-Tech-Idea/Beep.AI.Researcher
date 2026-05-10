"""Phase 2 Polarity Classifier — classifies evidence snippets as
supporting, contradicting, or mentioning.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from app.services import beep_ai_client

logger = logging.getLogger(__name__)

_CLASSIFY_PROMPT = (
    "You are an evidence classifier. For each evidence snippet below, determine "
    "whether it SUPPORTS, CONTRADICTS, or merely MENTIONS the given research question.\n\n"
    "Return ONLY valid JSON — no markdown fences.\n"
    'Schema: {"classifications": [{"snippet_index": 0, "polarity": "supporting", '
    '"confidence": 0.85, "reason": "brief reason"}]}\n\n'
    'Polarity values: "supporting", "contradicting", "mentioning".\n'
    "The snippet_index corresponds to the position in the snippets list."
)

_CACHE: dict[str, dict[str, Any]] = {}


class PolarityClassifier:
    """Classify evidence snippets by their stance on a research question."""

    def __init__(self, ai_client=None):
        self.ai_client = ai_client or beep_ai_client

    def classify_batch(
        self,
        question: str,
        snippets: list[str],
        *,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        """Classify a batch of snippets in a single LLM call.

        Returns list of {snippet_index, polarity, confidence, reason}.
        """
        if not snippets:
            return []

        cache_key = self._cache_key(question, snippets)
        if use_cache and cache_key in _CACHE:
            return _CACHE[cache_key]

        if not self.ai_client.is_configured():
            return self._heuristic_classify(question, snippets)

        snippet_list = "\n".join(f"[{i}] {s[:500]}" for i, s in enumerate(snippets))
        user_content = f"Question: {question}\n\nSnippets:\n{snippet_list}"

        messages = [
            {"role": "system", "content": _CLASSIFY_PROMPT},
            {"role": "user", "content": user_content},
        ]

        ok, raw = self.ai_client.chat_reply(messages, temperature=0.2)
        if not ok:
            logger.warning("PolarityClassifier: LLM call failed: %s", raw)
            return self._heuristic_classify(question, snippets)

        result = self._parse_response(raw, len(snippets))
        if result and use_cache:
            _CACHE[cache_key] = result

        return result or self._heuristic_classify(question, snippets)

    @staticmethod
    def _parse_response(raw: str, expected_count: int) -> list[dict] | None:
        """Parse LLM JSON response."""
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(l for l in lines if not l.strip().startswith("```"))

        try:
            data = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start >= 0 and end > start:
                try:
                    data = json.loads(cleaned[start : end + 1])
                except (json.JSONDecodeError, ValueError):
                    return None
            else:
                return None

        classifications = data.get("classifications", [])
        if not classifications:
            return None

        valid_polarities = {"supporting", "contradicting", "mentioning"}
        result = []
        for c in classifications:
            idx = c.get("snippet_index")
            polarity = c.get("polarity", "mentioning").lower()
            if polarity not in valid_polarities:
                polarity = "mentioning"
            result.append(
                {
                    "snippet_index": idx if idx is not None else 0,
                    "polarity": polarity,
                    "confidence": float(c.get("confidence", 0.5)),
                    "reason": c.get("reason", ""),
                }
            )

        return result

    @staticmethod
    def _heuristic_classify(question: str, snippets: list[str]) -> list[dict]:
        """Fallback heuristic: mark all as 'mentioning'."""
        return [
            {
                "snippet_index": i,
                "polarity": "mentioning",
                "confidence": 0.0,
                "reason": "Heuristic fallback — no AI available.",
            }
            for i in range(len(snippets))
        ]

    @staticmethod
    def _cache_key(question: str, snippets: list[str]) -> str:
        """Generate a cache key from question + snippets."""
        hasher = hashlib.md5()
        hasher.update(question.encode("utf-8"))
        for s in snippets:
            hasher.update(s[:200].encode("utf-8"))
        return hasher.hexdigest()
