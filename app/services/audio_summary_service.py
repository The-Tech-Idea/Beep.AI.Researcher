"""Document audio-summary generation for Phase 1 AI discovery."""
from __future__ import annotations

import base64
import re

from app.database import db
from app.models.researcher import FeedRecommendation, ResearcherDocument
from app.services import beep_ai_client
from app.services.ai_discovery_utils import collapse_whitespace


FINDING_PATTERN = re.compile(r"\b(find(?:ing|ings)?|result(?:s)?|conclu(?:de|des|ded|sion|sions)|suggest(?:s|ed|ing)?|demonstrat(?:e|es|ed|ing)|show(?:s|ed|ing)?)\b", re.IGNORECASE)


class AudioSummaryService:
    """Extract concise listen-mode summaries and delegate TTS to Beep.AI.Server."""

    def __init__(self, ai_client_module=beep_ai_client):
        self.ai_client = ai_client_module

    def build_summary_text(self, document_id: int, *, max_findings: int = 3, max_chars: int = 2400) -> str:
        document = db.session.get(ResearcherDocument, document_id)
        if document is None:
            raise LookupError("Document not found")
        if not document.text_content:
            raise ValueError("Document has no extracted text")

        paragraphs = [collapse_whitespace(chunk) for chunk in re.split(r"\n\s*\n", document.text_content) if collapse_whitespace(chunk)]
        if not paragraphs:
            raise ValueError("Document has no readable text")

        abstract = paragraphs[0]
        finding_sentences = []
        for paragraph in paragraphs[1:] or paragraphs[:1]:
            for sentence in self._split_sentences(paragraph):
                if FINDING_PATTERN.search(sentence):
                    finding_sentences.append(sentence)
                if len(finding_sentences) >= max_findings:
                    break
            if len(finding_sentences) >= max_findings:
                break

        if not finding_sentences:
            finding_sentences = self._split_sentences(" ".join(paragraphs[1:3]))[:max_findings]

        sections = [f"Abstract: {abstract}"]
        if finding_sentences:
            sections.append("Key findings:")
            sections.extend(f"- {sentence}" for sentence in finding_sentences if sentence)

        summary = "\n".join(section for section in sections if section).strip()
        return summary[:max_chars]

    def build_recommendation_summary_text(
        self,
        recommendation_id: int,
        user_id: int,
        *,
        max_chars: int = 1800,
    ) -> str:
        recommendation = FeedRecommendation.query.filter_by(
            id=recommendation_id,
            user_id=user_id,
        ).first()
        if recommendation is None:
            raise LookupError("Recommendation not found")

        title = collapse_whitespace(recommendation.title)
        if not title:
            raise ValueError("Recommendation has no readable title")

        authors = [
            collapse_whitespace(author)
            for author in (recommendation.authors or [])
            if collapse_whitespace(author)
        ]
        author_text = ", ".join(authors[:4])
        if len(authors) > 4:
            author_text = f"{author_text}, and others"

        sections = [f"Recommended paper: {title}"]
        if author_text:
            sections.append(f"Authors: {author_text}")
        if recommendation.reason:
            sections.append(f"Why it matches: {collapse_whitespace(recommendation.reason)}")
        if recommendation.abstract:
            sections.append(f"Abstract: {collapse_whitespace(recommendation.abstract)}")
        if recommendation.source:
            sections.append(f"Source: {collapse_whitespace(recommendation.source)}")

        summary = "\n".join(section for section in sections if section).strip()
        return summary[:max_chars]

    def generate_audio_summary(self, document_id: int, *, voice: str | None = None, speed: float | None = None) -> dict:
        summary_text = self.build_summary_text(document_id)
        kwargs = {}
        if speed is not None:
            kwargs["speed"] = speed
        ok, payload = self.ai_client.synthesize_speech(summary_text, voice=voice, **kwargs)
        if not ok:
            raise RuntimeError(payload or "Failed to synthesize speech")

        result = dict(payload) if isinstance(payload, dict) else {"audio": payload}
        result["summary_text"] = summary_text
        return result

    def generate_recommendation_audio_summary(
        self,
        recommendation_id: int,
        user_id: int,
        *,
        voice: str | None = None,
        speed: float | None = None,
    ) -> dict:
        summary_text = self.build_recommendation_summary_text(recommendation_id, user_id)
        kwargs = {}
        if speed is not None:
            kwargs["speed"] = speed
        ok, payload = self.ai_client.synthesize_speech(summary_text, voice=voice, **kwargs)
        if not ok:
            raise RuntimeError(payload or "Failed to synthesize speech")

        result = dict(payload) if isinstance(payload, dict) else {"audio": payload}
        result["summary_text"] = summary_text
        return result

    @staticmethod
    def extract_audio_bytes(payload) -> bytes:
        if isinstance(payload, (bytes, bytearray)):
            return bytes(payload)
        if not isinstance(payload, dict):
            return b""

        for key in ("audio", "audio_content"):
            audio_value = payload.get(key)
            if isinstance(audio_value, (bytes, bytearray)):
                return bytes(audio_value)
            if isinstance(audio_value, str):
                try:
                    return base64.b64decode(audio_value, validate=True)
                except Exception:
                    return audio_value.encode("utf-8")

        audio_base64 = payload.get("audio_base64")
        if isinstance(audio_base64, str):
            try:
                return base64.b64decode(audio_base64, validate=True)
            except Exception:
                return b""

        return b""

    def _split_sentences(self, text: str) -> list[str]:
        return [collapse_whitespace(part) for part in re.split(r"(?<=[.!?])\s+", text or "") if collapse_whitespace(part)]