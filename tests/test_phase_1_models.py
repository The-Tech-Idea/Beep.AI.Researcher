"""Tests for Phase 1 AI discovery models."""

from datetime import date

from app.database import db
from app.models.researcher import Reference
from app.models.researcher.phase_1_models import (
    FeedRecommendation,
    PaperAlert,
    ReadingListItem,
    ResearchInterestProfile,
)


class TestResearchInterestProfileModel:
    def test_create_profile(self, app_context, test_user):
        profile = ResearchInterestProfile(
            user_id=test_user.id,
            declared_topics=["machine learning", "systematic review"],
            inferred_topics=[{"topic": "ai safety", "score": 0.82}],
            preferred_sources=["semantic_scholar", "pubmed"],
            inference_enabled=True,
        )
        db.session.add(profile)
        db.session.commit()

        saved = db.session.get(ResearchInterestProfile, profile.id)
        assert saved is not None
        assert saved.user_id == test_user.id
        assert saved.declared_topics == ["machine learning", "systematic review"]
        assert saved.inferred_topics[0]["topic"] == "ai safety"
        assert saved.preferred_sources == ["semantic_scholar", "pubmed"]
        assert saved.inference_enabled is True

    def test_profile_to_dict(self, app_context, test_user):
        profile = ResearchInterestProfile(
            user_id=test_user.id,
            declared_topics=["oncology"],
            inferred_topics=[],
            preferred_sources=[],
        )
        db.session.add(profile)
        db.session.commit()

        payload = profile.to_dict()
        assert payload["user_id"] == test_user.id
        assert payload["declared_topics"] == ["oncology"]
        assert payload["inference_enabled"] is True
        assert payload["updated_at"] is not None


class TestFeedRecommendationModel:
    def test_create_recommendation(self, app_context, test_user):
        recommendation = FeedRecommendation(
            user_id=test_user.id,
            external_id="10.1000/feed-1",
            title="A highly relevant paper",
            authors=["Smith", "Jones"],
            abstract="Important abstract",
            source="semantic_scholar",
            relevance_score=0.94,
            reason="Matches your recent oncology reading",
            feed_date=date(2026, 4, 13),
        )
        db.session.add(recommendation)
        db.session.commit()

        saved = db.session.get(FeedRecommendation, recommendation.id)
        assert saved is not None
        assert saved.dismissed is False
        assert saved.saved is False
        assert saved.relevance_score == 0.94
        assert saved.feed_date == date(2026, 4, 13)

    def test_recommendation_to_dict(self, app_context, test_user):
        recommendation = FeedRecommendation(
            user_id=test_user.id,
            external_id="arxiv:1234.5678",
            title="Graph retrieval paper",
            authors=["Lee"],
            source="arxiv",
            relevance_score=0.61,
            feed_date=date(2026, 4, 13),
        )
        db.session.add(recommendation)
        db.session.commit()

        payload = recommendation.to_dict()
        assert payload["external_id"] == "arxiv:1234.5678"
        assert payload["authors"] == ["Lee"]
        assert payload["source"] == "arxiv"
        assert payload["feed_date"] == "2026-04-13"


class TestReadingListItemModel:
    def test_create_reading_list_item(self, app_context, test_user, test_project):
        reference = Reference(
            project_id=test_project.id,
            title="Reading List Reference",
            citation_key="ReadingListReference2026",
        )
        db.session.add(reference)
        db.session.flush()

        item = ReadingListItem(
            user_id=test_user.id,
            reference_id=reference.id,
            external_id="10.1000/reading-list-1",
            title="Reading List Paper",
            status="reading",
            topic_tags=["methods", "qualitative"],
        )
        db.session.add(item)
        db.session.commit()

        saved = db.session.get(ReadingListItem, item.id)
        assert saved is not None
        assert saved.reference_id == reference.id
        assert saved.status == "reading"
        assert saved.topic_tags == ["methods", "qualitative"]

    def test_reading_list_item_to_dict(self, app_context, test_user):
        item = ReadingListItem(
            user_id=test_user.id,
            title="Unread paper",
            status="unread",
            topic_tags=[],
        )
        db.session.add(item)
        db.session.commit()

        payload = item.to_dict()
        assert payload["title"] == "Unread paper"
        assert payload["status"] == "unread"
        assert payload["saved_at"] is not None
        assert payload["updated_at"] is not None


class TestPaperAlertModel:
    def test_create_paper_alert(self, app_context, test_user):
        alert = PaperAlert(
            user_id=test_user.id,
            external_id="10.1000/alert-1",
            title="Fresh alert paper",
            source="pubmed",
            alert_date=date(2026, 4, 13),
        )
        db.session.add(alert)
        db.session.commit()

        saved = db.session.get(PaperAlert, alert.id)
        assert saved is not None
        assert saved.is_read is False
        assert saved.source == "pubmed"
        assert saved.alert_date == date(2026, 4, 13)

    def test_paper_alert_to_dict(self, app_context, test_user):
        alert = PaperAlert(
            user_id=test_user.id,
            external_id="10.1000/alert-2",
            title="Unread alert",
            source="crossref",
            alert_date=date(2026, 4, 13),
            is_read=True,
        )
        db.session.add(alert)
        db.session.commit()

        payload = alert.to_dict()
        assert payload["source"] == "crossref"
        assert payload["is_read"] is True
        assert payload["alert_date"] == "2026-04-13"


class TestPhase1ModelRegistration:
    def test_models_exported_from_package(self):
        from app.models.researcher import (
            FeedRecommendation as ExportedFeedRecommendation,
            PaperAlert as ExportedPaperAlert,
            ReadingListItem as ExportedReadingListItem,
            ResearchInterestProfile as ExportedResearchInterestProfile,
        )

        assert ExportedResearchInterestProfile is ResearchInterestProfile
        assert ExportedFeedRecommendation is FeedRecommendation
        assert ExportedReadingListItem is ReadingListItem
        assert ExportedPaperAlert is PaperAlert

    def test_tablenames(self):
        assert ResearchInterestProfile.__tablename__ == "research_interest_profiles"
        assert FeedRecommendation.__tablename__ == "feed_recommendations"
        assert ReadingListItem.__tablename__ == "reading_list_items"
        assert PaperAlert.__tablename__ == "paper_alerts"