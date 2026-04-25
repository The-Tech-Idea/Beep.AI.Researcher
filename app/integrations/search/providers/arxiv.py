"""arXiv API Provider"""

import requests
from typing import List, Optional, Dict
from datetime import datetime
from ..base import (
    AbstractSearchProvider, SearchResult, SearchResultType,
    AccessType, SearchFilter, ProviderType
)


class ArxivProvider(AbstractSearchProvider):
    """
    arXiv API provider for preprints across multiple fields.
    
    Features:
    - Searches preprints in physics, mathematics, computer science, etc
    - Returns open access PDFs for all results
    - Supports filtering by category and date
    - High-speed API with no authentication required
    """
    
    BASE_URL = "http://export.arxiv.org/api/query"
    
    def __init__(self):
        super().__init__(ProviderType.ARXIV, rate_limit=1000)
    
    def search(self, query: str, filters: Optional[SearchFilter] = None,
               limit: int = 20) -> List[SearchResult]:
        """
        Search arXiv for papers matching the query.
        
        Args:
            query: Search query
            filters: Optional filters
            limit: Maximum results
        
        Returns:
            List of SearchResult objects
        """
        self.apply_rate_limit()
        
        if not query or len(query.strip()) < 2:
            return []
        
        try:
            # Build search query
            search_term = query.replace(" ", "+")
            
            params = {
                "search_query": f"all:{search_term}",
                "start": 0,
                "max_results": min(limit, 100),
                "sortBy": "relevance",
                "sortOrder": "descending"
            }
            
            # Add date filter if provided
            if filters and filters.from_date:
                # arXiv uses submission date filtering
                from_year = filters.from_date.split('-')[0]
                params["search_query"] += f" AND submittedDate:[{from_year}010100000000 TO 99991231235959]"
            
            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # Parse Atom feed
            import feedparser
            feed = feedparser.parse(response.text)
            results = []
            
            for entry in feed.entries[:limit]:
                result = self._parse_entry(entry)
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
    
    def _parse_entry(self, entry: Dict) -> Optional[SearchResult]:
        """Parse arXiv feed entry"""
        try:
            # Extract arXiv ID
            arxiv_id = entry.id.split('/abs/')[-1]
            
            # Extract authors
            authors = []
            if 'authors' in entry:
                authors = [author.name for author in entry.authors]
            
            # Extract publication date
            published = entry.get('published', '')
            if published:
                # Format: 2024-01-15T12:34:56Z -> Extract date
                pub_date = published.split('T')[0]
            else:
                pub_date = None
            
            # Extract summary
            summary = entry.get('summary', '').replace('\n', ' ').strip()
            
            # Extract primary category
            categories = []
            primary_category = ''
            if 'arxiv_primary_category' in entry:
                primary_category = entry['arxiv_primary_category'].get('term', '')
                categories.append(primary_category)
            
            # Map category to type
            type_map = {
                'cond-mat': SearchResultType.PREPRINT,
                'quant-ph': SearchResultType.PREPRINT,
                'physics': SearchResultType.PREPRINT,
                'math': SearchResultType.PREPRINT,
                'cs': SearchResultType.PREPRINT,
                'stat': SearchResultType.PREPRINT,
            }
            
            category_prefix = primary_category.split('.')[0] if primary_category else 'unknown'
            result_type = type_map.get(category_prefix, SearchResultType.PREPRINT)
            
            # Build result
            result = SearchResult(
                id=f"arxiv:{arxiv_id}",
                title=entry.get('title', 'Untitled'),
                authors=authors,
                abstract=summary,
                source="arxiv",
                source_id=arxiv_id,
                url=entry.id,
                pdf_url=f"http://arxiv.org/pdf/{arxiv_id}.pdf",
                publication_date=pub_date,
                access_type=AccessType.OPEN_ACCESS,
                result_type=result_type,
                keywords=categories,
                metadata={
                    'arxiv_id': arxiv_id,
                    'primary_category': primary_category
                }
            )
            
            return result
        
        except Exception:
            return None
    
    def get_metadata(self, source_id: str) -> Optional[Dict]:
        """Fetch metadata for arxiv preprint"""
        try:
            # For arXiv, we can get metadata via API
            params = {
                "search_query": f"arXiv:{source_id}",
                "start": 0,
                "max_results": 1
            }
            
            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            import feedparser
            feed = feedparser.parse(response.text)
            if feed.entries:
                entry = feed.entries[0]
                return {
                    'title': entry.get('title'),
                    'authors': [a.name for a in entry.get('authors', [])],
                    'abstract': entry.get('summary'),
                    'published': entry.get('published'),
                    'arxiv_id': source_id
                }
            return None
        
        except Exception:
            return None
    
    def is_available(self) -> bool:
        """Check if arXiv API is accessible"""
        try:
            params = {
                "search_query": "arXiv:1234.5678",  # Known paper
                "max_results": 1
            }
            
            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout
            )
            
            return response.status_code == 200
        except Exception:
            return False
