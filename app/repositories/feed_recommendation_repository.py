"""Feed recommendation repository — data access for FeedRecommendation."""

from __future__ import annotations

from typing import List, Optional, Set
from datetime import date

from app.extensions.db import db
from app.models.researcher.phase_1_models import FeedRecommendation
from app.models.researcher.researcher_references import Reference
from app.models.researcher.researcher_projects import ResearchProject
from app.models.researcher.phase_1_models import ReadingListItem


class FeedRecommendationRepository:
    """Repository for feed recommendation CRUD and user-specific queries."""

    def get_feed_for_date(
        self, user_id: int, feed_date: date, limit: int = 50
    ) -> List[FeedRecommendation]:
        """Get cached feed recommendations for a specific date."""
        return (
            db.session.query(FeedRecommendation)
            .filter_by(
                user_id=user_id,
                feed_date=feed_date,
                dismissed=False,
                saved=False,
            )
            .order_by(
                FeedRecommendation.relevance_score.desc(),
                FeedRecommendation.created_at.desc(),
            )
            .limit(limit)
            .all()
        )

    def get_dismissed_ids(self, user_id: int) -> Set[str]:
        """Get set of external_ids that the user has dismissed."""
        rows = (
            db.session.query(FeedRecommendation.external_id)
            .filter_by(user_id=user_id, dismissed=True)
            .all()
        )
        return {row[0] for row in rows if row[0]}

    def get_saved_records(self, user_id: int) -> List[FeedRecommendation]:
        """Get all saved feed recommendations for a user."""
        return (
            db.session.query(FeedRecommendation)
            .filter_by(user_id=user_id, saved=True)
            .all()
        )

    def get_by_external_id(
        self, user_id: int, external_id: str
    ) -> Optional[FeedRecommendation]:
        """Get the most recent recommendation for an external_id."""
        return (
            db.session.query(FeedRecommendation)
            .filter_by(user_id=user_id, external_id=external_id)
            .order_by(FeedRecommendation.created_at.desc())
            .first()
        )

    def get_by_id(self, recommendation_id: int) -> Optional[FeedRecommendation]:
        """Get a recommendation by its primary key."""
        return db.session.get(FeedRecommendation, recommendation_id)

    def clear_for_date(self, user_id: int, feed_date: date) -> None:
        """Remove non-dismissed recommendations for a date."""
        (
            db.session.query(FeedRecommendation)
            .filter_by(user_id=user_id, feed_date=feed_date, dismissed=False)
            .delete(synchronize_session=False)
        )

    def clear_non_dismissed(self, user_id: int) -> None:
        """Remove all non-dismissed recommendations for a user."""
        (
            db.session.query(FeedRecommendation)
            .filter_by(user_id=user_id, dismissed=False)
            .delete(synchronize_session=False)
        )

    def add(self, recommendation: FeedRecommendation) -> FeedRecommendation:
        """Add a new feed recommendation."""
        db.session.add(recommendation)
        db.session.flush()
        return recommendation

    def add_all(
        self, recommendations: List[FeedRecommendation]
    ) -> List[FeedRecommendation]:
        """Add multiple feed recommendations."""
        db.session.add_all(recommendations)
        db.session.flush()
        return recommendations

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()

    # ── Cross-reference queries (known saved items) ────────────────────────

    def get_known_saved_external_ids(self, user_id: int) -> Set[str]:
        """Get all external IDs the user has already saved across references, reading list, and feed."""
        identifiers: Set[str] = set()

        # References from user's projects
        references = (
            db.session.query(Reference.doi, Reference.pubmed_id, Reference.arxiv_id)
            .join(ResearchProject, Reference.project_id == ResearchProject.id)
            .filter(ResearchProject.owner_id == user_id)
            .all()
        )
        from app.services.ai_discovery_utils import canonical_external_id

        for doi, pubmed_id, arxiv_id in references:
            if doi:
                identifiers.add(canonical_external_id("doi", doi=doi))
            if pubmed_id:
                identifiers.add(canonical_external_id("pubmed", source_id=pubmed_id))
            if arxiv_id:
                identifiers.add(canonical_external_id("arxiv", source_id=arxiv_id))

        # Reading list items
        for item in (
            db.session.query(ReadingListItem.external_id)
            .filter_by(user_id=user_id)
            .all()
        ):
            if item[0]:
                identifiers.add(item[0])

        # Saved feed records
        for rec in self.get_saved_records(user_id):
            if rec.external_id:
                identifiers.add(rec.external_id)

        return identifiers

    def get_known_saved_titles(self, user_id: int) -> Set[str]:
        """Get all normalized titles the user has already saved."""
        from app.services.ai_discovery_utils import normalize_for_match

        titles: Set[str] = set()

        # References from user's projects
        references = (
            db.session.query(Reference.title)
            .join(ResearchProject, Reference.project_id == ResearchProject.id)
            .filter(ResearchProject.owner_id == user_id)
            .all()
        )
        for (title,) in references:
            if title:
                titles.add(normalize_for_match(title))

        # Reading list items
        for item in (
            db.session.query(ReadingListItem.title).filter_by(user_id=user_id).all()
        ):
            if item[0]:
                titles.add(normalize_for_match(item[0]))

        # Saved feed records
        for rec in self.get_saved_records(user_id):
            if rec.title:
                titles.add(normalize_for_match(rec.title))

        return titles
