"""Search cache manager - Database-backed caching for search results (Phase 2.5)."""

import hashlib
import json
import logging
from datetime import datetime, UTC
from functools import lru_cache
from typing import List, Optional, Dict, Any

from app.database import db
from app.models.researcher.search_cache import SearchCache, SearchIndex
from app.integrations.search.base import SearchResult, SearchFilter
from app.integrations.search.search_manager import SearchManager

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class SearchCacheManager:
    """
    Database-backed caching layer for search results.
    
    Provides:
    - SQLite persistent caching with 24-hour TTL
    - In-memory LRU cache for hot queries (top 100)
    - Search indexing for analytics
    - Cache invalidation via project events
    """
    
    def __init__(self, search_manager: Optional[SearchManager] = None):
        """Initialize cache manager."""
        self.search_manager = search_manager or SearchManager.get_instance()
        self.lru_cache = {}  # In-memory LRU cache (will track usage)
        self.max_lru_size = 100  # Keep top 100 hot queries
    
    def search_with_cache(self, project_id: int, query: str,
                         sources: Optional[List[str]] = None,
                         filters: Optional[SearchFilter] = None,
                         limit: int = 20, deduplicate: bool = True,
                         cache_enabled: bool = True) -> tuple[List[SearchResult], bool]:
        """
        Execute search with caching and indexing.
        
        Returns:
            (results, was_cached) - whether results came from cache
        """
        if not query or len(query.strip()) < 2:
            return [], False
        
        # Generate cache key
        cache_key = self._make_cache_key(query, sources, filters)
        
        # Try in-memory LRU cache first
        if cache_enabled and cache_key in self.lru_cache:
            logger.debug(f"LRU cache hit for: {query}")
            cache_entry = self.lru_cache[cache_key]
            cache_entry['hits'] += 1
            return cache_entry['results'], True
        
        # Try database cache
        if cache_enabled:
            cached_results = self._get_from_db_cache(project_id, query, filters, sources)
            if cached_results is not None:
                logger.debug(f"Database cache hit for: {query}")
                self._add_to_lru_cache(cache_key, cached_results)
                return cached_results, True
        
        # Execute search
        logger.debug(f"Cache miss, executing search: {query}")
        results = self.search_manager.search(query, sources, filters, limit, deduplicate)
        
        # Cache results
        if cache_enabled:
            self._save_to_db_cache(project_id, query, sources, filters, results)
            self._save_to_index(project_id, query, results, sources)
            self._add_to_lru_cache(cache_key, results)
        
        return results, False
    
    def _make_cache_key(self, query: str, sources: Optional[List[str]] = None,
                       filters: Optional[SearchFilter] = None) -> str:
        """Generate cache key from query and filters."""
        source_key = "_".join(sorted(sources or [])) or "all"
        filters_key = json.dumps(self._serialize_filters(filters), sort_keys=True)
        hash_input = f"{query}:{source_key}:{filters_key}"
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def _serialize_filters(self, filters: Optional[SearchFilter]) -> Dict[str, Any]:
        """Serialize SearchFilter to dict for caching."""
        if not filters:
            return {}
        
        return {
            'from_date': filters.from_date,
            'to_date': filters.to_date,
            'publication_type': filters.publication_type,
            'language': filters.language,
            'open_access_only': filters.open_access_only,
            'max_citation_count': filters.max_citation_count,
            'min_citation_count': filters.min_citation_count,
        }
    
    def _get_from_db_cache(self, project_id: int, query: str,
                          filters: Optional[SearchFilter] = None,
                          sources: Optional[List[str]] = None) -> Optional[List[SearchResult]]:
        """Retrieve cached results from database (provider-aware lookup)."""
        try:
            provider = '_'.join(sorted(sources)) if sources else 'all'
            filters_part = json.dumps(self._serialize_filters(filters), sort_keys=True) if filters else ''
            # Hash must match SearchCache.__init__ logic: provider:query:filters_json
            query_hash = hashlib.sha256(f"{provider}:{query}:{filters_part}".encode()).hexdigest()

            cache_entry = SearchCache.query.filter_by(
                project_id=project_id,
                provider=provider,
                query_hash=query_hash
            ).first()
            
            if not cache_entry or cache_entry.is_expired():
                return None
            
            # Record cache hit
            cache_entry.record_hit()
            db.session.commit()
            
            # Deserialize results
            return cache_entry.get_results()
        
        except Exception as e:
            logger.error(f"Error retrieving from cache: {e}")
            return None
    
    def _save_to_db_cache(self, project_id: int, query: str,
                         sources: Optional[List[str]],
                         filters: Optional[SearchFilter],
                         results: List[SearchResult]):
        """Save search results to database cache."""
        try:
            filters_json = json.dumps(self._serialize_filters(filters)) if filters else None
            
            provider = '_'.join(sorted(sources)) if sources else 'all'
            cache_entry = SearchCache(
                project_id=project_id,
                provider=provider,
                query=query,
                results=results,
                filters_json=filters_json
            )
            
            db.session.add(cache_entry)
            db.session.commit()
            logger.debug(f"Cached {len(results)} results for query: {query}")
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error saving cache: {e}")
    
    def _save_to_index(self, project_id: int, query: str,
                      results: List[SearchResult],
                      sources: Optional[List[str]] = None):
        """Index search results for analytics and faceted search."""
        try:
            for result in results:
                # Check if already indexed (avoid duplicates)
                existing = SearchIndex.query.filter_by(
                    project_id=project_id,
                    source_id=result.source_id,
                    provider=result.source
                ).first()
                
                if existing:
                    # Update hit count
                    existing.record_find(query)
                else:
                    # Create new index entry
                    index_entry = SearchIndex(
                        project_id=project_id,
                        source_id=result.source_id,
                        provider=result.source,
                        result=result,
                        query=query
                    )
                    db.session.add(index_entry)
            
            db.session.commit()
            logger.debug(f"Indexed {len(results)} results")
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error indexing results: {e}")
    
    def _add_to_lru_cache(self, key: str, results: List[SearchResult]):
        """Add results to in-memory LRU cache."""
        self.lru_cache[key] = {
            'results': results,
            'hits': 1,
            'cached_at': _utcnow()
        }
        
        # Evict least-used if over limit
        if len(self.lru_cache) > self.max_lru_size:
            # Find least-used entry
            min_hits_key = min(self.lru_cache.keys(),
                             key=lambda k: self.lru_cache[k]['hits'])
            del self.lru_cache[min_hits_key]
    
    def invalidate_project_cache(self, project_id: int):
        """Invalidate all cache entries for a project."""
        try:
            SearchCache.query.filter_by(project_id=project_id).delete()
            db.session.commit()
            
            # Also clear LRU cache (simple approach - could optimize)
            self.lru_cache.clear()
            
            logger.info(f"Invalidated cache for project {project_id}")
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error invalidating cache: {e}")
    
    def invalidate_query_cache(self, project_id: int, query: str,
                              filters: Optional[SearchFilter] = None):
        """Invalidate cache for specific query."""
        try:
            # Filter by query string directly (query_hash includes provider, so
            # we can't reconstruct it without provider; match on the text column instead).
            q = SearchCache.query.filter_by(
                project_id=project_id,
                search_query=query,
            )
            if filters:
                filters_json = json.dumps(self._serialize_filters(filters), sort_keys=True)
                q = q.filter_by(filters_json=filters_json)
            q.delete(synchronize_session=False)
            db.session.commit()
            
            logger.info(f"Invalidated cache for query: {query}")
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error invalidating query cache: {e}")
    
    def get_cache_stats(self, project_id: int) -> Dict[str, Any]:
        """Get cache statistics for a project."""
        try:
            cache_entries = SearchCache.query.filter_by(project_id=project_id).all()
            
            total_hits = sum(entry.hit_count for entry in cache_entries)
            total_size_mb = sum(len(entry.results_json) for entry in cache_entries) / (1024 * 1024)
            expired = sum(1 for entry in cache_entries if entry.is_expired())
            
            return {
                'total_cached_queries': len(cache_entries),
                'total_cache_hits': total_hits,
                'total_cache_size_mb': total_size_mb,
                'expired_entries': expired,
                'lru_cache_size': len(self.lru_cache),
                'indexed_results': SearchIndex.query.filter_by(project_id=project_id).count(),
            }
        
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}
    
    def get_faceted_search(self, project_id: int, **facets) -> List[SearchIndex]:
        """
        Query indexed results by facets.
        
        Facets: provider, source, result_type, access_type, year (from publication_date)
        """
        try:
            query = SearchIndex.query.filter_by(project_id=project_id)
            
            if provider := facets.get('provider'):
                query = query.filter_by(provider=provider)
            
            if source := facets.get('source'):
                query = query.filter_by(source=source)
            
            if result_type := facets.get('result_type'):
                query = query.filter_by(result_type=result_type)
            
            if access_type := facets.get('access_type'):
                query = query.filter_by(access_type=access_type)
            
            if year := facets.get('year'):
                query = query.filter(
                    SearchIndex.publication_date >= f"{year}-01-01",
                    SearchIndex.publication_date < f"{int(year)+1}-01-01"
                )
            
            # Sort by found_count or citation count
            query = query.order_by(
                SearchIndex.found_count.desc(),
                SearchIndex.citation_count.desc()
            )
            
            return query.all()
        
        except Exception as e:
            logger.error(f"Error getting faceted search: {e}")
            return []
    
    def clear_expired_cache(self):
        """Remove expired cache entries from database."""
        try:
            expired_count = SearchCache.query.filter(
                SearchCache.expires_at < _utcnow()
            ).delete()
            db.session.commit()
            logger.info(f"Cleared {expired_count} expired cache entries")
            return expired_count
        
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error clearing expired cache: {e}")
            return 0


# Singleton instance
_cache_manager: Optional[SearchCacheManager] = None


def get_cache_manager() -> SearchCacheManager:
    """Get or create SearchCacheManager singleton."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = SearchCacheManager()
    return _cache_manager
