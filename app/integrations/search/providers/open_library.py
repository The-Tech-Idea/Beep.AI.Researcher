"""OpenLibrary search provider (Phase 03).

Uses the Open Library Search API — free, no API key required.
Returns book metadata plus a link-out to Open Library; never stores
full copyrighted text.
"""
from __future__ import annotations

import logging
from typing import List, Optional

import requests

from ..base import (
    AbstractSearchProvider,
    AccessType,
    ProviderType,
    SearchFilter,
    SearchResult,
    SearchResultType,
)

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://openlibrary.org/search.json"
_COVER_URL = "https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
_WORK_URL = "https://openlibrary.org{key}"


class OpenLibraryProvider(AbstractSearchProvider):
    """Book metadata search via the Open Library Search API.

    Returns title, authors, ISBN, publisher, year, thumbnail URL, and a
    link-out to Open Library.  No copyrighted full text is stored.
    """

    def __init__(self) -> None:
        super().__init__(ProviderType.OPEN_LIBRARY, rate_limit=500, timeout=20)

    # ------------------------------------------------------------------
    # AbstractSearchProvider interface
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        filters: Optional[SearchFilter] = None,
        limit: int = 20,
    ) -> List[SearchResult]:
        self.apply_rate_limit()

        if not query or len(query.strip()) < 2:
            return []

        params: dict = {
            "q": query.strip(),
            "limit": min(limit, 100),
            "fields": (
                "key,title,author_name,first_publish_year,publisher,"
                "isbn,cover_i,subject,language,number_of_pages_median"
            ),
        }

        if filters:
            if filters.from_date:
                try:
                    params["publish_year"] = filters.from_date[:4]
                except (TypeError, IndexError):
                    pass

        try:
            response = requests.get(_SEARCH_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            self.record_request(success=False, error=str(exc))
            logger.warning("OpenLibrary search failed: %s", exc)
            return []

        results: List[SearchResult] = []
        for doc in (data.get("docs") or [])[:limit]:
            result = self._parse_doc(doc)
            if result:
                results.append(result)

        self.record_request(success=True)
        return results

    def get_metadata(self, source_id: str) -> Optional[SearchResult]:
        """Fetch a single work by its Open Library key (e.g. '/works/OL12345W')."""
        try:
            response = requests.get(
                f"https://openlibrary.org{source_id}.json",
                timeout=self.timeout,
            )
            response.raise_for_status()
            doc = response.json()
            return self._parse_work(source_id, doc)
        except Exception as exc:
            logger.warning("OpenLibrary metadata fetch failed for %s: %s", source_id, exc)
            return None

    def is_available(self) -> bool:
        try:
            r = requests.get(
                _SEARCH_URL, params={"q": "test", "limit": 1}, timeout=5
            )
            return r.status_code < 500
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_doc(self, doc: dict) -> Optional[SearchResult]:
        key = doc.get("key") or ""
        title = (doc.get("title") or "").strip()
        if not title:
            return None

        authors = doc.get("author_name") or []
        year = doc.get("first_publish_year")
        publishers = doc.get("publisher") or []
        isbns = doc.get("isbn") or []
        cover_id = doc.get("cover_i")
        subjects = doc.get("subject") or []

        thumbnail_url: Optional[str] = None
        if cover_id:
            thumbnail_url = _COVER_URL.format(cover_id=cover_id)

        info_link = f"https://openlibrary.org{key}" if key else ""

        metadata: dict = {
            "provider": "open_library",
            "work_key": key,
            "isbn": isbns[0] if isbns else None,
            "publisher": publishers[0] if publishers else None,
            "thumbnail_url": thumbnail_url,
            "info_link": info_link,
        }

        return SearchResult(
            id=f"open_library:{key}",
            title=title,
            authors=authors,
            abstract=", ".join(str(s) for s in subjects[:10]),
            source="open_library",
            source_id=key,
            url=info_link,
            pdf_url=None,
            publication_date=f"{year}-01-01" if year else None,
            result_type=SearchResultType.BOOK,
            access_type=AccessType.OPEN_ACCESS,
            keywords=[str(s) for s in subjects[:10]],
            metadata=metadata,
        )

    def _parse_work(self, key: str, doc: dict) -> Optional[SearchResult]:
        title = (doc.get("title") or "").strip()
        if not title:
            return None

        description = doc.get("description") or ""
        if isinstance(description, dict):
            description = description.get("value") or ""

        subjects = doc.get("subjects") or []
        info_link = f"https://openlibrary.org{key}"

        return SearchResult(
            id=f"open_library:{key}",
            title=title,
            authors=[],
            abstract=str(description)[:1000],
            source="open_library",
            source_id=key,
            url=info_link,
            result_type=SearchResultType.BOOK,
            access_type=AccessType.OPEN_ACCESS,
            keywords=[str(s) for s in subjects[:10]],
            metadata={
                "provider": "open_library",
                "work_key": key,
                "info_link": info_link,
            },
        )
