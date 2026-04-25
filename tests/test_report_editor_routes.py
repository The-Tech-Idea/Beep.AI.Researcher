from unittest.mock import patch

from app.database import db
from app.models.researcher import ResearchReportDraft


def test_report_draft_api_returns_default_draft(client, app_context, test_project):
    response = client.get(f"/researcher/api/projects/{test_project.id}/report/draft")

    assert response.status_code == 200
    data = response.get_json()
    assert data["draft"]["is_new"] is True
    assert "Introduction" in data["draft"]["html_content"]


def test_report_draft_api_saves_and_returns_draft(client, app_context, test_project):
    response = client.put(
        f"/researcher/api/projects/{test_project.id}/report/draft",
        json={
            "title": "My Report",
            "html_content": "<h1>My Report</h1><p>Saved body.</p>",
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["draft"]["title"] == "My Report"
    assert "Saved body." in data["draft"]["html_content"]

    saved = ResearchReportDraft.query.filter_by(project_id=test_project.id).first()
    assert saved is not None
    assert saved.title == "My Report"


def test_write_section_api_returns_fallback_outline_when_assistant_unavailable(client, app_context, test_project):
    with patch("app.routes.dashboard.beep_ai_client.is_configured", return_value=False):
        response = client.post(
            f"/researcher/api/projects/{test_project.id}/write-section",
            json={"prompt": "Write the discussion section around the main findings."},
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data["method"] == "fallback"
    assert "Suggested section outline" in data["text"]
    assert "RAG" not in data["text"]
    assert "prompt" not in data["text"].lower()


def test_write_section_api_uses_assistant_when_available(client, app_context, test_project):
    with patch("app.routes.dashboard.beep_ai_client.is_configured", return_value=True), \
         patch("app.routes.dashboard.beep_ai_client.chat_reply", return_value=(True, "Drafted section text.")):
        response = client.post(
            f"/researcher/api/projects/{test_project.id}/write-section",
            json={"prompt": "Write the introduction."},
        )

    assert response.status_code == 200
    data = response.get_json()
    assert data["method"] == "llm"
    assert data["text"] == "Drafted section text."


def test_write_section_api_uses_saved_project_quality_temperature(client, app_context, test_project):
    from app.database import db
    from app.models.researcher import ResearchProject

    project = db.session.get(ResearchProject, test_project.id)
    project.rag_quality_mode = "deep"
    db.session.commit()

    captured = {}

    def fake_chat_reply(messages, temperature=None):
        captured["temperature"] = temperature
        return True, "Drafted section text."

    with patch("app.routes.dashboard.beep_ai_client.is_configured", return_value=True), \
         patch("app.routes.dashboard.beep_ai_client.chat_reply", side_effect=fake_chat_reply):
        response = client.post(
            f"/researcher/api/projects/{test_project.id}/write-section",
            json={"prompt": "Write the introduction."},
        )

    assert response.status_code == 200
    assert captured["temperature"] == 0.1


def test_write_section_api_includes_grounded_library_evidence(client, app_context, test_project):
    captured = {}

    def fake_chat_reply(messages, temperature=None):
        captured["messages"] = messages
        return True, "Drafted section text."

    with patch("app.routes.dashboard.beep_ai_client.is_configured", return_value=True), \
         patch("app.routes.dashboard.build_project_grounded_context", return_value={
             "context_text": "Supporting library evidence:\n[1] Paper A [Doc 10]: Evidence for the requested section.",
             "sources": [{"source": "Paper A", "document_id": "10", "snippet": "Evidence for the requested section."}],
         }), \
         patch("app.routes.dashboard.beep_ai_client.chat_reply", side_effect=fake_chat_reply):
        response = client.post(
            f"/researcher/api/projects/{test_project.id}/write-section",
            json={"prompt": "Write the introduction."},
        )

    assert response.status_code == 200
    assert "Supporting library evidence:" in captured["messages"][1]["content"]
    assert response.get_json()["supporting_sources"][0]["document_id"] == "10"
