"""CrossRef API Provider — DOI-based metadata and publisher search."""

import requests
from typing import List, Optional, Dict
from ..base import (
    AbstractSearchProvider, SearchResult, SearchResultType,
    AccessType, SearchFilter, ProviderType
)


class CrossRefProvider(AbstractSearchProvider):
    """
    CrossRef API provider for published works metadata.

    Features:
    - 130M+ works with DOI resolution
    - Publisher and funder metadata
    - Reference linking
    - Polite pool: include mailto for better rate limits (50 req/sec vs 1 req/sec)
    """

    BASE_URL = "https://api.crossref.org"

    def __init__(self, mailto: str = "beep@example.com"):
        super().__init__(ProviderType.CROSSREF, rate_limit=50, timeout=30)
        self.mailto = mailto

    def search(self, query: str, filters: Optional[SearchFilter] = None,
               limit: int = 20) -> List[SearchResult]:
        """Search CrossRef for works matching query."""
        self.apply_rate_limit()

        if not query or len(query.strip()) < 2:
            return []

        try:
            params = {
                "query": query,
                "rows": min(limit, 100),
                "mailto": self.mailto,
                "select": "DOI,title,author,abstract,type,published-print,"
                          "published-online,container-title,URL,is-referenced-by-count,"
                          "link,subject"
            }

            # Date filter
            if filters:
                if filters.from_date:
                    params["filter"] = f"from-pub-date:{filters.from_date}"
                if filters.to_date:
                    existing = params.get("filter", "")
                    sep = "," if existing else ""
                    params["filter"] = f"{existing}{sep}until-pub-date:{filters.to_date}"

            response = requests.get(
                f"{self.BASE_URL}/works",
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("message", {}).get("items", []):
                result = self._parse_work(item)
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

    def _parse_work(self, item: Dict) -> Optional[SearchResult]:
        """Parse a CrossRef work item."""
        try:
            doi = item.get("DOI", "")

            # Title
            titles = item.get("title", [])
            title = titles[0] if titles else "Untitled"

            # Authors
            authors = []
            for a in item.get("author", []):
                given = a.get("given", "")
                family = a.get("family", "")
                authors.append(f"{given} {family}".strip())

            # Abstract (may be XML-encoded)
            abstract = item.get("abstract", "")
            if abstract.startswith("<jats:"):
                # Strip JATS XML tags
                import re
                abstract = re.sub(r'<[^>]+>', '', abstract).strip()

            # Date
            pub_date = None
            for date_field in ["published-print", "published-online", "created"]:
                dp = item.get(date_field, {}).get("date-parts", [[]])
                if dp and dp[0]:
                    parts = dp[0]
                    pub_date = "-".join(str(p).zfill(2) for p in parts[:3])
                    break

            # Type mapping
            cr_type = item.get("type", "")
            type_map = {
                "journal-article": SearchResultType.JOURNAL_ARTICLE,
                "proceedings-article": SearchResultType.CONFERENCE_PAPER,
                "book": SearchResultType.BOOK,
                "book-chapter": SearchResultType.BOOK_CHAPTER,
                "dataset": SearchResultType.DATASET,
                "dissertation": SearchResultType.THESIS,
                "report": SearchResultType.REPORT,
            }
            result_type = type_map.get(cr_type, SearchResultType.UNKNOWN)

            # PDF link
            pdf_url = None
            for link in item.get("link", []):
                if link.get("content-type") == "application/pdf":
                    pdf_url = link.get("URL")
                    break

            # Journal
            containers = item.get("container-title", [])
            journal = containers[0] if containers else ""

            # Citation count
            citation_count = item.get("is-referenced-by-count", 0)

            return SearchResult(
                id=f"crossref:{doi}",
                title=title,
                authors=authors,
                abstract=abstract,
                source="crossref",
                source_id=doi,
                url=item.get("URL", f"https://doi.org/{doi}"),
                pdf_url=pdf_url,
                doi=doi,
                publication_date=pub_date,
                citation_count=citation_count,
                access_type=AccessType.UNKNOWN,
                result_type=result_type,
                keywords=item.get("subject", []),
                metadata={
                    "journal": journal,
                    "publisher": item.get("publisher", ""),
                    "type": cr_type,
                }
            )
        except Exception:
            return None

    def get_metadata(self, source_id: str) -> Optional[Dict]:
        """Fetch full metadata for a DOI."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/works/{source_id}",
                params={"mailto": self.mailto},
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json().get("message", {})
        except Exception:
            return None

    def is_available(self) -> bool:
        """Check if CrossRef API is accessible."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/works",
                params={"query": "test", "rows": 1, "mailto": self.mailto},
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception:
            return False
