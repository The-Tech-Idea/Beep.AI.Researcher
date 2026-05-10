"""Alert generation for Phase 1 AI discovery."""

from __future__ import annotations

from datetime import date

from app.core.time_utils import utcnow_naive
from app.database import db
from app.models.researcher import PaperAlert
from app.services.recommendation_service import RecommendationService


class AlertService:
    """Generate and manage alert inbox records from recommendations."""

    def __init__(self, recommendation_service=None, alert_repo=None):
        self.recommendation_service = recommendation_service or RecommendationService()
        self._alert_repo = alert_repo

    @property
    def _repo(self):
        if self._alert_repo is None:
            from app.repositories.paper_alert_repository import PaperAlertRepository

            self._alert_repo = PaperAlertRepository()
        return self._alert_repo

    def generate_alerts(
        self, user_id: int, *, force: bool = False, limit: int = 20
    ) -> list[PaperAlert]:
        from app.services.interest_profile_service import InterestProfileService

        profile_service = InterestProfileService()
        profile = profile_service.get_or_create_profile(user_id)
        topics = profile_service.effective_topics(user_id, limit=12)
        if not topics:
            return []

        preferred_sources = (
            profile.preferred_sources or RecommendationService.DEFAULT_SOURCES
        )
        new_candidates = self.recommendation_service.fetch_candidates(
            topics, sources=preferred_sources, per_topic_limit=5
        )

        existing_ids = self._repo.get_existing_external_ids(user_id)

        created: list[PaperAlert] = []
        for item in new_candidates:
            if item.external_id in existing_ids:
                continue
            alert = PaperAlert(
                user_id=user_id,
                external_id=item.external_id,
                title=item.title,
                source=item.source,
                alert_date=utcnow_naive().date(),
            )
            self._repo.add(alert)
            created.append(alert)
            existing_ids.add(item.external_id)
            if len(created) >= limit:
                break

        self._repo.commit()
        return created

    def list_alerts(
        self, user_id: int, *, unread_only: bool = False
    ) -> list[PaperAlert]:
        return self._repo.get_by_user(user_id, unread_only=unread_only)

    def mark_read(self, user_id: int, alert_id: int) -> PaperAlert:
        alert = self._repo.get(alert_id, user_id)
        if alert is None:
            raise LookupError("Alert not found")
        alert.is_read = True
        self._repo.commit()
        return alert

    def mark_all_read(self, user_id: int) -> int:
        result = self._repo.mark_all_read(user_id)
        self._repo.commit()
        return result
