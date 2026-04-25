"""ExtractionSchema, ExtractionResult — Elicit-style structured extraction."""
from datetime import datetime
from app.core.time_utils import utcnow_naive
from app.database import db


class ExtractionSchema(db.Model):
    """Structured extraction schema (Elicit-style)."""
    __tablename__ = 'extraction_schemas'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('research_projects.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    schema_json = db.Column(db.Text, nullable=False)  # [{field, type, description}, ...]
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    project = db.relationship('ResearchProject', backref='extraction_schemas')
    results = db.relationship('ExtractionResult', backref='schema', cascade='all, delete-orphan')


class ExtractionResult(db.Model):
    """Single extraction result (one row per document)."""
    __tablename__ = 'extraction_results'

    id = db.Column(db.Integer, primary_key=True)
    schema_id = db.Column(db.Integer, db.ForeignKey('extraction_schemas.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('researcher_documents.id'), nullable=False)
    data_json = db.Column(db.Text, nullable=False)  # Extracted key-value pairs
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    document = db.relationship('ResearcherDocument', backref='extraction_results')
