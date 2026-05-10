"""Synthesis report repository — data access for SynthesisReport."""

from __future__ import annotations

from typing import List, Optional

from app.extensions.db import db
from app.models.researcher.phase_a_models import SynthesisReport


class SynthesisReportRepository:
    """Repository for SynthesisReport CRUD and project-scoped queries."""

    def get(self, report_id: int, project_id: int) -> Optional[SynthesisReport]:
        return (
            db.session.query(SynthesisReport)
            .filter_by(id=report_id, project_id=project_id)
            .first()
        )

    def get_by_project(
        self, project_id: int, *, limit: int = 50
    ) -> List[SynthesisReport]:
        return (
            db.session.query(SynthesisReport)
            .filter_by(project_id=project_id)
            .order_by(SynthesisReport.created_at.desc())
            .limit(limit)
            .all()
        )

    def add(self, report: SynthesisReport) -> SynthesisReport:
        db.session.add(report)
        db.session.flush()
        return report

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()
