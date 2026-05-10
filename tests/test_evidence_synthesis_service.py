"""Tests for Phase 2 Evidence Synthesis Service."""

import json
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from app.services.evidence_synthesis_service import EvidenceSynthesisService


def _make_project(collection_id=None, owner_id=1):
    return SimpleNamespace(
        id=1,
        collection_id=collection_id,
        owner_id=owner_id,
    )


def test_synthesise_requires_question():
    service = EvidenceSynthesisService()
    project = _make_project()
    result, status = service.synthesise(project, "", persist=False)
    assert status == 400
    assert "error" in result


def test_synthesise_ai_not_configured():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = False
    service = EvidenceSynthesisService(ai_client=mock_client)
    project = _make_project()
    result, status = service.synthesise(project, "Test question?", persist=False)
    assert status == 503
    assert "error" in result


def test_synthesise_no_evidence_fallback():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.query_project_rag.return_value = (True, {"sources": []})
    mock_client.chat_reply.return_value = (True, "Test answer.")

    service = EvidenceSynthesisService(ai_client=mock_client)
    project = _make_project(collection_id="test-collection")
    result, status = service.synthesise(project, "Test question?", persist=False)
    # Falls back to EvidenceItems (which will be empty without DB)
    assert status in (200, 400)


def test_synthesise_returns_answer_with_evidence():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.query_project_rag.return_value = (
        True,
        {
            "sources": [
                {
                    "content": "Study shows positive effect.",
                    "document_id": 1,
                    "doi": "10.1000/a",
                    "score": 0.9,
                },
                {
                    "content": "Another study disagrees.",
                    "document_id": 2,
                    "doi": "10.1000/b",
                    "score": 0.7,
                },
            ]
        },
    )
    mock_client.chat_reply.return_value = (True, "The evidence is mixed [1], [2].")

    mock_classifier = MagicMock()
    mock_classifier.classify_batch.return_value = [
        {"snippet_index": 0, "polarity": "supporting", "confidence": 0.9, "reason": ""},
        {
            "snippet_index": 1,
            "polarity": "contradicting",
            "confidence": 0.8,
            "reason": "",
        },
    ]

    service = EvidenceSynthesisService(
        ai_client=mock_client, polarity_classifier=mock_classifier
    )
    project = _make_project(collection_id="test-collection")
    result, status = service.synthesise(project, "Does X work?", persist=False)

    assert status == 200
    assert result["answer"] == "The evidence is mixed [1], [2]."
    assert result["evidence_count"] == 2
    assert result["confidence"] == "mixed"


def test_retrieve_evidence_handles_list_response():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    # query_project_rag returns a list (not dict)
    mock_client.query_project_rag.return_value = (
        True,
        [
            {"content": "Result 1", "document_id": 1, "score": 0.8},
            {"text": "Result 2", "source_id": 2, "relevance": 0.6},
        ],
    )

    service = EvidenceSynthesisService(ai_client=mock_client)
    project = _make_project(collection_id="test")
    snippets = service._retrieve_evidence(project, "Q", 5, "balanced")

    assert len(snippets) == 2
    assert snippets[0]["text"] == "Result 1"
    assert snippets[1]["text"] == "Result 2"
