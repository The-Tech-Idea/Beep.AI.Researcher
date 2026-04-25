from datetime import date

from app.database import db
from app.models.researcher import FeedRecommendation, ReadingListItem, Reference, ResearchInterestProfile, ResearchProject, ResearcherDocument
from app.services.interest_inference_service import InterestInferenceService


class FakeAIClient:
    @staticmethod
    def get_embeddings(texts, model=None, user_id=None):
        vectors = []
        for index, text in enumerate(texts):
            lowered = text.lower()
            if index == 0:
                vectors.append([1.0, 1.0, 1.0])
            elif "machine learning" in lowered:
                vectors.append([1.0, 0.4, 0.1])
            elif "medical imaging" in lowered:
                vectors.append([0.8, 1.0, 0.2])
            elif "neural networks" in lowered:
                vectors.append([0.7, 0.9, 0.3])
            else:
                # Orthogonal to corpus vector so keyword bigrams clearly outscore generic terms.
                vectors.append([0.0, 0.0, 1.0])
        return True, vectors


def test_infer_topics_uses_documents_and_references(app_context, test_user):
    project = ResearchProject(name="Topic Study", owner_id=test_user.id, status="active")
    db.session.add(project)
    db.session.flush()

    db.session.add_all([
        ResearcherDocument(
            project_id=project.id,
            filename="doc1.pdf",
            file_path="/tmp/doc1.pdf",
            mime_type="application/pdf",
            text_content="Machine learning improves medical imaging diagnosis. Machine learning models also use neural networks for image classification.",
            file_size=10,
            source_type="test",
        ),
        ResearcherDocument(
            project_id=project.id,
            filename="doc2.pdf",
            file_path="/tmp/doc2.pdf",
            mime_type="application/pdf",
            text_content="Medical imaging studies increasingly rely on neural networks and machine learning for clinical decision support.",
            file_size=10,
            source_type="test",
        ),
    ])
    reference = Reference(
        project_id=project.id,
        title="Neural Networks for Medical Imaging",
        citation_key="ref1",
        abstract="This paper surveys medical imaging applications of machine learning and neural networks.",
    )
    db.session.add(reference)
    db.session.commit()

    service = InterestInferenceService(ai_client_module=FakeAIClient())

    inferred_topics = service.infer_topics(test_user.id, max_topics=5)
    topic_names = {item["topic"] for item in inferred_topics}

    assert "machine learning" in topic_names
    assert "medical imaging" in topic_names or "neural networks" in topic_names


def test_update_profile_persists_inferred_topics(app_context, test_user):
    project = ResearchProject(name="Topic Study", owner_id=test_user.id, status="active")
    db.session.add(project)
    db.session.flush()
    db.session.add(
        ResearcherDocument(
            project_id=project.id,
            filename="doc1.pdf",
            file_path="/tmp/doc1.pdf",
            mime_type="application/pdf",
            text_content="Machine learning for medical imaging and neural networks.",
            file_size=10,
            source_type="test",
        )
    )
    db.session.commit()

    service = InterestInferenceService(ai_client_module=FakeAIClient())
    result = service.update_profile(test_user.id)

    profile = ResearchInterestProfile.query.filter_by(user_id=test_user.id).first()
    assert profile is not None
    assert profile.inferred_topics == result
    assert any(item["topic"] == "machine learning" for item in result)


def test_infer_topics_uses_reading_list_items_without_project_references(app_context, test_user):
    db.session.add(FeedRecommendation(
        user_id=test_user.id,
        external_id="doi:10.1000/reading-list-topic",
        title="Machine Learning Benchmarks",
        authors=["Lee"],
        abstract="Medical imaging models use neural networks for benchmarking.",
        source="semantic_scholar",
        source_id="reading-list-topic",
        publication_date="2026-04-01",
        doi="10.1000/reading-list-topic",
        relevance_score=0.8,
        reason="Matches your interest in medical imaging",
        feed_date=date(2026, 4, 13),
    ))
    db.session.add(ReadingListItem(
        user_id=test_user.id,
        external_id="doi:10.1000/reading-list-topic",
        title="Machine Learning Benchmarks",
        topic_tags=["medical imaging"],
    ))
    db.session.commit()

    service = InterestInferenceService(ai_client_module=FakeAIClient())

    inferred_topics = service.infer_topics(test_user.id, max_topics=5)
    topic_names = {item["topic"] for item in inferred_topics}

    assert "machine learning" in topic_names
    assert "medical imaging" in topic_names or "neural networks" in topic_names