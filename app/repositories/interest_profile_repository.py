"""Interest profile repository — data access for ResearchInterestProfile."""

from __future__ import annotations

from typing import Optional

from app.extensions.db import db
from app.models.researcher.phase_1_models import ResearchInterestProfile


class InterestProfileRepository:
    """Repository for ResearchInterestProfile CRUD and user-scoped queries."""

    def get_by_user(self, user_id: int) -> Optional[ResearchInterestProfile]:
        return (
            db.session.query(ResearchInterestProfile).filter_by(user_id=user_id).first()
        )

    def add(self, profile: ResearchInterestProfile) -> ResearchInterestProfile:
        db.session.add(profile)
        db.session.flush()
        return profile

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()
