from app.core.time_utils import utcnow_naive
from app.database import db
from app.integrations.search.base import SearchResult
from app.models.researcher import FeedRecommendation, ReadingListItem, Reference, ResearchInterestProfile, ResearchProject
from app.services.recommendation_service import RecommendationService


class FakeProvider:
    def __init__(self, results):
        self.results = results

    def search_by_topic(self, topic, limit=20):
        return self.results[:limit]


class FakeSearchManager:
    def __init__(self, providers):
        self.providers = providers


class FakeAIClient:
    @staticmethod
    def get_embeddings(texts, model=None, user_id=None):
        vectors = []
        for index, text in enumerate(texts):
            lowered = text.lower()
            if index == 0:
                vectors.append([1.0, 1.0, 1.0])
            elif "recent multimodal" in lowered:
                vectors.append([1.0, 0.8, 0.6])
            elif "classic overview" in lowered:
                vectors.append([0.95, 0.7, 0.5])
            elif "dismissed paper" in lowered:
                vectors.append([1.0, 1.0, 0.8])
            elif "existing library" in lowered:
                vectors.append([1.0, 0.9, 0.7])
            else:
                vectors.append([0.3, 0.3, 0.3])
        return True, vectors


def _result(title, source, source_id, publication_date, doi=None):
    return SearchResult(
        id=f"{source}:{source_id}",
        title=title,
        authors=["Alice Smith"],
        abstract=f"{title} about machine learning for medical imaging.",
        source=source,
        source_id=source_id,
        url=f"https://example.com/{source_id}",
        publication_date=publication_date,
        doi=doi,
    )


def test_refresh_feed_ranks_recent_items_and_filters_known_or_dismissed(app_context, test_user):
    project = ResearchProject(name="Feed Project", owner_id=test_user.id, status="active")
    db.session.add(project)
    db.session.flush()

    db.session.add(Reference(project_id=project.id, title="Existing Library", citation_key="ref1", doi="10.1000/existing"))
    db.session.add(ResearchInterestProfile(
        user_id=test_user.id,
        declared_topics=["machine learning"],
        inferred_topics=[{"topic": "medical imaging", "score": 0.9}],
        preferred_sources=["semantic_scholar"],
    ))
    db.session.add(FeedRecommendation(
        user_id=test_user.id,
        external_id="semantic_scholar:dismissed-1",
        title="Dismissed Paper",
        authors=["Old Author"],
        abstract="Dismissed paper about machine learning.",
        source="semantic_scholar",
        relevance_score=0.5,
        reason="Dismissed earlier",
        dismissed=True,
        feed_date=utcnow_naive().date(),
    ))
    db.session.commit()

    provider = FakeProvider([
        _result("Existing Library", "semantic_scholar", "existing-1", "2024-01-01", doi="10.1000/existing"),
        _result("Classic Overview", "semantic_scholar", "classic-1", "2018-02-01"),
        _result("Recent Multimodal Study", "semantic_scholar", "recent-1", "2024-06-01"),
        _result("Dismissed Paper", "semantic_scholar", "dismissed-1", "2024-05-01"),
    ])
    service = RecommendationService(
        search_manager=FakeSearchManager({"semantic_scholar": provider}),
        ai_client_module=FakeAIClient(),
    )

    recommendations = service.refresh_feed(test_user.id, force=True, limit=10)
    titles = [item.title for item in recommendations]

    assert titles == ["Recent Multimodal Study", "Classic Overview"]
    assert FeedRecommendation.query.filter_by(user_id=test_user.id, dismissed=False).count() == 2


def test_invalidate_user_feed_preserves_dismissed_feedback(app_context, test_user):
    db.session.add_all([
        FeedRecommendation(
            user_id=test_user.id,
            external_id="semantic_scholar:active-1",
            title="Active",
            authors=[],
            abstract="",
            source="semantic_scholar",
            relevance_score=0.5,
            feed_date=utcnow_naive().date(),
        ),
        FeedRecommendation(
            user_id=test_user.id,
            external_id="semantic_scholar:dismissed-1",
            title="Dismissed",
            authors=[],
            abstract="",
            source="semantic_scholar",
            relevance_score=0.1,
            dismissed=True,
            feed_date=utcnow_naive().date(),
        ),
    ])
    db.session.commit()

    service = RecommendationService(search_manager=FakeSearchManager({}), ai_client_module=FakeAIClient())
    service.invalidate_user_feed(test_user.id)

    remaining = FeedRecommendation.query.filter_by(user_id=test_user.id).all()
    assert len(remaining) == 1
    assert remaining[0].dismissed is True


def test_refresh_feed_hides_saved_items_from_cache_and_regeneration(app_context, test_user):
    db.session.add(ResearchInterestProfile(
        user_id=test_user.id,
        declared_topics=["machine learning"],
        inferred_topics=[{"topic": "medical imaging", "score": 0.9}],
        preferred_sources=["semantic_scholar"],
    ))
    db.session.commit()

    provider = FakeProvider([
        _result("Saved Reading Pick", "semantic_scholar", "saved-1", "2024-05-20"),
        _result("Recent Multimodal Study", "semantic_scholar", "recent-1", "2024-06-01"),
    ])
    service = RecommendationService(
        search_manager=FakeSearchManager({"semantic_scholar": provider}),
        ai_client_module=FakeAIClient(),
    )

    service.refresh_feed(test_user.id, force=True, limit=10)
    saved_recommendation = FeedRecommendation.query.filter_by(
        user_id=test_user.id,
        title="Saved Reading Pick",
    ).first()
    assert saved_recommendation is not None

    db.session.add(ReadingListItem(
        user_id=test_user.id,
        external_id=saved_recommendation.external_id,
        title=saved_recommendation.title,
        topic_tags=["medical imaging"],
    ))
    saved_recommendation.saved = True
    db.session.commit()

    cached = service.refresh_feed(test_user.id, force=False, limit=10)
    regenerated = service.refresh_feed(test_user.id, force=True, limit=10)

    assert [item.title for item in cached] == ["Recent Multimodal Study"]
    assert [item.title for item in regenerated] == ["Recent Multimodal Study"]


def test_refresh_feed_persists_recommendation_metadata(app_context, test_user):
    db.session.add(ResearchInterestProfile(
        user_id=test_user.id,
        declared_topics=["machine learning"],
        inferred_topics=[],
        preferred_sources=["semantic_scholar"],
    ))
    db.session.commit()

    provider = FakeProvider([
        _result("Recent Multimodal Study", "semantic_scholar", "recent-1", "2024-06-01", doi="10.1000/recent-1"),
    ])
    service = RecommendationService(
        search_manager=FakeSearchManager({"semantic_scholar": provider}),
        ai_client_module=FakeAIClient(),
    )

    persisted = service.refresh_feed(test_user.id, force=True, limit=10)
    cached = service.refresh_feed(test_user.id, force=False, limit=10)

    assert len(persisted) == 1
    assert persisted[0].source_id == "recent-1"
    assert persisted[0].url == "https://example.com/recent-1"
    assert persisted[0].publication_date == "2024-06-01"
    assert persisted[0].doi == "10.1000/recent-1"
    assert cached[0].source_id == "recent-1"
    assert cached[0].url == "https://example.com/recent-1"
    assert cached[0].publication_date == "2024-06-01"
    assert cached[0].doi == "10.1000/recent-1"