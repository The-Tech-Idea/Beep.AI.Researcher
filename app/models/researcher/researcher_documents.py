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
