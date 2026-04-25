from app.database import db
from app.models.researcher import FeedRecommendation, ReadingListItem, ResearchProject
from app.services.reading_list_service import ReadingListService


def test_save_recommendation_creates_reading_list_item(app_context, test_user):
    recommendation = FeedRecommendation(
        user_id=test_user.id,
        external_id="doi:10.1000/example",
        title="Machine Learning Paper",
        authors=["Alice Smith"],
        abstract="A paper about medical imaging.",
        source="semantic_scholar",
        relevance_score=0.9,
        reason="Matches your interest in medical imaging",
        feed_date=db.func.current_date(),
    )
    db.session.add(recommendation)
    db.session.commit()

    service = ReadingListService()
    item = service.save_recommendation(test_user.id, recommendation.id)

    db.session.refresh(recommendation)
    assert item.title == "Machine Learning Paper"
    assert item.external_id == "doi:10.1000/example"
    assert item.topic_tags == ["medical imaging"]
    assert recommendation.saved is True


def test_move_to_project_creates_reference_and_links_item(app_context, test_user):
    project = ResearchProject(name="Library Project", owner_id=test_user.id, status="active")
    db.session.add(project)
    db.session.flush()

    recommendation = FeedRecommendation(
        user_id=test_user.id,
        external_id="doi:10.1000/example",
        title="Machine Learning Paper",
        authors=["Alice Smith"],
        abstract="A paper about medical imaging.",
        source="semantic_scholar",
        relevance_score=0.9,
        reason="Matches your interest in medical imaging",
        feed_date=db.func.current_date(),
    )
    db.session.add(recommendation)
    db.session.commit()

    service = ReadingListService()
    item = service.save_recommendation(test_user.id, recommendation.id)
    reference = service.move_to_project(test_user.id, item.id, project.id)

    db.session.refresh(item)
    assert item.reference_id == reference.id
    assert reference.project_id == project.id
    assert reference.title == "Machine Learning Paper"
    assert reference.doi == "10.1000/example"


def test_save_recommendation_to_project_creates_reference_without_reading_list_item(app_context, test_user):
    project = ResearchProject(name="Direct Save Project", owner_id=test_user.id, status="active")
    db.session.add(project)
    db.session.flush()

    recommendation = FeedRecommendation(
        user_id=test_user.id,
        external_id="pubmed:12345",
        title="Project Saved Paper",
        authors=["Alice Smith"],
        abstract="A paper saved straight to a project.",
        source="pubmed",
        relevance_score=0.8,
        reason="Matches your interest in synthesis",
        feed_date=db.func.current_date(),
    )
    db.session.add(recommendation)
    db.session.commit()

    service = ReadingListService()
    reference = service.save_recommendation_to_project(test_user.id, recommendation.id, project.id)

    db.session.refresh(recommendation)
    assert reference.project_id == project.id
    assert reference.pubmed_id == "12345"
    assert recommendation.saved is True
    assert ReadingListItem.query.filter_by(user_id=test_user.id, external_id="pubmed:12345").count() == 0


def test_save_recommendation_to_project_uses_persisted_metadata(app_context, test_user):
    project = ResearchProject(name="Metadata Save Project", owner_id=test_user.id, status="active")
    db.session.add(project)
    db.session.flush()

    recommendation = FeedRecommendation(
        user_id=test_user.id,
        external_id="semantic_scholar:title:project-saved-paper",
        title="Project Saved Paper",
        authors=["Alice Smith"],
        abstract="A paper saved straight to a project.",
        source="semantic_scholar",
        source_id="paper-123",
        url="https://example.com/paper-123",
        publication_date="2024-02-15",
        doi="10.1000/project-saved",
        relevance_score=0.8,
        reason="Matches your interest in synthesis",
        feed_date=db.func.current_date(),
    )
    db.session.add(recommendation)
    db.session.commit()

    service = ReadingListService()
    reference = service.save_recommendation_to_project(test_user.id, recommendation.id, project.id)

    assert reference.project_id == project.id
    assert reference.doi == "10.1000/project-saved"
    assert reference.url == "https://example.com/paper-123"
    assert reference.year == 2024


def test_update_status_validates_value(app_context, test_user):
    item = ReadingListItem(user_id=test_user.id, title="Saved Paper")
    db.session.add(item)
    db.session.commit()

    service = ReadingListService()
    updated = service.update_status(test_user.id, item.id, "done")

    assert updated.status == "done"