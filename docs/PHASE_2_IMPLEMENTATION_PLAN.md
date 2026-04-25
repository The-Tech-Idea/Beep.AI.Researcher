# Phase 2: Web Search & Academic Libraries - Implementation Plan

**Status**: PLANNING  
**Duration**: 2-3 weeks estimated  
**Start Date**: February 7, 2026  

---

## Phase 2 Overview

### Goal

Integrate external academic and web search capabilities into Beep.AI.Researcher, enabling users to search and import research papers, articles, and data from multiple sources.

### Key Capabilities

✅ Search multiple academic databases (PubMed, arXiv, CrossRef, Semantic Scholar)  
✅ Manage library sources (enable/disable, test connection, track usage)  
✅ Import search results into projects as documents  
✅ Cache and deduplicate results  
✅ Async search operations using Phase 1.3 JobQueue  
✅ Event notifications via Phase 1.1 EventBus  

### Integration with Phase 1

**Uses Phase 1.3 (JobQueue)**:
- Queue search operations as async jobs
- Track search progress and status
- Handle search failures with retries

**Uses Phase 1.1 (EventBus)**:
- Publish search.started event
- Publish search.completed event
- Publish document.imported event

**Uses Phase 1.5 (Configuration)**:
- Feature flag: web_search_enabled
- Configure search providers
- Set rate limits per provider

**Uses Phase 1.2 (Hooks)**:
- Hook for search result processing
- Hook for document import validation

---

## Phase 2 Architecture

### Component Structure

```
app/
├── integrations/
│   └── search/
│       ├── __init__.py
│       ├── base.py                 # AbstractSearchProvider
│       ├── providers/
│       │   ├── __init__.py
│       │   ├── pubmed.py           # PubMed Central API
│       │   ├── arxiv.py            # arXiv.org API
│       │   ├── semantic_scholar.py # Semantic Scholar API
│       │   ├── crossref.py         # CrossRef API
│       │   ├── openaccessbutton.py # Open Access Button
│       │   └── ieee.py             # IEEE Xplore (if available)
│       ├── models.py               # SearchResult dataclass
│       ├── search_manager.py       # SearchManager singleton
│       └── cache.py                # Search result caching
├── models/
│   └── library_source.py           # LibrarySource model
└── routes/
    └── search.py                   # Search API routes

tests/
├── test_search_providers.py        # Provider tests
├── test_search_manager.py          # Manager tests
├── test_search_routes.py           # API tests
└── test_search_integration.py      # E2E tests

docs/
├── SEARCH_PROVIDERS_GUIDE.md       # Implementation guide
├── SEARCH_ROUTES_API.md            # API documentation
└── PHASE_2_COMPLETE.md             # Completion report
```

### Data Flow

```
Route Handler (/search POST)
    ↓
SearchManager.search()
    ↓
    ├─→ LocalSearchProvider (existing documents)
    ├─→ PubMedProvider
    ├─→ ArxivProvider
    └─→ SemanticScholarProvider
    ↓
Deduplicate Results
    ↓
EventBus.publish("search.completed")
    ↓
Cache Results
    ↓
Return to Client
    ↓
(Optional) Import Results via JobQueue
    ↓
EventBus.publish("document.imported")
```

---

## Phase 2.1: Search Provider System

### 1. Base Provider Class

**File**: `app/integrations/search/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class SearchResultType(Enum):
    JOURNAL_ARTICLE = "journal_article"
    PREPRINT = "preprint"
    CONFERENCE_PAPER = "conference_paper"
    BOOK = "book"
    BOOK_CHAPTER = "book_chapter"
    DATASET = "dataset"
    UNKNOWN = "unknown"

class AccessType(Enum):
    OPEN_ACCESS = "open_access"
    CLOSED = "closed"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"

@dataclass
class SearchResult:
    """Normalized search result from any provider"""
    id: str                                # Unique ID (provider_type:id)
    title: str
    authors: List[str]
    abstract: str
    source: str                            # Provider name (pubmed, arxiv, etc)
    source_id: str                         # ID in source system
    url: str
    pdf_url: Optional[str] = None
    publication_date: Optional[str] = None
    result_type: SearchResultType = SearchResultType.UNKNOWN
    access_type: AccessType = AccessType.UNKNOWN
    citation_count: Optional[int] = None
    keywords: List[str] = None
    metadata: Dict[str, Any] = None        # Provider-specific metadata
    retrieved_at: datetime = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization"""
        ...

class AbstractSearchProvider(ABC):
    """Base class for all search providers"""
    
    def __init__(self, name: str, api_key: Optional[str] = None, 
                 rate_limit: int = 100, timeout: int = 30):
        self.name = name
        self.api_key = api_key
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.last_request = None
        self.request_count = 0
        
    @abstractmethod
    def search(self, query: str, filters: Optional[Dict] = None, 
               limit: int = 20) -> List[SearchResult]:
        """Search the provider for results"""
        pass
    
    @abstractmethod
    def get_metadata(self, result_id: str) -> Optional[Dict]:
        """Fetch full metadata for a result"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider API is available"""
        pass
    
    def apply_rate_limit(self):
        """Apply rate limiting between requests"""
        ...
    
    def normalize_result(self, raw_result: Dict) -> SearchResult:
        """Convert provider-specific result to SearchResult"""
        ...
```

### 2. PubMed Provider

**File**: `app/integrations/search/providers/pubmed.py`

```python
import requests
from typing import List, Optional, Dict
from ..base import AbstractSearchProvider, SearchResult, SearchResultType, AccessType

class PubMedProvider(AbstractSearchProvider):
    """PubMed Central API provider"""
    
    BASE_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/webenv"
    SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    
    def __init__(self, email: str):
        super().__init__("pubmed")
        self.email = email  # PubMed requires email for access
    
    def search(self, query: str, filters: Optional[Dict] = None, 
               limit: int = 20) -> List[SearchResult]:
        """Search PubMed Central (open access articles only)"""
        self.apply_rate_limit()
        
        params = {
            "db": "pmc",
            "term": f"{query} AND open access[filter]",
            "retmax": limit,
            "rettype": "json",
            "tool": "BeepAI",
            "email": self.email
        }
        
        # Apply filters if provided
        if filters:
            if filters.get("from_date"):
                params["mindate"] = filters["from_date"]
            if filters.get("to_date"):
                params["maxdate"] = filters["to_date"]
        
        response = requests.get(self.SEARCH_URL, params=params, 
                               timeout=self.timeout)
        response.raise_for_status()
        
        results = []
        data = response.json()
        
        for article_id in data["esearchresult"].get("idlist", [])[:limit]:
            result = self._fetch_article(article_id)
            if result:
                results.append(result)
        
        return results
    
    def _fetch_article(self, pmid: str) -> Optional[SearchResult]:
        """Fetch article details"""
        ...
    
    def is_available(self) -> bool:
        """Check if PubMed API is accessible"""
        ...
```

### 3. arXiv Provider

**File**: `app/integrations/search/providers/arxiv.py`

### 4. Semantic Scholar Provider

**File**: `app/integrations/search/providers/semantic_scholar.py`

### 5. CrossRef Provider

**File**: `app/integrations/search/providers/crossref.py`

### 6. Local Provider (Search Existing Documents)

**File**: `app/integrations/search/providers/local.py`

- Searches documents already in project
- Uses SQLite full-text search
- No API calls or rate limits

---

## Phase 2.2: Search Manager & Caching

### SearchManager Singleton

**File**: `app/integrations/search/search_manager.py`

```python
from typing import List, Dict, Optional
from threading import Lock
from ..base import SearchResult, AbstractSearchProvider
from app.config import get_config, is_feature_enabled

class SearchManager:
    """Centralized search management (singleton)"""
    
    _instance = None
    _lock = Lock()
    
    def __init__(self):
        self.providers: Dict[str, AbstractSearchProvider] = {}
        self.cache: Dict[str, List[SearchResult]] = {}
        self.config = get_config()
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    cls._instance._initialize_providers()
        return cls._instance
    
    def search(self, query: str, sources: List[str] = None, 
               filters: Dict = None, limit: int = 20) -> List[SearchResult]:
        """Search multiple sources and deduplicate results"""
        
        if not is_feature_enabled("web_search_enabled"):
            sources = ["local"]  # Only local search if disabled
        
        if sources is None:
            sources = ["local"]  # Default to local only
        
        all_results = []
        
        for source in sources:
            if source not in self.providers:
                continue
            
            try:
                results = self.providers[source].search(query, filters, limit)
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Error searching {source}: {e}")
                # Continue with other sources
        
        # Deduplicate results
        deduped = self._deduplicate(all_results)
        
        # Sort by relevance (citation count, date)
        sorted_results = self._sort_results(deduped, limit)
        
        return sorted_results
    
    def _deduplicate(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicate results based on title/DOI"""
        ...
    
    def _sort_results(self, results: List[SearchResult], 
                     limit: int) -> List[SearchResult]:
        """Sort results by relevance"""
        ...
```

### Result Caching

**File**: `app/integrations/search/cache.py`

- Cache search results with TTL (24 hours default)
- Prevent duplicate searches
- Track cache hits/misses

---

## Phase 2.3: Library Source Model

### Database Model

**File**: `app/models/library_source.py`

```python
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from enum import Enum

db = SQLAlchemy()

class LibrarySourceType(Enum):
    PUBMED = "pubmed"
    ARXIV = "arxiv"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    CROSSREF = "crossref"
    OPENACCESSBUTTON = "openaccessbutton"
    IEEE = "ieee"
    JSTOR = "jstor"

class LibrarySource(db.Model):
    """Library source configuration"""
    
    __tablename__ = 'library_sources'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    source_type = db.Column(db.Enum(LibrarySourceType), nullable=False)
    api_key = db.Column(db.String(1000), nullable=True, encrypted=True)
    is_enabled = db.Column(db.Boolean, default=True)
    rate_limit = db.Column(db.Integer, default=100)  # requests/hour
    timeout = db.Column(db.Integer, default=30)      # seconds
    last_sync = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(db.String(1000), nullable=True)
    request_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    config = db.Column(db.JSON, default={})  # Provider-specific config
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, 
                          onupdate=datetime.utcnow)
    
    def to_dict(self, include_api_key=False):
        """Convert to dict for API response"""
        data = {
            'id': self.id,
            'name': self.name,
            'source_type': self.source_type.value,
            'is_enabled': self.is_enabled,
            'rate_limit': self.rate_limit,
            'timeout': self.timeout,
            'last_sync': self.last_sync,
            'last_error': self.last_error,
            'request_count': self.request_count,
            'error_count': self.error_count,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        if include_api_key:
            data['api_key'] = self.api_key
        return data
```

---

## Phase 2.4: Search API Routes

### Admin Routes (Library Source Management)

**File**: `app/routes/admin_search.py`

```python
from flask import Blueprint, request, jsonify
from app.models import LibrarySource
from app.decorators.permissions import require_permission
from app.integrations.search import SearchManager

admin_search = Blueprint('admin_search', __name__, url_prefix='/admin')

@admin_search.route('/library-sources', methods=['GET'])
@require_permission('admin:read')
def list_library_sources():
    """List all library sources"""
    sources = LibrarySource.query.all()
    return jsonify([s.to_dict() for s in sources])

@admin_search.route('/library-sources', methods=['POST'])
@require_permission('admin:write')
def create_library_source():
    """Create new library source"""
    data = request.json
    
    source = LibrarySource(
        name=data['name'],
        source_type=data['source_type'],
        api_key=data.get('api_key'),
        rate_limit=data.get('rate_limit', 100)
    )
    
    db.session.add(source)
    db.session.commit()
    
    return jsonify(source.to_dict()), 201

@admin_search.route('/library-sources/<int:source_id>', methods=['PUT'])
@require_permission('admin:write')
def update_library_source(source_id):
    """Update library source"""
    ...

@admin_search.route('/library-sources/<int:source_id>', methods=['DELETE'])
@require_permission('admin:write')
def delete_library_source(source_id):
    """Delete library source"""
    ...

@admin_search.route('/library-sources/<int:source_id>/test', methods=['POST'])
@require_permission('admin:write')
def test_connection(source_id):
    """Test connection to library source"""
    ...

@admin_search.route('/library-sources/<int:source_id>/status', methods=['GET'])
@require_permission('admin:read')
def get_source_status(source_id):
    """Get source connection status"""
    ...
```

### Search Routes

**File**: `app/routes/projects_search.py`

```python
from flask import Blueprint, request, jsonify
from app.decorators.permissions import require_permission
from app.integrations.search import SearchManager
from app.routes.integration import JobQueueManager, EventBusPublisher
from app.core import JobType

projects_search = Blueprint('projects_search', __name__)

@projects_search.route('/projects/<int:project_id>/search', methods=['POST'])
@require_permission('project:read', 'project')
def search_documents(project_id):
    """
    Search documents (existing + external sources)
    
    POST /projects/123/search
    {
        "query": "machine learning algorithms",
        "sources": ["local", "arxiv", "pubmed"],
        "filters": {
            "from_date": "2020-01-01",
            "publication_type": "journal_article"
        },
        "limit": 20
    }
    """
    data = request.json
    query = data.get('query')
    sources = data.get('sources', ['local'])
    filters = data.get('filters', {})
    limit = data.get('limit', 20)
    
    if not query:
        return {"error": "query required"}, 400
    
    # Publish event
    EventBusPublisher.publish(
        "search.started",
        query=query,
        sources=sources,
        project_id=project_id
    )
    
    # Search
    manager = SearchManager.get_instance()
    results = manager.search(query, sources, filters, limit)
    
    # Publish completion event
    EventBusPublisher.publish(
        "search.completed",
        query=query,
        result_count=len(results),
        project_id=project_id
    )
    
    return jsonify({
        "query": query,
        "sources": sources,
        "result_count": len(results),
        "results": [r.to_dict() for r in results]
    })

@projects_search.route('/projects/<int:project_id>/web-search', methods=['POST'])
@require_permission('project:read', 'project')
def web_search(project_id):
    """
    Explicit academic/web search (external sources only)
    
    POST /projects/123/web-search
    {
        "query": "quantum computing",
        "providers": ["arxiv", "pubmed", "semantic_scholar"],
        "filters": {
            "from_date": "2020-01-01",
            "to_date": "2024-12-31",
            "open_access_only": true
        },
        "limit": 50
    }
    """
    data = request.json
    query = data.get('query')
    providers = data.get('providers', ['arxiv', 'pubmed'])
    filters = data.get('filters', {})
    limit = data.get('limit', 50)
    
    if not query:
        return {"error": "query required"}, 400
    
    # Perform search
    manager = SearchManager.get_instance()
    results = manager.search(query, providers, filters, limit)
    
    return jsonify({
        "query": query,
        "providers": providers,
        "result_count": len(results),
        "results": [r.to_dict() for r in results]
    })

@projects_search.route('/projects/<int:project_id>/search-results/<result_id>/import', methods=['POST'])
@require_permission('project:write', 'project')
def import_search_result(project_id, result_id):
    """
    Import search result as document
    
    POST /projects/123/search-results/arxiv:2401.00123/import
    {
        "download_pdf": true
    }
    """
    download_pdf = request.json.get('download_pdf', True) if request.json else True
    
    # Queue import job
    job_id = JobQueueManager.queue_job(
        job_type=JobType.IMPORT_SEARCH_RESULT.value,
        project_id=project_id,
        result_id=result_id,
        download_pdf=download_pdf
    )
    
    return jsonify({
        "job_id": job_id,
        "status": "queued"
    }), 202
```

---

## Phase 2.5: Testing Strategy

### Unit Tests

**File**: `tests/test_search_providers.py`
- Test each provider independently
- Mock API responses
- Test error handling
- Test result normalization

Example:
```
TestPubMedProvider:
- test_search_success
- test_search_with_filters
- test_search_api_error
- test_rate_limiting
- test_result_normalization
- test_metadata_fetching

TestArxivProvider:
- Similar tests for arXiv
```

### Integration Tests

**File**: `tests/test_search_manager.py`
- Test SearchManager singleton
- Test multi-provider search
- Test result deduplication
- Test caching

### API Tests

**File**: `tests/test_search_routes.py`
- Test search routes
- Test permission checking
- Test query validation
- Test result pagination

### E2E Tests

**File**: `tests/test_search_integration.py`
- End-to-end: search → import → document creation
- Test with real API calls (staging)
- Test error scenarios

---

## Implementation Order

1. **Week 1**
   - [ ] Create base SearchProvider class
   - [ ] Implement PubMed provider
   - [ ] Implement arXiv provider
   - [ ] Create unit tests for providers

2. **Week 2**
   - [ ] Implement SearchManager
   - [ ] Add caching layer
   - [ ] Create LibrarySource model
   - [ ] Create admin routes

3. **Week 3**
   - [ ] Create search API routes
   - [ ] Implement import workflow
   - [ ] Add comprehensive tests
   - [ ] Create documentation
   - [ ] Integration with Phase 1 components

---

## Success Criteria

✅ Search multiple academic databases  
✅ Return normalized, deduplicated results  
✅ Import results as project documents  
✅ 50+ comprehensive tests (all passing)  
✅ Zero breaking changes to Phase 1  
✅ Complete documentation  
✅ Production-ready code  

