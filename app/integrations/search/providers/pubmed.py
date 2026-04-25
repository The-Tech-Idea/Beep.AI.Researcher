"""PubMed Central API Provider"""

import requests
from typing import List, Optional, Dict, Any
from datetime import datetime
import xml.etree.ElementTree as ET
from ..base import (
    AbstractSearchProvider, SearchResult, SearchResultType, 
    AccessType, SearchFilter, ProviderType
)


class PubMedProvider(AbstractSearchProvider):
    """
    PubMed Central API provider for searching biomedical literature.
    
    Features:
    - Searches PubMed Central (includes open access articles)
    - Supports date filtering and result pagination
    - Retrieves full article metadata including citations
    - Open access links to PDF articles
    """
    
    SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    
    def __init__(self, email: str = "beep@example.com"):
        """
        Initialize PubMed provider.
        
        Args:
            email: Email address for NCBI (required by their API)
        """
        super().__init__(ProviderType.PUBMED)
        self.email = email
    
    def search(self, query: str, filters: Optional[SearchFilter] = None,
               limit: int = 20) -> List[SearchResult]:
        """
        Search PubMed Central for articles matching the query.
        
        Args:
            query: Search query string
            filters: Optional filters (date range, open access only, etc)
            limit: Maximum number of results
        
        Returns:
            List of SearchResult objects
        """
        self.apply_rate_limit()
        
        if not query or len(query.strip()) < 2:
            return []
        
        try:
            # Build search query with filters
            search_term = self._build_search_term(query, filters)
            
            # Search for article IDs
            params = {
                "db": "pmc",
                "term": search_term,
                "retmax": min(limit, 100),  # API max is 100 per request
                "rettype": "json",
                "tool": "BeepAI",
                "email": self.email
            }
            
            response = requests.get(
                self.SEARCH_URL,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            article_ids = data.get("esearchresult", {}).get("idlist", [])
            
            if not article_ids:
                self.record_request(success=True)
                return []
            
            # Fetch metadata for articles
            results = []
            for article_id in article_ids[:limit]:
                result = self._fetch_article(article_id)
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
    
    def _build_search_term(self, query: str, filters: Optional[SearchFilter] = None) -> str:
        """Build PubMed search term with filters"""
        term = query
        
        if filters:
            # Add open access filter
            if filters.open_access_only:
                term += " AND open access[filter]"
            
            # Add date filter
            if filters.from_date:
                from_year = filters.from_date.split('-')[0]
                term += f" AND {from_year}[PDAT] : 3000[PDAT]"
            
            if filters.to_date:
                to_year = filters.to_date.split('-')[0]
                term += f" AND 1800[PDAT] : {to_year}[PDAT]"
            
            # Add publication type filter
            if filters.publication_type:
                type_map = {
                    'journal_article': 'Journal Article[PT]',
                    'preprint': 'Preprint[PT]',
                    'review': 'Review[PT]'
                }
                if filters.publication_type in type_map:
                    term += f" AND {type_map[filters.publication_type]}"
        
        return term
    
    def _fetch_article(self, article_id: str) -> Optional[SearchResult]:
        """Fetch full article metadata"""
        try:
            params = {
                "db": "pmc",
                "id": article_id,
                "rettype": "xml",
                "tool": "BeepAI",
                "email": self.email
            }
            
            response = requests.get(
                self.FETCH_URL,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # Parse XML response
            root = ET.fromstring(response.content)
            article_elem = root.find(".//article")
            
            if article_elem is None:
                return None
            
            # Extract metadata
            title = self._extract_text(article_elem, ".//title-group/article-title")
            abstract = self._extract_text(article_elem, ".//abstract/p")
            authors = self._extract_authors(article_elem)
            
            # Get PMC ID for link
            article_ids = article_elem.find(".//article-id-list")
            pmc_id = None
            if article_ids:
                for id_elem in article_ids.findall(".//article-id"):
                    if id_elem.get('pub-id-type') == 'pmc':
                        pmc_id = id_elem.text
                        break
            
            if not pmc_id:
                pmc_id = article_id
            
            # Extract publication date
            pub_date = self._extract_pub_date(article_elem)
            
            # Build result
            result = SearchResult(
                id=f"pubmed:{pmc_id}",
                title=title or "Untitled",
                authors=authors,
                abstract=abstract or "",
                source="pubmed",
                source_id=pmc_id,
                url=f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/",
                pdf_url=f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/",
                publication_date=pub_date,
                access_type=AccessType.OPEN_ACCESS,  # PMC articles are open access
                result_type=SearchResultType.JOURNAL_ARTICLE,
                keywords=self._extract_keywords(article_elem),
                journal=self._extract_journal(article_elem),
                metadata={'pmcid': pmc_id, 'pmid': article_id}
            )
            
            return result
        
        except Exception as e:
            return None
    
    def _extract_text(self, elem: ET.Element, path: str, default: str = "") -> str:
        """Extract text from XML element"""
        found = elem.find(path)
        if found is not None and found.text:
            return found.text.strip()
        return default
    
    def _extract_authors(self, article_elem: ET.Element) -> List[str]:
        """Extract author list from article"""
        authors = []
        contrib_group = article_elem.find(".//contrib-group")
        
        if contrib_group:
            for contrib in contrib_group.findall(".//contrib[@contrib-type='author']"):
                name_elem = contrib.find(".//name")
                if name_elem:
                    surname = name_elem.findtext("surname", "")
                    given = name_elem.findtext("given-names", "")
                    if surname:
                        authors.append(f"{given} {surname}".strip())
        
        return authors
    
    def _extract_pub_date(self, article_elem: ET.Element) -> Optional[str]:
        """Extract publication date"""
        pub_date = article_elem.find(".//pub-date")
        if pub_date:
            year = pub_date.findtext("year")
            month = pub_date.findtext("month", "01")
            day = pub_date.findtext("day", "01")
            
            if year:
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        return None
    
    def _extract_keywords(self, article_elem: ET.Element) -> List[str]:
        """Extract keywords from article"""
        keywords = []
        kwd_group = article_elem.find(".//kwd-group")
        
        if kwd_group:
            for kwd in kwd_group.findall(".//kwd"):
                if kwd.text:
                    keywords.append(kwd.text.strip())
        
        return keywords
    
    def _extract_journal(self, article_elem: ET.Element) -> Optional[str]:
        """Extract journal name"""
        journal = article_elem.find(".//journal-title")
        if journal and journal.text:
            return journal.text.strip()
        return None
    
    def get_metadata(self, source_id: str) -> Optional[Dict]:
        """Fetch full metadata for article"""
        try:
            params = {
                "db": "pmc",
                "id": source_id,
                "rettype": "xml",
                "tool": "BeepAI",
                "email": self.email
            }
            
            response = requests.get(
                self.FETCH_URL,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # Return XML as dict for processing
            return {'raw_xml': response.text}
        
        except Exception:
            return None
    
    def is_available(self) -> bool:
        """Check if PubMed API is accessible"""
        try:
            params = {
                "db": "pubmed",
                "id": "20676729",  # Known article ID
                "rettype": "json",
                "tool": "BeepAI",
                "email": self.email
            }
            
            response = requests.get(
                self.SUMMARY_URL,
                params=params,
                timeout=self.timeout
            )
            
            return response.status_code == 200
        except Exception:
            return False
