"""Manuscript binder models for the Phase 04 Writing Studio."""
from __future__ import annotations

import json
from typing import List

from app.database import db
from app.core.time_utils import utcnow_naive


class Manuscript(db.Model):
    """Long-form writing container for a research project (Phase 04)."""

    __tablename__ = "manuscripts"
    __table_args__ = (
        db.Index("ix_manuscripts_project_id", "project_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("research_projects.id"), nullable=False
    )
    title = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    # Relationships
    sections = db.relationship(
        "ManuscriptSection",
        backref="manuscript",
        cascade="all, delete-orphan",
        order_by="ManuscriptSection.sort_order",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "section_count": len(self.sections),
        }


class ManuscriptSection(db.Model):
    """A single section (chapter, part, note) within a Manuscript (Phase 04).

    Supports a shallow two-level tree via ``parent_id`` — use flat ordering for
    simple documents; set ``parent_id`` for nested sub-sections.
    """

    __tablename__ = "manuscript_sections"
    __table_args__ = (
        db.Index("ix_manuscript_sections_manuscript_id", "manuscript_id"),
        db.Index("ix_manuscript_sections_parent_id", "parent_id"),
    )

    # Allowed status values (stored as free string for forward compatibility)
    STATUS_IDEA = "idea"
    STATUS_OUTLINE = "outline"
    STATUS_DRAFT = "draft"
    STATUS_REVIEW = "review"
    STATUS_FINAL = "final"
    STATUS_VALUES = (STATUS_IDEA, STATUS_OUTLINE, STATUS_DRAFT, STATUS_REVIEW, STATUS_FINAL)

    id = db.Column(db.Integer, primary_key=True)
    manuscript_id = db.Column(
        db.Integer, db.ForeignKey("manuscripts.id"), nullable=False
    )
    parent_id = db.Column(
        db.Integer, db.ForeignKey("manuscript_sections.id"), nullable=True
    )
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    title = db.Column(db.String(512), nullable=False, default="Untitled Section")
    content = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default=STATUS_DRAFT)
    synopsis = db.Column(db.Text, default="")

    # JSON array of Reference.id values (int list)
    linked_reference_ids_json = db.Column(db.Text, default="[]")

    # Children (sub-sections)
    children = db.relationship(
        "ManuscriptSection",
        backref=db.backref("parent", remote_side="ManuscriptSection.id"),
        cascade="all, delete-orphan",
        order_by="ManuscriptSection.sort_order",
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_linked_reference_ids(self) -> List[int]:
        try:
            return json.loads(self.linked_reference_ids_json or "[]")
        except (ValueError, TypeError):
            return []

    def set_linked_reference_ids(self, ids: List[int]) -> None:
        self.linked_reference_ids_json = json.dumps(
            [int(i) for i in ids if i is not None]
        )

    def to_dict(self, include_content: bool = True) -> dict:
        data: dict = {
            "id": self.id,
            "manuscript_id": self.manuscript_id,
            "parent_id": self.parent_id,
            "sort_order": self.sort_order,
            "title": self.title,
            "status": self.status,
            "synopsis": self.synopsis or "",
            "linked_reference_ids": self.get_linked_reference_ids(),
        }
        if include_content:
            data["content"] = self.content or ""
        return data
