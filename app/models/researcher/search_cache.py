"""Search result caching and indexing models (Phase 2.5)."""
from datetime import datetime, timedelta, UTC
from app.database import db
from sqlalchemy import Text
import hashlib
import json


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class SearchCache(db.Model):
    """Cached search results with TTL-based expiration (24 hours)."""
    __tablename__ = 'search_cache'
    __table_args__ = (
        db.UniqueConstraint('project_id', 'provider', 'query_hash', name='uq_cache_lookup'),
        db.Index('idx_cache_expiration', 'expires_at'),
        db.Index('idx_cache_project', 'project_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    
    # Cache key components
    provider = db.Column(db.String(50), nullable=False)  # pubmed | arxiv | semantic_scholar | local
    search_query = db.Column('query', db.Text, nullable=False)  # Original query string
    query_hash = db.Column(db.String(64), nullable=False)  # SHA-256 hash of (query + filters)
    
    # Filter snapshot (JSON) to detect cache invalidation
    filters_json = db.Column(db.Text)  # JSON-encoded SearchFilter
    
    # Cached results (JSON array of SearchResult dicts)
    results_json = db.Column(Text, nullable=False)  # Serialized SearchResult list
    result_count = db.Column(db.Integer, default=0)  # Number of results cached
    
    # Cache metadata
    created_at = db.Column(db.DateTime, default=_utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)  # 24 hours from now
    
    # Hit tracking
    hit_count = db.Column(db.Integer, default=0)  # Number of times cache was hit
    last_accessed = db.Column(db.DateTime)  # Last time this cache was used
    
    # Relationships
    project = db.relationship('ResearchProject', backref='search_caches')

    def __getattribute__(self, name):
        # Preserve instance-level compatibility for existing code/tests that access `obj.query`.
        if name == 'query':
            return object.__getattribute__(self, 'search_query')
        return super().__getattribute__(name)

    def __setattr__(self, name, value):
        # Preserve instance-level compatibility for existing code/tests that assign `obj.query`.
        if name == 'query':
            name = 'search_query'
        super().__setattr__(name, value)
    
    def __init__(self, project_id, provider, query, results, filters_json=None):
        """Initialize cache entry with 24-hour TTL."""
        self.project_id = project_id
        self.provider = provider
        self.search_query = query
        self.filters_json = filters_json
        self.result_count = len(results) if results else 0
        self.results_json = json.dumps([r.to_dict() if hasattr(r, 'to_dict') else r for r in results])
        
        # Set expiration to 24 hours from now
        self.created_at = _utcnow()
        self.expires_at = self.created_at + timedelta(hours=24)
        
        # Generate query hash from provider + query + filters (provider-aware)
        hash_input = f"{provider}:{query}:{filters_json or ''}"
        self.query_hash = hashlib.sha256(hash_input.encode()).hexdigest()
    
    def is_expired(self):
        """Check if cache entry has expired."""
        return _utcnow() > self.expires_at
    
    def record_hit(self):
        """Record a cache hit and update access time."""
        self.hit_count += 1
        self.last_accessed = _utcnow()
    
    def get_results(self):
        """Return deserialized search results."""
        return json.loads(self.results_json)
    
    def to_dict(self):
        """Convert to dict for response."""
        return {
            'id': self.id,
            'project_id': self.project_id,
            'provider': self.provider,
            'query': self.search_query,
            'result_count': self.result_count,
            'hit_count': self.hit_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'is_expired': self.is_expired(),
        }


class SearchIndex(db.Model):
    """Index of all search results for analytics and faceted search."""
    __tablename__ = 'search_index'
    __table_args__ = (
        db.Index('idx_index_project', 'project_id'),
        db.Index('idx_index_provider', 'provider'),
        db.Index('idx_index_date', 'created_at'),
        db.Index('idx_index_facets', 'project_id', 'provider', 'source'),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    
    # Result identity
    source_id = db.Column(db.String(255), nullable=False)  # Provider-specific ID
    provider = db.Column(db.String(50), nullable=False)  # pubmed | arxiv | semantic_scholar | local
    title = db.Column(db.Text, nullable=False)
    
    # Result metadata for faceting
    authors = db.Column(db.Text)  # Comma-separated or JSON list
    publication_date = db.Column(db.DateTime)  # Facet by date
    source = db.Column(db.String(255))  # Journal name or conference
    result_type = db.Column(db.String(50))  # journal_article | preprint | conference_paper, etc.
    access_type = db.Column(db.String(50))  # open_access | closed | restricted
    citation_count = db.Column(db.Integer, default=0)  # For sorting
    
    # Full result data (JSON)
    result_json = db.Column(db.Text, nullable=False)  # Full SearchResult dict
    
    # Search tracking
    search_query = db.Column('query', db.Text)  # Query that found this result
    first_found_at = db.Column(db.DateTime, default=_utcnow)  # When first indexed
    found_count = db.Column(db.Integer, default=1)  # How many searches found this result
    
    # Metadata
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)
    
    # Relationships
    project = db.relationship('ResearchProject', backref='search_indexes')

    def __getattribute__(self, name):
        if name == 'query':
            return object.__getattribute__(self, 'search_query')
        return super().__getattribute__(name)

    def __setattr__(self, name, value):
        if name == 'query':
            name = 'search_query'
        super().__setattr__(name, value)
    
    def __init__(self, project_id, source_id, provider, result, query=None):
        """Initialize index entry from a SearchResult."""
        self.project_id = project_id
        self.source_id = source_id
        self.provider = provider
        self.search_query = query
        self.found_count = 1
        
        # Extract metadata from result dict/object
        if hasattr(result, 'to_dict'):
            result_data = result.to_dict()
        else:
            result_data = result
        
        self.title = result_data.get('title', '')
        self.authors = json.dumps(result_data.get('authors', [])) if result_data.get('authors') else None
        
        # Parse publication date if string
        pub_date = result_data.get('publication_date')
        if pub_date and isinstance(pub_date, str):
            try:
                self.publication_date = datetime.fromisoformat(pub_date)
            except (ValueError, TypeError):
                self.publication_date = None
        else:
            self.publication_date = pub_date
        
        self.source = result_data.get('journal') or result_data.get('source', '')
        self.result_type = result_data.get('result_type', 'unknown')
        self.access_type = result_data.get('access_type', 'unknown')
        self.citation_count = result_data.get('citation_count', 0) or 0
        
        # Store complete result as JSON
        self.result_json = json.dumps(result_data, default=str)
    
    def record_find(self, query=None):
        """Record that this result was found in a new search."""
        self.found_count += 1
        self.updated_at = _utcnow()
        if query:
            self.search_query = query
    
    def get_result(self):
        """Return deserialized result."""
        return json.loads(self.result_json)
    
    def to_dict(self):
        """Convert to dict for response."""
        authors = []
        if self.authors:
            try:
                authors = json.loads(self.authors)
            except (json.JSONDecodeError, TypeError):
                authors = self.authors.split(',')
        
        return {
            'id': self.id,
            'project_id': self.project_id,
            'source_id': self.source_id,
            'provider': self.provider,
            'title': self.title,
            'authors': authors,
            'source': self.source,
            'result_type': self.result_type,
            'access_type': self.access_type,
            'publication_date': self.publication_date.isoformat() if self.publication_date else None,
            'citation_count': self.citation_count,
            'found_count': self.found_count,
            'first_found_at': self.first_found_at.isoformat() if self.first_found_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
