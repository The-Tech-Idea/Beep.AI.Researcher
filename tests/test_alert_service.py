from app.database import db
from app.models.researcher import FeedRecommendation
from app.services.alert_service import AlertService


class StubRecommendationService:
    def __init__(self, items):
        self.items = items
        self.calls = []

    def refresh_feed(self, user_id, force=False, limit=20):
        self.calls.append((user_id, force, limit))
        return self.items


def test_generate_alerts_deduplicates_existing_items(app_context, test_user):
    rec1 = FeedRecommendation(
        user_id=test_user.id,
        external_id="doi:10.1000/a",
        title="Paper A",
        authors=[],
        abstract="",
        source="semantic_scholar",
        relevance_score=0.9,
        feed_date=db.func.current_date(),
    )
    rec2 = FeedRecommendation(
        user_id=test_user.id,
        external_id="doi:10.1000/b",
        title="Paper B",
        authors=[],
        abstract="",
        source="pubmed",
        relevance_score=0.8,
        feed_date=db.func.current_date(),
    )
    db.session.add_all([rec1, rec2])
    db.session.commit()

    service = AlertService(recommendation_service=StubRecommendationService([rec1, rec2]))
    first_run = service.generate_alerts(test_user.id, force=True)
    second_run = service.generate_alerts(test_user.id, force=True)

    assert len(first_run) == 2
    assert second_run == []


def test_mark_read_and_mark_all_read(app_context, test_user):
    rec1 = FeedRecommendation(
        user_id=test_user.id,
        external_id="doi:10.1000/a",
        title="Paper A",
        authors=[],
        abstract="",
        source="semantic_scholar",
        relevance_score=0.9,
        feed_date=db.func.current_date(),
    )
    rec2 = FeedRecommendation(
        user_id=test_user.id,
        external_id="doi:10.1000/b",
        title="Paper B",
        authors=[],
        abstract="",
        source="pubmed",
        relevance_score=0.8,
        feed_date=db.func.current_date(),
    )
    db.session.add_all([rec1, rec2])
    db.session.commit()

    service = AlertService(recommendation_service=StubRecommendationService([rec1, rec2]))
    alerts = service.generate_alerts(test_user.id, force=True)
    marked = service.mark_read(test_user.id, alerts[0].id)
    changed = service.mark_all_read(test_user.id)

    assert marked.is_read is True
    assert changed == 1