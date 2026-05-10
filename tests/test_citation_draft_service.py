"""Tests for Phase 4 Citation Draft Service."""

import json
from unittest.mock import MagicMock

from app.services.citation_draft_service import CitationDraftService


def test_draft_requires_theme():
    service = CitationDraftService()
    result, status = service.draft("", [])
    assert status == 400
    assert "error" in result


def test_draft_requires_sources():
    service = CitationDraftService()
    result, status = service.draft("Climate change", [])
    assert status == 400
    assert "error" in result


def test_draft_ai_not_configured():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = False
    service = CitationDraftService(ai_client=mock_client)
    result, status = service.draft(
        "Test theme", [{"doi": "10.1000/a", "title": "Paper A", "abstract": "Abstract"}]
    )
    assert status == 503


def test_draft_returns_markers():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.chat_reply.return_value = (
        True,
        "Climate change [Cite: 10.1000/a] has been studied extensively.",
    )
    service = CitationDraftService(ai_client=mock_client)
    result, status = service.draft(
        "Climate change",
        [
            {"doi": "10.1000/a", "title": "Paper A", "abstract": "Climate impacts..."},
        ],
    )
    assert status == 200
    assert "draft" in result
    assert result["markers"]["total_markers"] >= 1


def test_draft_strips_markdown_fences():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.chat_reply.return_value = (True, '```json\n"Draft text here"\n```')
    service = CitationDraftService(ai_client=mock_client)
    result, status = service.draft(
        "Test",
        [
            {"doi": "10.1000/a", "title": "Paper A", "abstract": "Abstract"},
        ],
    )
    assert status == 200
    assert not result["draft"].startswith("```")


def test_draft_limits_sources_to_20():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.chat_reply.return_value = (True, "A short draft.")
    service = CitationDraftService(ai_client=mock_client)
    sources = [
        {"doi": f"10.1000/{i}", "title": f"Paper {i}", "abstract": "A"}
        for i in range(30)
    ]
    result, status = service.draft("Test", sources)
    assert status == 200
    assert len(sources) == 30
    # Service should internally limit to 20
    assert result["source_count"] == 20
