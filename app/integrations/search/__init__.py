"""
Search Integration Package

Provides unified search across multiple academic and local sources.

Example:
    from app.integrations.search import search_manager, SearchResult
    
    manager = search_manager.get_search_manager()
    results = manager.search("machine learning", sources=["local", "arxiv"])
"""

from .base import (
    SearchResult, SearchResultType, AccessType, SearchFilter,
    ProviderType, AbstractSearchProvider, LocalSearchProvider
)
from .search_manager import SearchManager, get_search_manager

__all__ = [
    # Data Models
    'SearchResult',
    'SearchResultType',
    'AccessType',
    'SearchFilter',
    'ProviderType',
    # Providers
    'AbstractSearchProvider',
    'LocalSearchProvider',
    # Manager
    'SearchManager',
    'get_search_manager',
]
