"""Alert generation for Phase 1 AI discovery."""
from __future__ import annotations

from app.database import db
from app.models.researcher import PaperAlert
from app.services.recommendation_service import RecommendationService


class AlertService:
    """Generate and manage alert inbox records from recommendations."""

    def __init__(self, recommendation_service=None):
        self.recommendation_service = recommendation_service or RecommendationService()

    def generate_alerts(self, user_id: int, *, force: bool = False, limit: int = 20) -> list[PaperAlert]:
        feed_items = self.recommendation_service.refresh_feed(user_id, force=force, limit=limit)
        existing_ids = {
            row.external_id
            for row in PaperAlert.query.filter_by(user_id=user_id).all()
        }

        created: list[PaperAlert] = []
        for item in feed_items:
            if item.external_id in existing_ids:
                continue
            alert = PaperAlert(
                user_id=user_id,
                external_id=item.external_id,
                title=item.title,
                source=item.source,
                alert_date=item.feed_date,
            )
            db.session.add(alert)
            created.append(alert)
            existing_ids.add(item.external_id)

        db.session.commit()
        return created

    def list_alerts(self, user_id: int, *, unread_only: bool = False) -> list[PaperAlert]:
        query = PaperAlert.query.filter_by(user_id=user_id)
        if unread_only:
            query = query.filter_by(is_read=False)
        return query.order_by(PaperAlert.alert_date.desc(), PaperAlert.created_at.desc()).all()

    def mark_read(self, user_id: int, alert_id: int) -> PaperAlert:
        alert = PaperAlert.query.filter_by(id=alert_id, user_id=user_id).first()
        if alert is None:
            raise LookupError("Alert not found")
        alert.is_read = True
        db.session.commit()
        return alert

    def mark_all_read(self, user_id: int) -> int:
        updated = (
            PaperAlert.query
            .filter_by(user_id=user_id, is_read=False)
            .update({"is_read": True}, synchronize_session=False)
        )
        db.session.commit()
        return int(updated or 0)