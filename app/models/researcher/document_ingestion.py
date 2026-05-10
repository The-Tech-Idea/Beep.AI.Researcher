"""Document ingestion state for local hash/upsert tracking."""
from __future__ import annotations

from app.core.time_utils import utcnow_naive
from app.database import db


class DocumentIngestionState(db.Model):
    """Tracks Researcher-side ingestion state before and after AI Server sync."""

    __tablename__ = "document_ingestion_states"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer,
        db.ForeignKey("researcher_documents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    project_id = db.Column(db.Integer, db.ForeignKey("research_projects.id"), nullable=False, index=True)
    document_hash = db.Column(db.String(64), nullable=False, index=True)
    content_hash = db.Column(db.String(64), index=True)
    rag_document_id = db.Column(db.String(255), index=True)
    rag_collection_id = db.Column(db.String(255), index=True)
    ingestion_status = db.Column(db.String(30), default="new", index=True)
    extraction_status = db.Column(db.String(30), default="pending")
    rag_sync_status = db.Column(db.String(30), default="not_indexed")
    duplicate_of_document_id = db.Column(db.Integer, db.ForeignKey("researcher_documents.id"))
    last_error = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    last_synced_at = db.Column(db.DateTime)

    document = db.relationship(
        "ResearcherDocument",
        foreign_keys=[document_id],
        backref=db.backref("ingestion_state", uselist=False, cascade="all, delete-orphan"),
    )
    duplicate_of = db.relationship("ResearcherDocument", foreign_keys=[duplicate_of_document_id])

    def to_dict(self):
        return {
            "id": self.id,
            "document_id": self.document_id,
            "project_id": self.project_id,
            "document_hash": self.document_hash,
            "content_hash": self.content_hash,
            "rag_document_id": self.rag_document_id,
            "rag_collection_id": self.rag_collection_id,
            "ingestion_status": self.ingestion_status,
            "extraction_status": self.extraction_status,
            "rag_sync_status": self.rag_sync_status,
            "duplicate_of_document_id": self.duplicate_of_document_id,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
        }
