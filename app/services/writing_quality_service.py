"""Phase 4 Writing Quality Service — LLM-based structured scoring with offset-mapped issues."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services import beep_ai_client

logger = logging.getLogger(__name__)

_ANALYSE_SYSTEM_PROMPT = (
    "You are an expert academic writing reviewer. Analyse the given manuscript section "
    "and return a structured JSON object with writing quality feedback. "
    "Return ONLY valid JSON — no markdown fences, no explanation.\n\n"
    "The JSON must match this schema:\n"
    "{\n"
    '  "overall_score": 0.0-100.0,\n'
    '  "tone_score": 0.0-100.0,\n'
    '  "clarity_score": 0.0-100.0,\n'
    '  "grammar_score": 0.0-100.0,\n'
    '  "issues": [\n'
    '    {"type": "tone"|"clarity"|"grammar"|"passive_voice"|"hedge"|"wordy",\n'
    '     "severity": "info"|"warning"|"error",\n'
    '     "text": "the exact substring from the original text",\n'
    '     "suggestion": "how to fix it",\n'
    '     "offset": 0-based character position in the original text,\n'
    '     "length": number of characters in the flagged text}\n'
    "  ],\n"
    '  "suggestions": ["general improvement suggestions"]\n'
    "}\n\n"
    "Rules:\n"
    "- overall_score should reflect academic writing quality (100 = publication-ready)\n"
    "- Flag passive voice overuse, hedging language, wordy constructions, unclear references\n"
    "- Only flag real issues; don't be overly pedantic\n"
    "- Each issue's offset and length MUST correspond to actual positions in the input text\n"
    "- If the text is already excellent, return an empty issues array and high scores"
)


class WritingQualityService:
    """Score a manuscript section and return offset-mapped writing issues."""

    def __init__(self, ai_client=None):
        self.ai_client = ai_client or beep_ai_client

    def analyse(self, text: str, section_id: int | None = None) -> dict[str, Any]:
        """Return structured writing feedback for the given text."""
        if not text or not text.strip():
            return {"error": "No text to analyse"}, 400
        if len(text) > 10000:
            return {
                "error": "Section too long for analysis (max 10,000 characters). Try a shorter selection."
            }, 400

        if not self.ai_client.is_configured():
            return {
                "overall_score": None,
                "tone_score": None,
                "clarity_score": None,
                "grammar_score": None,
                "issues": [],
                "suggestions": [],
                "note": "Writing quality service unavailable — Beep.AI.Server not configured.",
            }, 503

        messages = [
            {"role": "system", "content": _ANALYSE_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ]

        ok, raw_text = self.ai_client.chat_reply(messages, temperature=0.3)
        if not ok:
            logger.warning("WritingQualityService: LLM call failed: %s", raw_text)
            return {
                "error": "Analysis failed — could not reach the writing model."
            }, 502

        parsed = self._parse_response(raw_text)
        if parsed is None:
            logger.warning("WritingQualityService: could not parse LLM response")
            return {"error": "Analysis returned an unexpected format."}, 502

        result = {
            "overall_score": round(parsed.get("overall_score", 0), 1),
            "tone_score": round(parsed.get("tone_score", 0), 1),
            "clarity_score": round(parsed.get("clarity_score", 0), 1),
            "grammar_score": round(parsed.get("grammar_score", 0), 1),
            "issues": self._validate_issues(parsed.get("issues", []), text),
            "suggestions": parsed.get("suggestions", []),
        }

        return result, 200

    def apply_fix(self, text: str, issue: dict[str, Any]) -> str | None:
        """Patch a single issue in the text at the given offset."""
        offset = issue.get("offset")
        length = issue.get("length")
        suggestion = issue.get("suggestion", "")

        if offset is None or length is None or not suggestion:
            return None

        try:
            offset = int(offset)
            length = int(length)
        except (TypeError, ValueError):
            return None

        if offset < 0 or offset + length > len(text):
            return None

        before = text[:offset]
        after = text[offset + length :]
        return before + suggestion + after

    @staticmethod
    def _parse_response(raw: str) -> dict | None:
        """Extract JSON from the LLM response, tolerating markdown fences."""
        cleaned = raw.strip()
        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            pass

        # Try to find JSON object within the response
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except (json.JSONDecodeError, ValueError):
                pass

        return None

    @staticmethod
    def _validate_issues(issues: list[dict], text: str) -> list[dict]:
        """Ensure each issue has valid offset/length within the text."""
        valid = []
        valid_types = {"tone", "clarity", "grammar", "passive_voice", "hedge", "wordy"}
        valid_severities = {"info", "warning", "error"}

        for issue in issues:
            if not isinstance(issue, dict):
                continue

            issue_type = issue.get("type", "info")
            if issue_type not in valid_types:
                issue_type = "info"

            severity = issue.get("severity", "info")
            if severity not in valid_severities:
                severity = "info"

            try:
                offset = int(issue.get("offset", 0))
                length = int(issue.get("length", 0))
            except (TypeError, ValueError):
                continue

            if offset < 0 or offset + length > len(text):
                continue

            valid.append(
                {
                    "type": issue_type,
                    "severity": severity,
                    "text": text[offset : offset + length],
                    "suggestion": issue.get("suggestion", ""),
                    "offset": offset,
                    "length": length,
                }
            )

        return valid
