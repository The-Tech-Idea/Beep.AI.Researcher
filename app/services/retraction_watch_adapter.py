"""Phase 2 Retraction Watch Adapter — checks DOIs against the Crossref
Retraction Watch API to identify retracted publications.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

_RETRACTION_API = "https://api.labs.crossref.org/data/retractionwatch/v1"
_RETRACTION_SEARCH = "https://api.crossref.org/works"


class RetractionWatchAdapter:
    """Adapter for the Crossref Retraction Watch API."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def check_doi(self, doi: str) -> dict[str, Any] | None:
        """Check if a single DOI has been retracted.

        Returns None if not retracted, or a dict with:
        {doi, reason, retraction_date, source_url}
        """
        if not doi:
            return None

        try:
            resp = requests.get(
                _RETRACTION_SEARCH,
                params={"doi": doi, "select": "link,relation"},
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                return None

            data = resp.json().get("message", {})
            return self._parse_retraction(doi, data)

        except requests.RequestException as exc:
            logger.warning("RetractionWatchAdapter: API error for DOI %s: %s", doi, exc)
            return None

    def check_dois(self, dois: list[str]) -> list[dict[str, Any]]:
        """Check multiple DOIs for retractions. Returns list of retracted records."""
        results = []
        for doi in dois:
            record = self.check_doi(doi)
            if record:
                results.append(record)
        return results

    @staticmethod
    def _parse_retraction(doi: str, data: dict) -> dict[str, Any] | None:
        """Parse Crossref response for retraction indicators."""
        links = data.get("link", [])
        relations = data.get("relation", {})

        # Check for retraction relation
        for rel_type, rel_list in relations.items():
            if "is-retracted-by" in rel_type or "retraction" in rel_type.lower():
                for rel in rel_list:
                    return {
                        "doi": doi,
                        "reason": rel.get("id", "Retracted"),
                        "retraction_date": None,
                        "source_url": rel.get("id", ""),
                    }

        # Check links for retraction notices
        for link in links:
            content_type = link.get("content-type", "")
            if (
                "retraction" in content_type.lower()
                or "correction" in content_type.lower()
            ):
                return {
                    "doi": doi,
                    "reason": link.get("content-type", "Retraction notice"),
                    "retraction_date": None,
                    "source_url": link.get("URL", ""),
                }

        return None
