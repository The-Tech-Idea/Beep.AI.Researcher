"""ResearcherDocument model — standalone document storage per project."""
from app.database import db
from app.core.time_utils import utcnow_naive


class ResearcherDocument(db.Model):
    """Document stored in a research project."""
    __tablename__ = 'researcher_documents'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    mime_type = db.Column(db.String(100), default='application/octet-stream')
    text_content = db.Column(db.Text)  # Extracted text for search
    file_size = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    # Source metadata for imports (Phase 2.4)
    source_type = db.Column(db.String(50))  # web_search | pubmed | arxiv | etc.
    source_id = db.Column(db.String(255))  # Original provider result id
    source_url = db.Column(db.String(1024))  # Original article / landing page URL
    imported_at = db.Column(db.DateTime)

    # Phase C.4 — PHI / student-data flags (medical / education sectors)
    phi_detected = db.Column(db.Boolean, default=False)
    phi_redacted = db.Column(db.Boolean, default=False)
    phi_backup_json = db.Column(db.JSON)         # {'original_text': '...', 'redacted_at': '...'}
    contains_student_data = db.Column(db.Boolean, default=False)

    # Phase C.4 — Real-estate geo-fields
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    parcel_id = db.Column(db.String(100))
    property_address = db.Column(db.String(512))

    # Phase C.4 — Ingest/processing status
    status = db.Column(db.String(30), default='pending')  # pending | processing | ready | error
    archived_at = db.Column(db.DateTime)
    deleted_at = db.Column(db.DateTime)

    # Document-manager extraction metadata
    parser_name = db.Column(db.String(100))
    parser_version = db.Column(db.String(100))
    extraction_status = db.Column(db.String(30), default='pending')
    extraction_quality = db.Column(db.String(50))
    page_count = db.Column(db.Integer)
    table_count = db.Column(db.Integer)
    image_count = db.Column(db.Integer)
    formula_count = db.Column(db.Integer)
    chart_count = db.Column(db.Integer)
    audio_duration_seconds = db.Column(db.Float)
    document_hash = db.Column(db.String(64))
    language = db.Column(db.String(50))
    extraction_warnings = db.Column(db.Text)

    # AI Server RAG indexing status
    rag_document_id = db.Column(db.String(255))
    rag_collection_id = db.Column(db.String(255))
    rag_content_hash = db.Column(db.String(64))
    rag_sync_status = db.Column(db.String(30), default='not_indexed')
    # not_indexed | indexed | failed | unavailable
    rag_sync_message = db.Column(db.Text)
    rag_synced_at = db.Column(db.DateTime)

    project = db.relationship('ResearchProject', backref='documents')

    @property
    def name(self):
        """Display name — the original filename."""
        return self.filename or ''

    @property
    def file_type(self):
        """File extension without dot, e.g. 'pdf', 'txt'."""
        from pathlib import Path
        if not self.filename:
            return 'file'
        return Path(self.filename).suffix.lower().lstrip('.') or 'file'

    @property
    def size_formatted(self):
        """Human-readable file size."""
        size = self.file_size or 0
        for unit in ('B', 'KB', 'MB', 'GB'):
            if size < 1024:
                return f"{size:.1f} {unit}" if unit != 'B' else f"{size} B"
            size /= 1024
        return f"{size:.1f} TB"

    def to_dict(self):
        return {
            'id': self.id, 'project_id': self.project_id, 'filename': self.filename,
            'name': self.name, 'file_type': self.file_type, 'size_formatted': self.size_formatted,
            'file_path': self.file_path, 'mime_type': self.mime_type,
            'file_size': self.file_size,
            'status': self.status,
            'archived_at': self.archived_at.isoformat() if self.archived_at else None,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'parser_name': self.parser_name,
            'parser_version': self.parser_version,
            'extraction_status': self.extraction_status,
            'extraction_quality': self.extraction_quality,
            'page_count': self.page_count,
            'table_count': self.table_count,
            'image_count': self.image_count,
            'formula_count': self.formula_count,
            'chart_count': self.chart_count,
            'audio_duration_seconds': self.audio_duration_seconds,
            'document_hash': self.document_hash,
            'language': self.language,
            'extraction_warnings': self.extraction_warnings,
            'rag_document_id': self.rag_document_id,
            'rag_collection_id': self.rag_collection_id,
            'rag_content_hash': self.rag_content_hash,
            'rag_sync_status': self.rag_sync_status,
            'rag_sync_message': self.rag_sync_message,
            'rag_synced_at': self.rag_synced_at.isoformat() if self.rag_synced_at else None,
            'phi_detected': self.phi_detected,
            'phi_redacted': self.phi_redacted,
            'contains_student_data': self.contains_student_data,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'parcel_id': self.parcel_id,
            'property_address': self.property_address,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'source_type': self.source_type,
            'source_id': self.source_id,
            'source_url': self.source_url,
            'imported_at': self.imported_at.isoformat() if self.imported_at else None,
        }
