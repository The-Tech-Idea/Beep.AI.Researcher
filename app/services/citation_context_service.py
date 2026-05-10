"""Phase 6 Citation Context Service — fetches and stores how a reference
is cited in other papers (citation intent analysis).
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any

import requests

from app.core.time_utils import utcnow_naive
from app.database import db

logger = logging.getLogger(__name__)

_SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"
_INTENT_TO_POLARITY = {
    "background": "mentioning",
    "methodology": "mentioning",
    "result": "supporting",
    "comparison": "contradicting",
}


class CitationContextRecord(db.Model):
    """Stored citation context: how one paper cites another."""

    __tablename__ = "citation_context_records"

    id = db.Column(db.Integer, primary_key=True)
    citing_doi = db.Column(db.String(255), nullable=False, index=True)
    cited_doi = db.Column(db.String(255), nullable=False, index=True)
    snippet = db.Column(db.Text)
    intent = db.Column(db.String(50))
    polarity = db.Column(db.String(20), default="mentioning")
    polarity_score = db.Column(db.Float)
    source = db.Column(db.String(50), default="semantic_scholar")
    fetched_at = db.Column(db.DateTime, default=utcnow_naive)

    __table_args__ = (
        db.UniqueConstraint("citing_doi", "cited_doi", name="uq_citation_context"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "citing_doi": self.citing_doi,
            "cited_doi": self.cited_doi,
            "snippet": self.snippet,
            "intent": self.intent,
            "polarity": self.polarity,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
        }


class CitationContextService:
    """Fetch and manage citation context from Semantic Scholar API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
        self._session = requests.Session()
        if api_key:
            self._session.headers["x-api-key"] = api_key

    def fetch_contexts(
        self, doi: str, *, limit: int = 50
    ) -> list[CitationContextRecord]:
        """Fetch citation contexts for a DOI from Semantic Scholar.

        Returns list of CitationContextRecord (new or existing).
        """
        # Check cache freshness
        one_week_ago = utcnow_naive() - timedelta(days=7)
        existing = CitationContextRecord.query.filter_by(cited_doi=doi).all()
        if existing and existing[0].fetched_at > one_week_ago:
            return existing

        try:
            resp = self._session.get(
                f"{_SEMANTIC_SCHOLAR_API}/paper/DOI:{doi}/citations",
                params={
                    "fields": "title,authors,abstract,contexts,intents",
                    "limit": limit,
                },
                timeout=30,
            )
            if resp.status_code != 200:
                logger.warning(
                    "CitationContextService: API error for DOI %s: %d",
                    doi,
                    resp.status_code,
                )
                return existing

            data = resp.json().get("data", [])
        except requests.RequestException as exc:
            logger.warning("CitationContextService: network error: %s", exc)
            return existing

        records = []
        for item in data:
            contexts = item.get("contexts") or []
            intents = item.get("intents") or []
            citing_doi = item.get("externalIds", {}).get("DOI", "")

            for ctx in contexts:
                intent = intents[0] if intents else "unknown"
                polarity = _INTENT_TO_POLARITY.get(intent.lower(), "mentioning")

                record = CitationContextRecord.query.filter_by(
                    citing_doi=citing_doi, cited_doi=doi
                ).first()

                if record:
                    record.snippet = ctx
                    record.intent = intent
                    record.polarity = polarity
                    record.fetched_at = utcnow_naive()
                else:
                    record = CitationContextRecord(
                        citing_doi=citing_doi,
                        cited_doi=doi,
                        snippet=ctx,
                        intent=intent,
                        polarity=polarity,
                    )
                    db.session.add(record)

                records.append(record)

        db.session.commit()
        return records

    def get_contexts_for_doi(self, doi: str) -> list[dict]:
        """Return cached citation contexts for a DOI."""
        records = CitationContextRecord.query.filter_by(cited_doi=doi).all()
        return [r.to_dict() for r in records]

    def get_polarity_summary(self, doi: str) -> dict[str, int]:
        """Get polarity counts for a DOI."""
        records = CitationContextRecord.query.filter_by(cited_doi=doi).all()
        summary = {"supporting": 0, "contradicting": 0, "mentioning": 0}
        for r in records:
            summary[r.polarity] = summary.get(r.polarity, 0) + 1
        return summary
