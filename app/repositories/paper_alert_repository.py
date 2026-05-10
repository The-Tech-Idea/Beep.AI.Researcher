"""Paper alert repository — data access for PaperAlert model."""

from __future__ import annotations

from typing import List, Optional, Set

from app.extensions.db import db
from app.models.researcher.phase_1_models import PaperAlert


class PaperAlertRepository:
    """Repository for PaperAlert CRUD and user-scoped queries."""

    def get(self, alert_id: int, user_id: int) -> Optional[PaperAlert]:
        return (
            db.session.query(PaperAlert).filter_by(id=alert_id, user_id=user_id).first()
        )

    def get_by_user(
        self, user_id: int, *, unread_only: bool = False
    ) -> List[PaperAlert]:
        query = db.session.query(PaperAlert).filter_by(user_id=user_id)
        if unread_only:
            query = query.filter_by(is_read=False)
        return query.order_by(
            PaperAlert.alert_date.desc(), PaperAlert.created_at.desc()
        ).all()

    def get_existing_external_ids(self, user_id: int) -> Set[str]:
        rows = db.session.query(PaperAlert.external_id).filter_by(user_id=user_id).all()
        return {row[0] for row in rows if row[0]}

    def count_unread(self, user_id: int) -> int:
        return (
            db.session.query(PaperAlert)
            .filter_by(user_id=user_id, is_read=False)
            .count()
        )

    def add(self, alert: PaperAlert) -> PaperAlert:
        db.session.add(alert)
        db.session.flush()
        return alert

    def add_all(self, alerts: List[PaperAlert]) -> List[PaperAlert]:
        db.session.add_all(alerts)
        db.session.flush()
        return alerts

    def mark_all_read(self, user_id: int) -> int:
        count = (
            db.session.query(PaperAlert)
            .filter_by(user_id=user_id, is_read=False)
            .count()
        )
        (
            db.session.query(PaperAlert)
            .filter_by(user_id=user_id, is_read=False)
            .update({"is_read": True}, synchronize_session=False)
        )
        db.session.flush()
        return count

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()
