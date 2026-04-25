"""Library sources for web search and academic databases (Phase 2.2)."""
from app.database import db
from app.core.time_utils import utcnow_naive


class LibrarySource(db.Model):
    """Configured library source for search operations (PubMed, arXiv, Semantic Scholar, etc.)."""
    __tablename__ = 'library_sources'
    __table_args__ = (db.UniqueConstraint('project_id', 'name', name='uq_source_name_per_project'),)

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    
    # Source identification
    name = db.Column(db.String(255), nullable=False)  # e.g., "PubMed Central", "arXiv", "Custom API"
    source_type = db.Column(db.String(50), nullable=False)  # pubmed | arxiv | semantic_scholar | crossref | custom
    description = db.Column(db.Text)  # User-friendly description
    
    # Connection details
    api_endpoint = db.Column(db.String(512))  # Base URL for API (null for built-in sources)
    api_key = db.Column(db.String(512))  # API key (encrypted at rest via column property)
    auth_token = db.Column(db.String(512))  # Auth token (encrypted at rest)
    
    # Configuration
    rate_limit_per_hour = db.Column(db.Integer, default=100)  # Requests per hour
    timeout_seconds = db.Column(db.Integer, default=30)  # Request timeout
    headers_json = db.Column(db.Text)  # JSON-encoded custom headers
    
    # Status tracking
    is_active = db.Column(db.Boolean, default=True)
    is_available = db.Column(db.Boolean, default=False)  # Last health check result
    last_health_check = db.Column(db.DateTime)  # Last time we verified availability
    last_error = db.Column(db.Text)  # Last error message
    
    # Import configuration
    auto_import = db.Column(db.Boolean, default=False)  # Auto-import search results
    max_results_per_query = db.Column(db.Integer, default=50)
    min_confidence = db.Column(db.Float, default=0.0)  # Min relevance score (0.0-1.0)
    
    # Statistics
    request_count = db.Column(db.Integer, default=0)  # Total requests made
    error_count = db.Column(db.Integer, default=0)  # Total errors
    import_count = db.Column(db.Integer, default=0)  # Results imported
    
    # Metadata
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    
    # Relationships
    project = db.relationship('ResearchProject', backref='library_sources')
    connections = db.relationship('SourceConnection', backref='source', cascade='all, delete-orphan')
    import_logs = db.relationship('SourceImportLog', backref='source', cascade='all, delete-orphan')
    
    def to_dict(self, include_sensitive=False):
        """Convert to dict, optionally excluding sensitive data."""
        result = {
            'id': self.id,
            'project_id': self.project_id,
            'name': self.name,
            'source_type': self.source_type,
            'description': self.description,
            'is_active': self.is_active,
            'is_available': self.is_available,
            'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None,
            'auto_import': self.auto_import,
            'max_results_per_query': self.max_results_per_query,
            'rate_limit_per_hour': self.rate_limit_per_hour,
            'timeout_seconds': self.timeout_seconds,
            'request_count': self.request_count,
            'error_count': self.error_count,
            'import_count': self.import_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_sensitive:
            result.update({
                'api_endpoint': self.api_endpoint,
                'api_key': self.api_key,
                'auth_token': self.auth_token,
                'headers_json': self.headers_json,
            })
        
        return result

    def to_dict_summary(self):
        """Brief summary for list views."""
        return {
            'id': self.id,
            'name': self.name,
            'source_type': self.source_type,
            'is_active': self.is_active,
            'is_available': self.is_available,
            'request_count': self.request_count,
            'import_count': self.import_count,
        }


class SourceConnection(db.Model):
    """Test connection history for a library source."""
    __tablename__ = 'source_connections'

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('library_sources.id'), nullable=False)
    
    # Connection test result
    is_successful = db.Column(db.Boolean, default=False)
    status_code = db.Column(db.Integer)  # HTTP status code if applicable
    response_time_ms = db.Column(db.Float)  # Response time in milliseconds
    error_message = db.Column(db.Text)  # Error details if failed
    
    # Test details
    test_query = db.Column(db.String(255))  # What we tested
    test_result_count = db.Column(db.Integer, default=0)  # Results returned
    
    tested_at = db.Column(db.DateTime, default=utcnow_naive)
    
    def to_dict(self):
        return {
            'id': self.id,
            'source_id': self.source_id,
            'is_successful': self.is_successful,
            'status_code': self.status_code,
            'response_time_ms': self.response_time_ms,
            'test_result_count': self.test_result_count,
            'tested_at': self.tested_at.isoformat() if self.tested_at else None,
        }


class SourceImportLog(db.Model):
    """Log of documents imported from a library source."""
    __tablename__ = 'source_import_logs'

    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey('library_sources.id'), nullable=False)
    
    # Import details
    query = db.Column(db.String(512), nullable=False)  # Search query used
    results_found = db.Column(db.Integer, default=0)  # Total results
    documents_imported = db.Column(db.Integer, default=0)  # Successfully imported
    documents_skipped = db.Column(db.Integer, default=0)  # Already exists, filtered, etc.
    
    # Status
    status = db.Column(db.String(50), default='pending')  # pending | in_progress | completed | failed
    error_message = db.Column(db.Text)  # Error if failed
    
    # Performance
    import_duration_seconds = db.Column(db.Float)  # Time taken
    
    # Metadata
    imported_at = db.Column(db.DateTime, default=utcnow_naive)
    completed_at = db.Column(db.DateTime)
    
    def to_dict(self):
        return {
            'id': self.id,
            'source_id': self.source_id,
            'query': self.query,
            'results_found': self.results_found,
            'documents_imported': self.documents_imported,
            'documents_skipped': self.documents_skipped,
            'status': self.status,
            'import_duration_seconds': self.import_duration_seconds,
            'imported_at': self.imported_at.isoformat() if self.imported_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }
