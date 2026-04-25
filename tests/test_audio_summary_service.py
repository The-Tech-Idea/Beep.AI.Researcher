from datetime import date

import pytest

from app.database import db
from app.models.researcher import FeedRecommendation, ResearchProject, ResearcherDocument
from app.services.audio_summary_service import AudioSummaryService


class FakeAIClient:
    @staticmethod
    def synthesize_speech(text, voice=None, **kwargs):
        return True, {
            "audio_base64": "ZmFrZQ==",
            "content_type": "audio/mpeg",
            "voice": voice,
            "speed": kwargs.get("speed"),
        }


def test_build_summary_text_extracts_abstract_and_findings(app_context, test_user):
    project = ResearchProject(name="Audio Project", owner_id=test_user.id, status="active")
    db.session.add(project)
    db.session.flush()
    document = ResearcherDocument(
        project_id=project.id,
        filename="paper.pdf",
        file_path="/tmp/paper.pdf",
        mime_type="application/pdf",
        text_content=(
            "This study evaluates machine learning for radiology triage. It introduces a lightweight workflow.\n\n"
            "Results show improved sensitivity across all cohorts. The findings suggest lower review time for clinicians."
        ),
        file_size=10,
        source_type="test",
    )
    db.session.add(document)
    db.session.commit()

    service = AudioSummaryService(ai_client_module=FakeAIClient())
    summary = service.build_summary_text(document.id)

    assert "Abstract:" in summary
    assert "Key findings:" in summary
    assert "Results show improved sensitivity" in summary


def test_generate_audio_summary_calls_tts(app_context, test_user):
    project = ResearchProject(name="Audio Project", owner_id=test_user.id, status="active")
    db.session.add(project)
    db.session.flush()
    document = ResearcherDocument(
        project_id=project.id,
        filename="paper.pdf",
        file_path="/tmp/paper.pdf",
        mime_type="application/pdf",
        text_content="Abstract paragraph. Results show better outcomes.",
        file_size=10,
        source_type="test",
    )
    db.session.add(document)
    db.session.commit()

    service = AudioSummaryService(ai_client_module=FakeAIClient())
    payload = service.generate_audio_summary(document.id, voice="alloy", speed=1.1)

    assert payload["audio_base64"] == "ZmFrZQ=="
    assert payload["voice"] == "alloy"
    assert payload["speed"] == 1.1
    assert "summary_text" in payload
    assert AudioSummaryService.extract_audio_bytes(payload) == b"fake"


def test_generate_recommendation_audio_summary_calls_tts(app_context, test_user):
    recommendation = FeedRecommendation(
        user_id=test_user.id,
        external_id="doi:10.1000/example",
        title="Radiology Workflow Paper",
        authors=["Alice Smith", "Bob Jones"],
        abstract="This paper studies workflow improvements for radiology teams.",
        source="crossref",
        relevance_score=0.82,
        reason="Matches your interest in radiology triage",
        feed_date=date(2026, 4, 13),
    )
    db.session.add(recommendation)
    db.session.commit()

    service = AudioSummaryService(ai_client_module=FakeAIClient())
    payload = service.generate_recommendation_audio_summary(recommendation.id, test_user.id, voice="alloy")

    assert payload["audio_base64"] == "ZmFrZQ=="
    assert payload["voice"] == "alloy"
    assert "Radiology Workflow Paper" in payload["summary_text"]
    assert "Matches your interest in radiology triage" in payload["summary_text"]
    assert AudioSummaryService.extract_audio_bytes(payload) == b"fake"


def test_build_summary_text_raises_for_missing_document(app_context):
    service = AudioSummaryService(ai_client_module=FakeAIClient())

    with pytest.raises(LookupError):
        service.build_summary_text(999999)