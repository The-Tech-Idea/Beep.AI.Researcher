"""OpenAlex API Provider — Open scholarly metadata (replaces OpenAccessButton)."""

import requests
from typing import List, Optional, Dict
from ..base import (
    AbstractSearchProvider, SearchResult, SearchResultType,
    AccessType, SearchFilter, ProviderType
)


class OpenAlexProvider(AbstractSearchProvider):
    """
    OpenAlex API provider for open scholarly metadata.

    Features:
    - 250M+ works, fully open, no auth required
    - Rich filtering: by institution, journal, concept, year
    - Open access status and PDF links
    - Replaces the deprecated OpenAccessButton provider
    """

    BASE_URL = "https://api.openalex.org"

    def __init__(self, mailto: str = "beep@example.com"):
        # Use OPENACCESSBUTTON slot since OpenAlex replaces it
        super().__init__(ProviderType.OPENACCESSBUTTON, rate_limit=100, timeout=30)
        self.mailto = mailto

    def search(self, query: str, filters: Optional[SearchFilter] = None,
               limit: int = 20) -> List[SearchResult]:
        """Search OpenAlex for works."""
        self.apply_rate_limit()

        if not query or len(query.strip()) < 2:
            return []

        try:
            params = {
                "search": query,
                "per_page": min(limit, 200),
                "mailto": self.mailto,
                "select": "id,doi,title,authorships,publication_date,"
                          "type,cited_by_count,open_access,primary_location,"
                          "abstract_inverted_index,concepts"
            }

            # Filters
            filter_parts = []
            if filters:
                if filters.from_date:
                    filter_parts.append(f"from_publication_date:{filters.from_date}")
                if filters.to_date:
                    filter_parts.append(f"to_publication_date:{filters.to_date}")
                if filters.open_access_only:
                    filter_parts.append("open_access.is_oa:true")
            if filter_parts:
                params["filter"] = ",".join(filter_parts)

            response = requests.get(
                f"{self.BASE_URL}/works",
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for work in data.get("results", []):
                result = self._parse_work(work)
                if result:
                    results.append(result)

            self.record_request(success=True)
            return results

        except Exception as e:
            self.record_request(success=False, error=str(e))
            return []

    def _parse_work(self, work: Dict) -> Optional[SearchResult]:
        """Parse an OpenAlex work object."""
        try:
            openalex_id = work.get("id", "").replace("https://openalex.org/", "")
            doi = (work.get("doi") or "").replace("https://doi.org/", "")

            # Title
            title = work.get("title") or "Untitled"

            # Authors
            authors = []
            for authorship in work.get("authorships", []):
                author = authorship.get("author", {})
                name = author.get("display_name", "")
                if name:
                    authors.append(name)

            # Abstract from inverted index
            abstract = self._reconstruct_abstract(work.get("abstract_inverted_index"))

            # Publication date
            pub_date = work.get("publication_date")

            # Type mapping
            oa_type = work.get("type", "")
            type_map = {
                "article": SearchResultType.JOURNAL_ARTICLE,
                "book": SearchResultType.BOOK,
                "book-chapter": SearchResultType.BOOK_CHAPTER,
                "dataset": SearchResultType.DATASET,
                "dissertation": SearchResultType.THESIS,
                "proceedings-article": SearchResultType.CONFERENCE_PAPER,
                "report": SearchResultType.REPORT,
            }
            result_type = type_map.get(oa_type, SearchResultType.UNKNOWN)

            # Open access info
            oa_info = work.get("open_access", {}) or {}
            is_oa = oa_info.get("is_oa", False)
            oa_url = oa_info.get("oa_url")

            # Primary location for PDF
            primary_loc = work.get("primary_location", {}) or {}
            source = primary_loc.get("source", {}) or {}
            journal_name = source.get("display_name", "")

            # Landing page URL
            landing_url = primary_loc.get("landing_page_url", "")

            # Concepts as keywords
            concepts = work.get("concepts", []) or []
            keywords = [c.get("display_name", "") for c in concepts[:5] if c.get("display_name")]

            return SearchResult(
                id=f"openalex:{openalex_id}",
                title=title,
                authors=authors,
                abstract=abstract,
                source="openalex",
                source_id=openalex_id,
                url=landing_url or f"https://openalex.org/{openalex_id}",
                pdf_url=oa_url,
                doi=doi if doi else None,
                publication_date=pub_date,
                citation_count=work.get("cited_by_count", 0),
                access_type=AccessType.OPEN_ACCESS if is_oa else AccessType.CLOSED,
                result_type=result_type,
                keywords=keywords,
                metadata={
                    "openalex_id": openalex_id,
                    "journal": journal_name,
                    "type": oa_type,
                }
            )
        except Exception:
            return None

    @staticmethod
    def _reconstruct_abstract(inverted_index: Optional[Dict]) -> str:
        """Reconstruct abstract text from OpenAlex inverted index format."""
        if not inverted_index:
            return ""
        try:
            # inverted_index: {"word": [position1, position2], ...}
            word_positions = []
            for word, positions in inverted_index.items():
                for pos in positions:
                    word_positions.append((pos, word))
            word_positions.sort(key=lambda x: x[0])
            return " ".join(w for _, w in word_positions)
        except Exception:
            return ""

    def get_metadata(self, source_id: str) -> Optional[Dict]:
        """Fetch full metadata for an OpenAlex work."""
        try:
            url = source_id if source_id.startswith("http") else f"{self.BASE_URL}/works/{source_id}"
            response = requests.get(
                url,
                params={"mailto": self.mailto},
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    def is_available(self) -> bool:
        """Check if OpenAlex API is accessible."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/works",
                params={"search": "test", "per_page": 1, "mailto": self.mailto},
                timeout=self.timeout
            )
            return response.status_code == 200
        except Exception:
            return False
