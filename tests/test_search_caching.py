"""Tests for Phase 2.5: Search Caching & Indexing."""

import pytest
import json
from datetime import datetime, timedelta
from app import create_app
from app.database import db
from app.models.researcher import (
    ResearchProject, SearchCache, SearchIndex,
    LibrarySource, SourceImportLog
)
from app.integrations.search.base import SearchResult, SearchResultType, AccessType
from app.services.search_cache_manager import SearchCacheManager


@pytest.fixture
def app():
    """Create test app."""
    app = create_app()
    app.config['TESTING'] = True
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def project(app):
    """Create test project."""
    with app.app_context():
        project = ResearchProject(name='Test Project', description='For testing')
        db.session.add(project)
        db.session.commit()
        return project


@pytest.fixture
def sample_results():
    """Create sample search results."""
    return [
        SearchResult(
            id='pubmed:12345',
            title='Machine Learning in Healthcare',
            authors=['Smith, J.', 'Doe, A.'],
            abstract='This study explores ML applications in healthcare',
            source='pubmed',
            source_id='12345',
            url='https://pubmed.ncbi.nlm.nih.gov/12345',
            pdf_url='https://example.com/ml-healthcare.pdf',
            publication_date='2023-01-15',
            result_type=SearchResultType.JOURNAL_ARTICLE,
            access_type=AccessType.OPEN_ACCESS,
            citation_count=45,
            keywords=['machine learning', 'healthcare', 'AI'],
            journal='Journal of Medical Computing',
            volume='15',
            issue='3',
            pages='234-245',
            doi='10.1234/jmc.2023.001',
        ),
        SearchResult(
            id='arxiv:2301.05000',
            title='Deep Learning Interpretability',
            authors=['Johnson, B.', 'Williams, C.'],
            abstract='Survey on interpretability methods for deep neural networks',
            source='arxiv',
            source_id='2301.05000',
            url='https://arxiv.org/abs/2301.05000',
            pdf_url='https://arxiv.org/pdf/2301.05000.pdf',
            publication_date='2023-01-20',
            result_type=SearchResultType.PREPRINT,
            access_type=AccessType.OPEN_ACCESS,
            citation_count=12,
            keywords=['deep learning', 'interpretability', 'AI safety'],
            doi='10.48550/arXiv.2301.05000',
        ),
    ]


# Test Suite 1: Cache Hit/Miss (4 tests)
class TestCacheHitMiss:
    """Test cache hit and miss scenarios."""
    
    def test_cache_miss_first_search(self, app, project, sample_results):
        """Test that first search results in cache miss."""
        with app.app_context():
            cache_manager = SearchCacheManager()
            query = 'machine learning healthcare'
            
            # Mock search_manager to return sample results
            cache_manager.search_manager.search = lambda *args, **kwargs: sample_results
            
            results, was_cached = cache_manager.search_with_cache(
                project.id, query, cache_enabled=True
            )
            
            assert len(results) == 2
            assert not was_cached
            assert results[0].title == 'Machine Learning in Healthcare'
    
    def test_cache_hit_second_search(self, app, project, sample_results):
        """Test that second search with same query hits cache."""
        with app.app_context():
            cache_manager = SearchCacheManager()
            query = 'machine learning healthcare'
            
            cache_manager.search_manager.search = lambda *args, **kwargs: sample_results
            
            # First search - cache miss
            results1, was_cached1 = cache_manager.search_with_cache(
                project.id, query, cache_enabled=True
            )
            assert not was_cached1
            
            # Second search - cache hit
            results2, was_cached2 = cache_manager.search_with_cache(
                project.id, query, cache_enabled=True
            )
            assert was_cached2
            assert len(results2) == 2
            assert results2[0].id == results1[0].id
    
    def test_cache_disabled(self, app, project, sample_results):
        """Test that cache can be disabled."""
        with app.app_context():
            cache_manager = SearchCacheManager()
            query = 'deep learning'
            
            cache_manager.search_manager.search = lambda *args, **kwargs: sample_results
            
            # Search with cache disabled
            results, was_cached = cache_manager.search_with_cache(
                project.id, query, cache_enabled=False
            )
            
            assert not was_cached
            assert len(results) == 2
    
    def test_different_queries_different_cache(self, app, project, sample_results):
        """Test that different queries use different cache entries."""
        with app.app_context():
            cache_manager = SearchCacheManager()
            
            cache_manager.search_manager.search = lambda *args, **kwargs: sample_results
            
            # First query
            results1, _ = cache_manager.search_with_cache(
                project.id, 'machine learning', cache_enabled=True
            )
            
            # Different query should not be cached together
            different_results = [sample_results[0]]
            cache_manager.search_manager.search = lambda *args, **kwargs: different_results
            results2, was_cached = cache_manager.search_with_cache(
                project.id, 'neural networks', cache_enabled=True
            )
            
            assert not was_cached  # Different query, not cached
            assert len(results2) == 1


# Test Suite 2: TTL Expiration (3 tests)
class TestCacheTTL:
    """Test cache TTL and expiration."""
    
    def test_cache_not_expired_within_ttl(self, app, project, sample_results):
        """Test that fresh cache is not expired."""
        with app.app_context():
            cache_entry = SearchCache(
                project_id=project.id,
                provider='pubmed',
                query='test query',
                results=sample_results,
                filters_json=None
            )
            
            assert not cache_entry.is_expired()
    
    def test_cache_expired_after_ttl(self, app, project, sample_results):
        """Test that old cache is marked expired."""
        with app.app_context():
            cache_entry = SearchCache(
                project_id=project.id,
                provider='pubmed',
                query='test query',
                results=sample_results,
                filters_json=None
            )
            
            # Set expiration to past
            cache_entry.expires_at = datetime.utcnow() - timedelta(hours=1)
            
            assert cache_entry.is_expired()
    
    def test_clear_expired_cache(self, app, project, sample_results):
        """Test clearing expired cache entries."""
        with app.app_context():
            # Create fresh cache entry
            fresh_cache = SearchCache(
                project_id=project.id,
                provider='pubmed',
                query='fresh query',
                results=sample_results,
                filters_json=None
            )
            db.session.add(fresh_cache)
            
            # Create expired cache entry
            expired_cache = SearchCache(
                project_id=project.id,
                provider='arxiv',
                query='expired query',
                results=sample_results,
                filters_json=None
            )
            expired_cache.expires_at = datetime.utcnow() - timedelta(hours=1)
            db.session.add(expired_cache)
            db.session.commit()
            
            # Clear expired
            cache_manager = SearchCacheManager()
            cleared = cache_manager.clear_expired_cache()
            
            # One should be cleared
            assert cleared == 1
            
            # Fresh one should remain
            remaining = SearchCache.query.filter_by(project_id=project.id).count()
            assert remaining == 1


# Test Suite 3: Cache Invalidation (4 tests)
class TestCacheInvalidation:
    """Test cache invalidation."""
    
    def test_invalidate_project_cache(self, app, project, sample_results):
        """Test invalidating all cache for a project."""
        with app.app_context():
            # Add multiple cache entries
            for i in range(3):
                cache = SearchCache(
                    project_id=project.id,
                    provider='pubmed',
                    query=f'query {i}',
                    results=sample_results,
                    filters_json=None
                )
                db.session.add(cache)
            db.session.commit()
            
            assert SearchCache.query.filter_by(project_id=project.id).count() == 3
            
            # Invalidate
            cache_manager = SearchCacheManager()
            cache_manager.invalidate_project_cache(project.id)
            
            # All should be deleted
            assert SearchCache.query.filter_by(project_id=project.id).count() == 0
    
    def test_invalidate_query_cache(self, app, project, sample_results):
        """Test invalidating cache for specific query."""
        with app.app_context():
            # Add multiple cache entries with different queries
            query1_cache = SearchCache(
                project_id=project.id,
                provider='pubmed',
                query='machine learning',
                results=sample_results,
                filters_json=None
            )
            
            query2_cache = SearchCache(
                project_id=project.id,
                provider='pubmed',
                query='deep learning',
                results=sample_results,
                filters_json=None
            )
            
            db.session.add(query1_cache)
            db.session.add(query2_cache)
            db.session.commit()
            
            # Invalidate only first query
            cache_manager = SearchCacheManager()
            cache_manager.invalidate_query_cache(project.id, 'machine learning')
            
            # Only query2 should remain
            remaining = SearchCache.query.filter_by(project_id=project.id).all()
            assert len(remaining) == 1
            assert remaining[0].query == 'deep learning'
    
    def test_cache_hit_count_tracking(self, app, project, sample_results):
        """Test that cache tracks hit count."""
        with app.app_context():
            cache_entry = SearchCache(
                project_id=project.id,
                provider='pubmed',
                query='test',
                results=sample_results,
                filters_json=None
            )
            cache_entry.hit_count = 0
            db.session.add(cache_entry)
            db.session.commit()
            
            # Record hits
            cache_entry.record_hit()
            cache_entry.record_hit()
            cache_entry.record_hit()
            db.session.commit()
            
            assert cache_entry.hit_count == 3
            assert cache_entry.last_accessed is not None
    
    def test_lru_eviction(self, app, project, sample_results):
        """Test LRU cache eviction when exceeding size limit."""
        with app.app_context():
            cache_manager = SearchCacheManager()
            cache_manager.max_lru_size = 3  # Small size for testing
            
            # Add 4 items (should evict least-used)
            for i in range(4):
                key = f"key_{i}"
                results = [sample_results[0]] * (i + 1)
                cache_manager._add_to_lru_cache(key, results)
            
            # LRU size should not exceed max
            assert len(cache_manager.lru_cache) <= 3


# Test Suite 4: Search from Cache (3 tests)
class TestSearchFromCache:
    """Test searching with caching."""
    
    def test_search_returns_cached_results(self, app, project, sample_results):
        """Test that search returns cached results."""
        with app.app_context():
            cache = SearchCache(
                project_id=project.id,
                provider='pubmed',
                query='test search',
                results=sample_results,
                filters_json=None
            )
            db.session.add(cache)
            db.session.commit()
            
            cache_manager = SearchCacheManager()
            results = cache.get_results()
            
            assert len(results) == 2
            assert isinstance(results[0], dict)  # Deserialized from JSON
            assert results[0]['title'] == 'Machine Learning in Healthcare'
    
    def test_empty_search_no_cache(self, app, project):
        """Test that empty query returns no results."""
        with app.app_context():
            cache_manager = SearchCacheManager()
            results, was_cached = cache_manager.search_with_cache(
                project.id, '', cache_enabled=True
            )
            
            assert results == []
            assert not was_cached
    
    def test_cache_key_generation(self, app):
        """Test that cache keys are correctly generated."""
        with app.app_context():
            cache_manager = SearchCacheManager()
            
            # Same query should generate same key
            key1 = cache_manager._make_cache_key('test query', ['pubmed'])
            key2 = cache_manager._make_cache_key('test query', ['pubmed'])
            
            assert key1 == key2
            
            # Different query should generate different key
            key3 = cache_manager._make_cache_key('different query', ['pubmed'])
            assert key1 != key3


# Test Suite 5: Search Indexing (3 tests)
class TestSearchIndexing:
    """Test search result indexing."""
    
    def test_index_search_result(self, app, project, sample_results):
        """Test indexing a search result."""
        with app.app_context():
            result = sample_results[0]
            
            index = SearchIndex(
                project_id=project.id,
                source_id=result.source_id,
                provider=result.source,
                result=result,
                query='machine learning'
            )
            
            assert index.title == 'Machine Learning in Healthcare'
            assert index.access_type == 'open_access'
            assert index.citation_count == 45
            assert index.found_count == 1
    
    def test_faceted_search_by_provider(self, app, project, sample_results):
        """Test faceted search filtering by provider."""
        with app.app_context():
            # Index multiple results
            for result in sample_results:
                index = SearchIndex(
                    project_id=project.id,
                    source_id=result.source_id,
                    provider=result.source,
                    result=result,
                    query='test'
                )
                db.session.add(index)
            db.session.commit()
            
            # Faceted search by provider
            cache_manager = SearchCacheManager()
            results = cache_manager.get_faceted_search(
                project.id, provider='pubmed'
            )
            
            assert len(results) == 1
            assert results[0].provider == 'pubmed'
    
    def test_search_index_deduplication(self, app, project, sample_results):
        """Test that duplicate results are handled in indexing."""
        with app.app_context():
            result = sample_results[0]
            source_id = result.source_id
            provider = result.source
            
            # Create first index
            index1 = SearchIndex(
                project_id=project.id,
                source_id=source_id,
                provider=provider,
                result=result,
                query='query1'
            )
            db.session.add(index1)
            db.session.commit()
            
            # Try to add same result again (simulate duplicate)
            # In real implementation, would check existing first
            existing = SearchIndex.query.filter_by(
                project_id=project.id,
                source_id=source_id,
                provider=provider
            ).first()
            
            assert existing is not None
            assert existing.found_count == 1
            
            # Record another find
            existing.record_find('query2')
            db.session.commit()
            
            assert existing.found_count == 2


# Test Suite 6: Performance Metrics (2 tests)
class TestCachePerformance:
    """Test cache performance improvements."""
    
    def test_cache_stats(self, app, project, sample_results):
        """Test getting cache statistics."""
        with app.app_context():
            # Add cache entries
            cache = SearchCache(
                project_id=project.id,
                provider='pubmed',
                query='test',
                results=sample_results,
                filters_json=None
            )
            cache.hit_count = 5
            db.session.add(cache)
            db.session.commit()
            
            cache_manager = SearchCacheManager()
            stats = cache_manager.get_cache_stats(project.id)
            
            assert stats['total_cached_queries'] == 1
            assert stats['total_cache_hits'] == 5
            assert stats['total_cache_size_mb'] > 0
    
    def test_lru_cache_efficiency(self, app):
        """Test LRU cache hit efficiency."""
        with app.app_context():
            cache_manager = SearchCacheManager()
            
            # Simulate hot queries
            results1 = [SearchResult(
                id='test1', title='Test', authors=[], abstract='',
                source='test', source_id='1', url='http://test'
            )]
            
            # Add to LRU and access multiple times
            for i in range(5):
                cache_manager._add_to_lru_cache('hot_query', results1)
                cache_manager.lru_cache['hot_query']['hits'] += 1
            
            # Check that hot query has high hit count
            assert cache_manager.lru_cache['hot_query']['hits'] > 1


# Integration Tests
class TestCacheIntegration:
    """Integration tests for caching system."""
    
    def test_end_to_end_search_with_cache(self, app, project, sample_results):
        """Test complete search with caching workflow."""
        with app.app_context():
            cache_manager = SearchCacheManager()
            
            # Mock the search manager
            call_count = 0
            def mock_search(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return sample_results
            
            cache_manager.search_manager.search = mock_search
            
            # First search - should call backend
            results1, cached1 = cache_manager.search_with_cache(
                project.id, 'test query'
            )
            assert call_count == 1
            assert not cached1
            assert len(results1) == 2
            
            # Second search - should use cache
            results2, cached2 = cache_manager.search_with_cache(
                project.id, 'test query'
            )
            assert call_count == 1  # No additional call
            assert cached2
            assert len(results2) == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
