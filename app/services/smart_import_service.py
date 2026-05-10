"""Phase 6 Smart Import Service — unified identifier resolver for importing
references by DOI, PMID, arXiv ID, or URL.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.database import db
from app.models.researcher import Reference

logger = logging.getLogger(__name__)

_DOI_RE = re.compile(r"^10\.\d{4,}/\S+$")
_PMID_RE = re.compile(r"^\d{4,}$")
_ARXIV_RE = re.compile(r"^(?:\d{4}\.\d{4,5}|[a-z\-]+/\d{7})v\d*$")


class SmartImportService:
    """Resolve and import references from any identifier type."""

    def __init__(self, search_manager=None, reference_repo=None):
        self.search_manager = search_manager
        self._reference_repo = reference_repo
        self._providers = {}

    @property
    def _ref_repo(self):
        if self._reference_repo is None:
            from app.repositories.reference_repository import ReferenceRepository

            self._reference_repo = ReferenceRepository()
        return self._reference_repo

    def _get_providers(self):
        """Lazy-load search providers."""
        if not self._providers and self.search_manager:
            self._providers = self.search_manager.providers
        return self._providers

    def detect_identifier(self, raw: str) -> tuple[str | None, str | None]:
        """Detect identifier type and return (type, value).

        Returns: ("doi", "10.1000/xyz") | ("pmid", "12345") |
                 ("arxiv", "2101.00001") | ("url", "https://...") |
                 (None, None)
        """
        raw = raw.strip()
        if _DOI_RE.match(raw):
            return "doi", raw
        if _PMID_RE.match(raw):
            return "pmid", raw
        if _ARXIV_RE.match(raw):
            return "arxiv", raw
        if raw.startswith(("http://", "https://")):
            # Try to extract DOI from URL
            doi_match = re.search(r"(10\.\d{4,}/\S+)", raw)
            if doi_match:
                return "doi", doi_match.group(1)
            return "url", raw
        return None, None

    def resolve(
        self, identifier: str, *, prefer_provider: str | None = None
    ) -> dict[str, Any] | None:
        """Resolve a single identifier to reference metadata.

        Returns metadata dict or None.
        """
        id_type, value = self.detect_identifier(identifier)
        if not id_type:
            return None

        providers = self._get_providers()

        # Try prefered provider first
        if prefer_provider and prefer_provider in providers:
            result = self._fetch_from_provider(prefer_provider, id_type, value)
            if result:
                return result

        # Try all providers
        order = {
            "doi": ["crossref", "semantic_scholar", "pubmed", "openalex"],
            "pmid": ["pubmed", "crossref", "semantic_scholar"],
            "arxiv": ["arxiv", "semantic_scholar", "crossref"],
            "url": ["semantic_scholar", "crossref"],
        }
        for provider_name in order.get(id_type, []):
            provider = providers.get(provider_name)
            if provider is None:
                continue
            result = self._fetch_from_provider(provider_name, id_type, value)
            if result:
                return result

        return None

    def resolve_batch(
        self, identifiers: list[str]
    ) -> list[tuple[str, dict[str, Any] | None]]:
        """Resolve multiple identifiers. Returns list of (original, result)."""
        results = []
        for ident in identifiers:
            metadata = self.resolve(ident)
            results.append((ident, metadata))
        return results

    def check_duplicate(
        self, project_id: int, metadata: dict[str, Any]
    ) -> Reference | None:
        """Check if a reference with this metadata already exists in the project."""
        doi = metadata.get("doi")
        if doi:
            existing = self._ref_repo.get_by_doi(project_id, doi)
            if existing:
                return existing

        title = metadata.get("title", "").lower().strip()
        if title:
            from app.services.ai_discovery_utils import normalize_for_match

            normalized = normalize_for_match(title)
            for ref in Reference.query.filter_by(project_id=project_id):
                if ref.title and normalize_for_match(ref.title) == normalized:
                    return ref

        return None

    def _fetch_from_provider(
        self, provider_name: str, id_type: str, value: str
    ) -> dict[str, Any] | None:
        """Fetch metadata from a specific provider."""
        providers = self._get_providers()
        provider = providers.get(provider_name)
        if not provider:
            return None

        try:
            if id_type == "doi" and hasattr(provider, "fetch_by_doi"):
                return provider.fetch_by_doi(value)
            elif id_type == "pmid" and hasattr(provider, "fetch_by_pmid"):
                return provider.fetch_by_pmid(value)
            elif id_type == "arxiv" and hasattr(provider, "fetch_by_id"):
                return provider.fetch_by_id(value)
            elif id_type in ("doi", "url"):
                # Fallback: try general search
                results = provider.search(value, limit=1)
                if results:
                    r = results[0]
                    return {
                        "title": r.title,
                        "authors": r.authors or [],
                        "abstract": r.abstract or "",
                        "doi": r.doi,
                        "publication_year": r.publication_date[:4]
                        if r.publication_date
                        else None,
                        "source": r.source,
                        "url": r.url,
                    }
        except Exception as exc:
            logger.warning(
                "SmartImportService: %s fetch failed for %s: %s",
                provider_name,
                id_type,
                exc,
            )

        return None

    def create_reference(self, project_id: int, metadata: dict[str, Any]) -> Reference:
        """Create a Reference from resolved metadata."""
        import re

        title = metadata.get("title", "Untitled")
        words = re.findall(r"[A-Za-z]+", title)
        author = words[0] if words else "Unknown"
        year = metadata.get("publication_year") or metadata.get("year") or ""
        citation_key = f"{author}{year}"

        authors = metadata.get("authors") or []

        ref = Reference(
            project_id=project_id,
            title=title,
            citation_key=citation_key,
            doi=metadata.get("doi"),
            year=int(year) if year and str(year).isdigit() else None,
            url=metadata.get("url"),
            source=metadata.get("source", "smart_import"),
            abstract=metadata.get("abstract", ""),
        )
        ref.set_authors(authors)
        self._ref_repo.add(ref)
        self._ref_repo.commit()
        return ref
