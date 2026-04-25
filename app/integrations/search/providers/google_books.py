"""Google Books search provider (Phase 03).

Uses the Google Books Volumes API.  An API key is optional — searches
work without one but rate limits are lower.  The key is resolved from
the integration credential vault (service type: 'google_books').

Never stores full copyrighted book text per Google Books Terms of Service.
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

_VOLUMES_URL = "https://www.googleapis.com/books/v1/volumes"


class GoogleBooksProvider(AbstractSearchProvider):
    """Book metadata search via the Google Books Volumes API.

    Returns title, authors, ISBN, publisher, year, thumbnail URL, and a
    link-out to Google Books.  No full-text book content is stored.

    ``api_key`` is optional.  Without it, the provider uses the public
    unauthenticated quota (which is lower).
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        super().__init__(
            ProviderType.GOOGLE_BOOKS,
            api_key=api_key,
            rate_limit=1000,
            timeout=20,
        )

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
            "maxResults": min(limit, 40),
            "printType": "books",
            "projection": "full",
        }
        if self.api_key:
            params["key"] = self.api_key

        if filters and filters.from_date:
            try:
                year = int(filters.from_date[:4])
                params["q"] += f" after:{year}"
            except (TypeError, ValueError):
                pass

        try:
            response = requests.get(_VOLUMES_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            self.record_request(success=False, error=str(exc))
            logger.warning("Google Books search failed: %s", exc)
            return []

        results: List[SearchResult] = []
        for item in (data.get("items") or [])[:limit]:
            result = self._parse_volume(item)
            if result:
                results.append(result)

        self.record_request(success=True)
        return results

    def get_metadata(self, source_id: str) -> Optional[SearchResult]:
        """Fetch a single volume by its Google Books ID."""
        params: dict = {}
        if self.api_key:
            params["key"] = self.api_key
        try:
            response = requests.get(
                f"{_VOLUMES_URL}/{source_id}",
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            item = response.json()
            return self._parse_volume(item)
        except Exception as exc:
            logger.warning("Google Books metadata fetch failed for %s: %s", source_id, exc)
            return None

    def is_available(self) -> bool:
        try:
            params: dict = {"q": "test", "maxResults": 1}
            if self.api_key:
                params["key"] = self.api_key
            r = requests.get(_VOLUMES_URL, params=params, timeout=5)
            return r.status_code < 500
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_volume(self, item: dict) -> Optional[SearchResult]:
        volume_id = item.get("id") or ""
        vi = item.get("volumeInfo") or {}

        title = (vi.get("title") or "").strip()
        if not title:
            return None

        authors = vi.get("authors") or []
        publisher = vi.get("publisher") or ""
        published_date = vi.get("publishedDate") or ""
        description = (vi.get("description") or "")[:1000]
        categories = vi.get("categories") or []
        info_link = vi.get("infoLink") or vi.get("canonicalVolumeLink") or ""

        # ISBN
        isbn13: Optional[str] = None
        isbn10: Optional[str] = None
        for ident in vi.get("industryIdentifiers") or []:
            if ident.get("type") == "ISBN_13":
                isbn13 = ident.get("identifier")
            elif ident.get("type") == "ISBN_10":
                isbn10 = ident.get("identifier")

        thumbnail_url: Optional[str] = None
        image_links = vi.get("imageLinks") or {}
        thumbnail_url = (
            image_links.get("thumbnail")
            or image_links.get("smallThumbnail")
        )

        # Normalise publication date to YYYY-MM-DD
        pub_date_norm: Optional[str] = None
        if published_date:
            if len(published_date) == 4:
                pub_date_norm = f"{published_date}-01-01"
            elif len(published_date) == 7:
                pub_date_norm = f"{published_date}-01"
            else:
                pub_date_norm = published_date[:10]

        metadata: dict = {
            "provider": "google_books",
            "volume_id": volume_id,
            "isbn13": isbn13,
            "isbn10": isbn10,
            "publisher": publisher,
            "thumbnail_url": thumbnail_url,
            "info_link": info_link,
        }

        return SearchResult(
            id=f"google_books:{volume_id}",
            title=title,
            authors=authors,
            abstract=description,
            source="google_books",
            source_id=volume_id,
            url=info_link,
            pdf_url=None,  # Never store copyrighted full text
            publication_date=pub_date_norm,
            result_type=SearchResultType.BOOK,
            access_type=AccessType.UNKNOWN,
            keywords=[str(c) for c in categories],
            metadata=metadata,
        )
