"""Search Manager - Centralized Search Across Multiple Providers"""

from typing import List, Dict, Optional, Set
from threading import Lock
from datetime import datetime, timedelta
import logging

from app.core.time_utils import utcnow_naive

from .base import (
    SearchResult, SearchFilter, AbstractSearchProvider,
    ProviderType, LocalSearchProvider
)

try:
    from .providers.pubmed import PubMedProvider
except ImportError:
    PubMedProvider = None

try:
    from .providers.arxiv import ArxivProvider
except ImportError:
    ArxivProvider = None

try:
    from .providers.semantic_scholar import SemanticScholarProvider
except ImportError:
    SemanticScholarProvider = None

try:
    from .providers.crossref import CrossRefProvider
except ImportError:
    CrossRefProvider = None

try:
    from .providers.openalex import OpenAlexProvider
except ImportError:
    OpenAlexProvider = None

try:
    from .providers.open_library import OpenLibraryProvider
except ImportError:
    OpenLibraryProvider = None

try:
    from .providers.google_books import GoogleBooksProvider
except ImportError:
    GoogleBooksProvider = None

logger = logging.getLogger(__name__)


class SearchManager:
    """
    Centralized search management system.
    
    Manages multiple search providers and handles:
    - Result deduplication
    - Result ranking/sorting
    - Query result caching
    - Provider availability monitoring
    """
    
    _instance = None
    _lock = Lock()
    
    def __init__(self):
        """Initialize SearchManager"""
        self.providers: Dict[str, AbstractSearchProvider] = {}
        self.result_cache: Dict[str, Dict] = {}  # Cache for search results
        self.cache_ttl = 3600  # 1 hour TTL
        self._initialize_providers()
    
    @classmethod
    def get_instance(cls) -> 'SearchManager':
        """Get singleton instance (thread-safe)"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def _initialize_providers(self):
        """Initialize default providers"""
        try:
            # Always include local provider
            self.register_provider("local", LocalSearchProvider())
            
            # Register external providers (graceful failure if API unavailable)
            if PubMedProvider is not None:
                try:
                    pubmed_provider = PubMedProvider(email="beep@example.com")
                    if pubmed_provider.is_available():
                        self.register_provider("pubmed", pubmed_provider)
                    else:
                        logger.warning("PubMed provider not available")
                except Exception as e:
                    logger.warning(f"Failed to initialize PubMed provider: {e}")
            
            if ArxivProvider is not None:
                try:
                    arxiv_provider = ArxivProvider()
                    if arxiv_provider.is_available():
                        self.register_provider("arxiv", arxiv_provider)
                    else:
                        logger.warning("arXiv provider not available")
                except Exception as e:
                    logger.warning(f"Failed to initialize arXiv provider: {e}")

            # Phase 2: Semantic Scholar
            if SemanticScholarProvider is not None:
                try:
                    s2_provider = SemanticScholarProvider()
                    self.register_provider("semantic_scholar", s2_provider)
                except Exception as e:
                    logger.warning(f"Failed to initialize Semantic Scholar provider: {e}")

            # Phase 2: CrossRef
            if CrossRefProvider is not None:
                try:
                    cr_provider = CrossRefProvider()
                    self.register_provider("crossref", cr_provider)
                except Exception as e:
                    logger.warning(f"Failed to initialize CrossRef provider: {e}")

            # Phase 2: OpenAlex
            if OpenAlexProvider is not None:
                try:
                    oa_provider = OpenAlexProvider()
                    self.register_provider("openalex", oa_provider)
                except Exception as e:
                    logger.warning(f"Failed to initialize OpenAlex provider: {e}")

            # Phase 03: OpenLibrary (no API key required)
            if OpenLibraryProvider is not None:
                try:
                    ol_provider = OpenLibraryProvider()
                    self.register_provider("open_library", ol_provider)
                except Exception as e:
                    logger.warning(f"Failed to initialize OpenLibrary provider: {e}")

            # Phase 03: Google Books (API key optional; resolved at runtime)
            if GoogleBooksProvider is not None:
                try:
                    gb_provider = GoogleBooksProvider()  # key injected per-request if needed
                    self.register_provider("google_books", gb_provider)
                except Exception as e:
                    logger.warning(f"Failed to initialize Google Books provider: {e}")

        except Exception as e:
            logger.error(f"Error initializing providers: {e}")
    
    def register_provider(self, name: str, provider: AbstractSearchProvider) -> bool:
        """
        Register a search provider.
        
        Args:
            name: Unique provider name
            provider: AbstractSearchProvider instance
        
        Returns:
            True if registered successfully
        """
        if not isinstance(provider, AbstractSearchProvider):
            raise ValueError("Provider must inherit from AbstractSearchProvider")
        
        self.providers[name] = provider
        logger.info(f"Registered search provider: {name}")
        return True
    
    def unregister_provider(self, name: str) -> bool:
        """Unregister a provider"""
        if name in self.providers:
            del self.providers[name]
            return True
        return False
    
    def get_available_providers(self) -> List[str]:
        """Get list of available providers"""
        available = []
        for name, provider in self.providers.items():
            try:
                if provider.is_available():
                    available.append(name)
            except Exception:
                pass
        return available
    
    def search(self, query: str, sources: Optional[List[str]] = None,
               filters: Optional[SearchFilter] = None,
               limit: int = 20, deduplicate: bool = True) -> List[SearchResult]:
        """
        Search across multiple sources.
        
        Args:
            query: Search query string
            sources: List of provider names to search (None = all available)
            filters: Search filters
            limit: Max results per source
            deduplicate: Whether to deduplicate results
        
        Returns:
            List of SearchResult objects
        """
        if not query or len(query.strip()) < 2:
            return []
        
        # Check cache
        cache_key = self._make_cache_key(query, sources)
        cached = self._get_cached_results(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit for query: {query}")
            return cached
        
        # Determine sources to search
        if sources is None or len(sources) == 0:
            # Default: local + available external sources
            sources = ["local"] + self.get_available_providers()
        else:
            # Filter to only registered providers
            sources = [s for s in sources if s in self.providers]
        
        # Search all sources
        all_results = []
        for source_name in sources:
            try:
                provider = self.providers.get(source_name)
                if provider is None:
                    logger.warning(f"Provider not found: {source_name}")
                    continue
                
                results = provider.search(query, filters, limit)
                if results:
                    logger.debug(f"Got {len(results)} results from {source_name}")
                    all_results.extend(results)
            
            except Exception as e:
                logger.error(f"Error searching {source_name}: {e}")
                continue
        
        # Deduplicate
        if deduplicate:
            all_results = self._deduplicate_results(all_results)
        
        # Sort by relevance
        sorted_results = self._sort_results(all_results)[:limit]
        
        # Cache results
        self._cache_results(cache_key, sorted_results)
        
        logger.info(f"Search '{query}': {len(sorted_results)} results from {len(sources)} sources")
        return sorted_results
    
    def _make_cache_key(self, query: str, sources: Optional[List[str]]) -> str:
        """Create cache key for search"""
        source_key = "_".join(sorted(sources)) if sources else "all"
        return f"{query}:{source_key}"
    
    def _get_cached_results(self, key: str) -> Optional[List[SearchResult]]:
        """Get cached search results if still valid"""
        if key not in self.result_cache:
            return None
        
        cached = self.result_cache[key]
        age = (utcnow_naive() - cached['time']).total_seconds()
        
        if age > self.cache_ttl:
            del self.result_cache[key]
            return None
        
        return cached['results']
    
    def _cache_results(self, key: str, results: List[SearchResult]):
        """Cache search results"""
        self.result_cache[key] = {
            'time': utcnow_naive(),
            'results': results
        }
    
    def _deduplicate_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicate results based on title and DOI"""
        seen: Set[str] = set()
        unique_results = []
        
        for result in results:
            # Prefer DOI for fingerprinting if available, otherwise use title
            if result.doi:
                fingerprint = f"doi:{result.doi}"
            else:
                fingerprint = f"title:{result.title.lower().strip()}"
            
            if fingerprint not in seen:
                seen.add(fingerprint)
                unique_results.append(result)
        
        return unique_results
    
    def _sort_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """Sort results by relevance (citation count, then date)"""
        def relevance_score(result: SearchResult) -> tuple:
            # Score: (has_citation_count, citation_count DESC, has_date, date DESC)
            citation_count = result.citation_count or 0
            
            # Parse date for sorting (newer = higher score)
            date_score = 0
            if result.publication_date:
                try:
                    date_obj = datetime.fromisoformat(result.publication_date)
                    # Days since epoch (more recent = higher number)
                    date_score = (date_obj - datetime(1970, 1, 1)).days
                except Exception:
                    date_score = 0
            
            # Return tuple for sorting (higher scores first)
            return (-citation_count, -date_score)
        
        return sorted(results, key=relevance_score)
    
    def get_provider_stats(self) -> Dict[str, Dict]:
        """Get statistics for all providers"""
        stats = {}
        for name, provider in self.providers.items():
            try:
                stats[name] = provider.get_stats()
            except Exception as e:
                stats[name] = {'error': str(e)}
        return stats
    
    def clear_cache(self):
        """Clear all cached search results"""
        self.result_cache.clear()
        logger.info("Cleared search cache")
    
    def set_cache_ttl(self, ttl_seconds: int):
        """Set cache time-to-live"""
        self.cache_ttl = ttl_seconds
        logger.info(f"Set cache TTL to {ttl_seconds} seconds")


def get_search_manager() -> SearchManager:
    """Convenience function to get SearchManager instance"""
    return SearchManager.get_instance()
