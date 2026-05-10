"""Phase 4 Auto Extraction Service — schema-free summary, findings, and data table extraction."""

from __future__ import annotations

import logging

from app.core.time_utils import utcnow_naive
from app.database import db
from app.services import beep_ai_client

logger = logging.getLogger(__name__)

_SUMMARY_PROMPT = (
    "You are a research assistant. Read the following document text and return a JSON object with:\n"
    "{\n"
    '  "summary": "2-3 paragraph summary of the document",\n'
    '  "key_findings": ["finding 1", "finding 2", ...]\n'
    "}\n"
    "Return ONLY valid JSON. No markdown fences."
)

_TABLE_PROMPT = (
    "You are a data extraction assistant. Identify all numeric data tables in the following text. "
    "Return a JSON array of tables, where each table is:\n"
    "{\n"
    '  "title": "brief description of the table",\n'
    '  "headers": ["col1", "col2"],\n'
    '  "rows": [["val1", "val2"], ...]\n'
    "}\n"
    "If no tables found, return []. Return ONLY valid JSON."
)


class AutoExtractionCache(db.Model):
    """Cached auto-extraction results per document."""

    __tablename__ = "auto_extraction_cache"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, unique=True, nullable=False)
    document_hash = db.Column(db.String(64), nullable=False)
    summary_text = db.Column(db.Text, nullable=True)
    findings_json = db.Column(db.JSON, nullable=True)
    tables_json = db.Column(db.JSON, nullable=True)
    extracted_at = db.Column(db.DateTime, nullable=True, default=utcnow_naive)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "summary": self.summary_text,
            "findings": self.findings_json or [],
            "tables": self.tables_json or [],
            "extracted_at": self.extracted_at.isoformat()
            if self.extracted_at
            else None,
        }


class AutoExtractionService:
    """Schema-free extraction: summary, key findings, data tables per document."""

    def __init__(self, ai_client=None, cache_repo=None):
        self.ai_client = ai_client or beep_ai_client
        self._cache_repo = cache_repo

    @property
    def _repo(self):
        if self._cache_repo is None:
            from app.repositories.auto_extraction_cache_repository import (
                AutoExtractionCacheRepository,
            )

            self._cache_repo = AutoExtractionCacheRepository()
        return self._cache_repo

    def extract(
        self, document_id: int, text: str, *, use_cache: bool = True
    ) -> tuple[dict, int]:
        """Extract summary, findings, and tables. Returns (result_dict, status_code)."""
        if not text or not text.strip():
            return {"error": "No text content to extract from"}, 400

        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        if use_cache:
            cached = self._repo.get_by_document(document_id)
            if cached and cached.document_hash == content_hash:
                return cached.to_dict(), 200

        if not self.ai_client.is_configured():
            return {"error": "AI server not configured for extraction"}, 503

        # Truncate text for API — use first 8000 chars
        truncated = text[:8000] if len(text) > 8000 else text

        summary_result = self._call_llm(_SUMMARY_PROMPT, truncated)
        if summary_result is None:
            return {"error": "Extraction failed — could not reach the model."}, 502

        tables_result = self._call_llm(_TABLE_PROMPT, truncated)
        if tables_result is None:
            tables_result = {"tables": []}

        findings = summary_result.get("key_findings", [])
        summary = summary_result.get("summary", "")

        # Upsert cache
        cache = self._repo.get_by_document(document_id)
        if cache:
            cache.document_hash = content_hash
            cache.summary_text = summary
            cache.findings_json = findings
            cache.tables_json = tables_result.get("tables", [])
            cache.extracted_at = utcnow_naive()
            self._repo.commit()
        else:
            cache = AutoExtractionCache(
                document_id=document_id,
                document_hash=content_hash,
                summary_text=summary,
                findings_json=findings,
                tables_json=tables_result.get("tables", []),
                extracted_at=utcnow_naive(),
            )
            self._repo.add(cache)
            self._repo.commit()

        return cache.to_dict(), 200

    def _call_llm(self, system_prompt: str, text: str) -> dict | None:
        """Make an LLM call and parse JSON response."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]

        ok, raw = self.ai_client.chat_reply(messages, temperature=0.2)
        if not ok:
            logger.warning("AutoExtractionService: LLM call failed: %s", raw)
            return None

        # Parse JSON, tolerating markdown fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(l for l in lines if not l.strip().startswith("```"))

        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(cleaned[start : end + 1])
                except (json.JSONDecodeError, ValueError):
                    pass
            return None
