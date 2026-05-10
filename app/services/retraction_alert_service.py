"""Phase 2 Retraction Alert Service — monitors project references for retractions
and creates PaperAlert records when a reference is retracted.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.time_utils import utcnow_naive
from app.database import db
from app.models.researcher import PaperAlert, Reference, RetractionRecord
from app.services.retraction_watch_adapter import RetractionWatchAdapter

logger = logging.getLogger(__name__)


class RetractionAlertService:
    """Monitor references for retractions and create alerts."""

    def __init__(self, adapter=None):
        self.adapter = adapter or RetractionWatchAdapter()

    def check_project_references(self, project_id: int) -> list[dict[str, Any]]:
        """Check all references in a project for retractions.

        Returns list of new retraction alerts created.
        """
        references = Reference.query.filter_by(project_id=project_id).all()
        dois = [r.doi for r in references if r.doi]

        if not dois:
            return []

        # Get already-known retractions
        known_dois = {row.doi for row in RetractionRecord.query.all()}

        new_alerts = []
        for record in self.adapter.check_dois(dois):
            doi = record["doi"]
            if doi in known_dois:
                continue

            # Upsert retraction record
            existing = RetractionRecord.query.filter_by(doi=doi).first()
            if existing:
                continue

            retraction_record = RetractionRecord(
                doi=doi,
                reason=record.get("reason", ""),
                retraction_date=utcnow_naive(),
                acknowledged_by_json=[],
            )
            db.session.add(retraction_record)

            # Find all users with this reference and create alerts
            refs = Reference.query.filter_by(doi=doi).all()
            for ref in refs:
                project = ref.project
                if project:
                    alert = PaperAlert(
                        user_id=project.owner_id,
                        external_id=f"doi:{doi}",
                        title=f"RETRACTED: {ref.title or doi}",
                        source="retraction_watch",
                        alert_date=utcnow_naive().date(),
                    )
                    db.session.add(alert)
                    new_alerts.append(
                        {
                            "doi": doi,
                            "title": ref.title or doi,
                            "reason": record.get("reason", ""),
                            "user_id": project.owner_id,
                        }
                    )

        db.session.commit()
        return new_alerts

    def acknowledge_retraction(self, doi: str, user_id: int) -> bool:
        """Mark a retraction as acknowledged by a user."""
        record = RetractionRecord.query.filter_by(doi=doi).first()
        if not record:
            return False

        acknowledged = record.acknowledged_by_json or []
        if str(user_id) not in [str(u) for u in acknowledged]:
            acknowledged.append(user_id)
            record.acknowledged_by_json = acknowledged
            db.session.commit()

        return True

    def is_retracted(self, doi: str) -> bool:
        """Check if a DOI has been retracted."""
        return RetractionRecord.query.filter_by(doi=doi).first() is not None
