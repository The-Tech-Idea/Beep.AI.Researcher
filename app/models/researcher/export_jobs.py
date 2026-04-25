"""ExportJob model — tracks asynchronous export bundle generation (Phase 05)."""
from __future__ import annotations

from app.database import db
from app.core.time_utils import utcnow_naive


class ExportJob(db.Model):
    """Records an export bundle request and its outcome.

    ``format`` values: ``markdown_zip``, ``bibtex``
    ``status`` values: ``pending``, ``running``, ``done``, ``failed``
    ``artifact_path`` is a filesystem path (relative to project storage root) or
    an absolute temp path; cleared on deletion.
    """

    __tablename__ = "export_jobs"
    __table_args__ = (
        db.Index("ix_export_jobs_project_id", "project_id"),
    )

    FORMAT_MARKDOWN_ZIP = "markdown_zip"
    FORMAT_BIBTEX = "bibtex"
    FORMAT_VALUES = (FORMAT_MARKDOWN_ZIP, FORMAT_BIBTEX)

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("research_projects.id"), nullable=False
    )
    # Optional: pin the export to a specific manuscript
    manuscript_id = db.Column(
        db.Integer, db.ForeignKey("manuscripts.id", ondelete="SET NULL"), nullable=True
    )
    format = db.Column(db.String(30), nullable=False, default=FORMAT_MARKDOWN_ZIP)
    status = db.Column(db.String(20), nullable=False, default=STATUS_PENDING)
    artifact_path = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "manuscript_id": self.manuscript_id,
            "format": self.format,
            "status": self.status,
            "artifact_path": self.artifact_path,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
