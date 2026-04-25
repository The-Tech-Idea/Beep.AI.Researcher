"""
Search Provider Base Classes and Models

Provides abstract base classes and data models for implementing search providers
across different academic and web search sources.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import json

from app.core.time_utils import utcnow_naive


class SearchResultType(Enum):
    """Types of search results"""
    JOURNAL_ARTICLE = "journal_article"
    PREPRINT = "preprint"
    CONFERENCE_PAPER = "conference_paper"
    BOOK = "book"
    BOOK_CHAPTER = "book_chapter"
    DATASET = "dataset"
    THESIS = "thesis"
    REPORT = "report"
    UNKNOWN = "unknown"


class AccessType(Enum):
    """Document access level"""
    OPEN_ACCESS = "open_access"
    CLOSED = "closed"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


class ProviderType(Enum):
    """Search provider types"""
    PUBMED = "pubmed"
    ARXIV = "arxiv"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    CROSSREF = "crossref"
    OPENACCESSBUTTON = "openaccessbutton"
    IEEE = "ieee"
    JSTOR = "jstor"
    LOCAL = "local"
    OPEN_LIBRARY = "open_library"
    GOOGLE_BOOKS = "google_books"
    UNKNOWN = "unknown"


@dataclass
class SearchResult:
    """Normalized search result from any provider"""
    
    id: str                                # Unique ID (provider:source_id)
    title: str                             # Article/document title
    authors: List[str]                     # List of author names
    abstract: str                          # Abstract text
    source: str                            # Provider name (pubmed, arxiv, etc)
    source_id: str                         # ID in source system
    url: str                               # Link to source
    pdf_url: Optional[str] = None          # Direct PDF link if available
    publication_date: Optional[str] = None # Publication date (YYYY-MM-DD)
    result_type: SearchResultType = SearchResultType.UNKNOWN
    access_type: AccessType = AccessType.UNKNOWN
    citation_count: Optional[int] = None   # Number of citations (if available)
    keywords: List[str] = field(default_factory=list)  # Subject keywords/tags
    journal: Optional[str] = None          # Journal name if applicable
    volume: Optional[str] = None           # Journal volume
    issue: Optional[str] = None            # Journal issue
    pages: Optional[str] = None            # Page range
    doi: Optional[str] = None              # Digital Object Identifier
    metadata: Dict[str, Any] = field(default_factory=dict)  # Provider-specific data
    retrieved_at: datetime = field(default_factory=utcnow_naive)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization"""
        data = asdict(self)
        
        # Convert enums to strings
        data['result_type'] = self.result_type.value
        data['access_type'] = self.access_type.value
        
        # Convert datetime to ISO format
        if self.retrieved_at:
            data['retrieved_at'] = self.retrieved_at.isoformat()
        
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SearchResult':
        """Create from dict"""
        # Convert string enums back to enum
        if isinstance(data.get('result_type'), str):
            data['result_type'] = SearchResultType(data['result_type'])
        if isinstance(data.get('access_type'), str):
            data['access_type'] = AccessType(data['access_type'])
        
        # Convert ISO datetime string to datetime
        if isinstance(data.get('retrieved_at'), str):
            data['retrieved_at'] = datetime.fromisoformat(data['retrieved_at'])
        
        return cls(**data)


@dataclass
class SearchFilter:
    """Search filter criteria"""
    from_date: Optional[str] = None        # YYYY-MM-DD
    to_date: Optional[str] = None          # YYYY-MM-DD
    publication_type: Optional[str] = None # journal_article, preprint, etc
    language: Optional[str] = None         # ISO 639-1 code (en, de, etc)
    open_access_only: bool = False         # Filter to open access only
    max_citation_count: Optional[int] = None
    min_citation_count: Optional[int] = None
    custom_filters: Dict[str, Any] = field(default_factory=dict)


class AbstractSearchProvider(ABC):
    """
    Base class for all search providers.
    
    Subclasses must implement search(), get_metadata(), and is_available() methods.
    """
    
    def __init__(self, provider_type: ProviderType, api_key: Optional[str] = None,
                 rate_limit: int = 100, timeout: int = 30):
        """
        Initialize search provider.
        
        Args:
            provider_type: Type of provider (PUBMED, ARXIV, etc)
            api_key: API key for authentication (if required)
            rate_limit: Requests per hour limit
            timeout: Request timeout in seconds
        """
        self.provider_type = provider_type
        self.name = provider_type.value
        self.api_key = api_key
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.last_request: Optional[datetime] = None
        self.request_count = 0
        self.error_count = 0
        self.last_error: Optional[str] = None
    
    @abstractmethod
    def search(self, query: str, filters: Optional[SearchFilter] = None,
               limit: int = 20) -> List[SearchResult]:
        """
        Search the provider for results matching query.
        
        Args:
            query: Search query string
            filters: Optional search filters (date range, type, etc)
            limit: Maximum number of results to return
        
        Returns:
            List of normalized SearchResult objects
        
        Raises:
            ConnectionError: If unable to connect to provider
            ValueError: If query is invalid
        """
        pass
    
    @abstractmethod
    def get_metadata(self, source_id: str) -> Optional[Dict]:
        """
        Fetch full metadata for a specific source ID.
        
        Args:
            source_id: Provider-specific document ID
        
        Returns:
            Metadata dictionary or None if not found
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if provider API is accessible.
        
        Returns:
            True if provider is available, False if down
        """
        pass
    
    def apply_rate_limit(self):
        """Apply rate limiting between requests"""
        if self.last_request is None:
            return
        
        time_since_last = (utcnow_naive() - self.last_request).total_seconds()
        min_interval = 3600 / self.rate_limit  # seconds between requests
        
        if time_since_last < min_interval:
            import time
            time.sleep(min_interval - time_since_last)
    
    def record_request(self, success: bool = True, error: Optional[str] = None):
        """Record request for rate limiting and error tracking"""
        self.last_request = utcnow_naive()
        self.request_count += 1
        
        if not success:
            self.error_count += 1
            self.last_error = error
    
    def get_stats(self) -> Dict[str, Any]:
        """Get provider statistics"""
        return {
            'provider': self.name,
            'request_count': self.request_count,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'last_request': self.last_request.isoformat() if self.last_request else None
        }


class LocalSearchProvider(AbstractSearchProvider):
    """
    Local search provider for existing documents in database.
    Searches documents already imported into projects.
    """
    
    def __init__(self):
        super().__init__(ProviderType.LOCAL, rate_limit=1000, timeout=5)
    
    def search(self, query: str, filters: Optional[SearchFilter] = None,
               limit: int = 20) -> List[SearchResult]:
        """Search local documents using full-text search"""
        from flask import current_app
        
        if not query or len(query.strip()) < 2:
            return []
        
        try:
            # Import here to avoid circular imports
            from app.models import Document
            
            # Full-text search on title and abstract
            search_pattern = f"%{query}%"
            results = Document.query.filter(
                db.or_(
                    Document.title.ilike(search_pattern),
                    Document.abstract.ilike(search_pattern)
                )
            ).limit(limit).all()
            
            # Convert to SearchResult
            search_results = []
            for doc in results:
                result = SearchResult(
                    id=f"local:{doc.id}",
                    title=doc.title,
                    authors=doc.authors or [],
                    abstract=doc.abstract or "",
                    source="local",
                    source_id=str(doc.id),
                    url=f"/documents/{doc.id}",
                    publication_date=doc.publication_date,
                    access_type=AccessType.OPEN_ACCESS,
                    result_type=SearchResultType.JOURNAL_ARTICLE,
                    doi=doc.doi,
                    keywords=doc.keywords or [],
                    metadata={'document_id': doc.id, 'project_id': doc.project_id}
                )
                search_results.append(result)
            
            self.record_request(success=True)
            return search_results
        
        except Exception as e:
            self.record_request(success=False, error=str(e))
            return []
    
    def get_metadata(self, source_id: str) -> Optional[Dict]:
        """Get local document metadata"""
        try:
            from app.database import db
            from app.models import Document
            
            doc_id = int(source_id)
            doc = db.session.get(Document, doc_id)
            
            if doc:
                return {
                    'id': doc.id,
                    'title': doc.title,
                    'authors': doc.authors,
                    'abstract': doc.abstract,
                    'project_id': doc.project_id,
                    'created_at': doc.created_at.isoformat() if doc.created_at else None
                }
            return None
        except Exception:
            return None
    
    def is_available(self) -> bool:
        """Local search is always available"""
        return True
