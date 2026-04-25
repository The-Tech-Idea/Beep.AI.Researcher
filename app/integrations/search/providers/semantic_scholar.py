"""Semantic Scholar API Provider — Free academic search with citation data."""

import requests
from typing import List, Optional, Dict
from datetime import datetime
from ..base import (
    AbstractSearchProvider, SearchResult, SearchResultType,
    AccessType, SearchFilter, ProviderType
)


class SemanticScholarProvider(AbstractSearchProvider):
    """
    Semantic Scholar API provider.

    Features:
    - 200M+ papers across all fields
    - Rich citation data (influential citations, citation velocity)
    - Paper recommendations
    - Free tier: 100 req / 5 min (public), 1 req/sec with API key
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(ProviderType.SEMANTIC_SCHOLAR,
                         api_key=api_key, rate_limit=100, timeout=30)
        self.headers = {}
        if api_key:
            self.headers["x-api-key"] = api_key

    def search(self, query: str, filters: Optional[SearchFilter] = None,
               limit: int = 20) -> List[SearchResult]:
        """Search Semantic Scholar for papers."""
        self.apply_rate_limit()

        if not query or len(query.strip()) < 2:
            return []

        try:
            params = {
                "query": query,
                "limit": min(limit, 100),
                "fields": "paperId,title,abstract,authors,year,citationCount,"
                          "url,externalIds,publicationDate,publicationTypes,"
                          "openAccessPdf,journal"
            }

            # Date filter
            if filters:
                if filters.from_date:
                    year = filters.from_date.split('-')[0]
                    params["year"] = f"{year}-"
                if filters.open_access_only:
                    params["openAccessPdf"] = ""

            response = requests.get(
                f"{self.BASE_URL}/paper/search",
                params=params,
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for paper in data.get("data", []):
                result = self._parse_paper(paper)
                if result:
                    results.append(result)

            self.record_request(success=True)
            return results

        except Exception as e:
            self.record_request(success=False, error=str(e))
            return []

    def search_by_topic(self, topic: str, limit: int = 20) -> List[SearchResult]:
        """Convenience wrapper for topic-driven recommendation queries."""
        return self.search(topic, limit=limit)

    def _parse_paper(self, paper: Dict) -> Optional[SearchResult]:
        """Parse a Semantic Scholar paper object."""
        try:
            paper_id = paper.get("paperId", "")
            external_ids = paper.get("externalIds", {}) or {}
            doi = external_ids.get("DOI")

            # Authors
            authors = []
            for a in paper.get("authors", []) or []:
                name = a.get("name", "")
                if name:
                    authors.append(name)

            # PDF URL
            oap = paper.get("openAccessPdf")
            pdf_url = oap.get("url") if oap else None

            # Access type
            access = AccessType.OPEN_ACCESS if pdf_url else AccessType.UNKNOWN

            # Publication type
            pub_types = paper.get("publicationTypes") or []
            if "JournalArticle" in pub_types:
                result_type = SearchResultType.JOURNAL_ARTICLE
            elif "Conference" in pub_types:
                result_type = SearchResultType.CONFERENCE_PAPER
            elif "Book" in pub_types:
                result_type = SearchResultType.BOOK
            else:
                result_type = SearchResultType.UNKNOWN

            # Journal
            journal = paper.get("journal", {}) or {}
            journal_name = journal.get("name", "")

            return SearchResult(
                id=f"s2:{paper_id}",
                title=paper.get("title", "Untitled"),
                authors=authors,
                abstract=paper.get("abstract") or "",
                source="semantic_scholar",
                source_id=paper_id,
                url=paper.get("url") or f"https://api.semanticscholar.org/CorpusID:{paper_id}",
                pdf_url=pdf_url,
                doi=doi,
                publication_date=paper.get("publicationDate"),
                citation_count=paper.get("citationCount", 0),
                access_type=access,
                result_type=result_type,
                metadata={
                    "semantic_scholar_id": paper_id,
                    "journal": journal_name,
                    "year": paper.get("year"),
                }
            )
        except Exception:
            return None

    def get_related_papers(self, source_id: str, limit: int = 10) -> List[SearchResult]:
        """Fetch related papers by paper id when the recommendation API is available."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/paper/{source_id}/recommendations",
                params={
                    "limit": min(limit, 100),
                    "fields": "paperId,title,abstract,authors,year,citationCount,"
                              "url,externalIds,publicationDate,publicationTypes,"
                              "openAccessPdf,journal"
                },
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            payload = response.json()
            results = []
            for paper in payload.get("recommendedPapers", []) or []:
                parsed = self._parse_paper(paper)
                if parsed:
                    results.append(parsed)
            return results
        except Exception:
            return []

    def get_metadata(self, source_id: str) -> Optional[Dict]:
        """Fetch full metadata for a paper by its S2 ID."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/paper/{source_id}",
                params={
                    "fields": "paperId,title,abstract,authors,year,citationCount,"
                              "referenceCount,url,externalIds,publicationDate,"
                              "openAccessPdf,journal,publicationTypes,tldr"
                },
                headers=self.headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    def is_available(self) -> bool:
        """Check if Semantic Scholar API is accessible."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/paper/search",
                params={"query": "test", "limit": 1, "fields": "paperId"},
                headers=self.headers,
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception:
            return False
