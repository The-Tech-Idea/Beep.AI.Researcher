"""Tests for Phase 2 Polarity Classifier."""

import json
from unittest.mock import MagicMock

from app.services.polarity_classifier import PolarityClassifier


def test_classify_empty():
    service = PolarityClassifier()
    result = service.classify_batch("Test question", [])
    assert result == []


def test_classify_ai_not_configured():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = False
    service = PolarityClassifier(ai_client=mock_client)
    result = service.classify_batch("Test", ["Snippet 1"])
    assert len(result) == 1
    assert result[0]["polarity"] == "mentioning"
    assert result[0]["confidence"] == 0.0


def test_classify_returns_results():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.chat_reply.return_value = (
        True,
        json.dumps(
            {
                "classifications": [
                    {
                        "snippet_index": 0,
                        "polarity": "supporting",
                        "confidence": 0.9,
                        "reason": "Matches question",
                    },
                    {
                        "snippet_index": 1,
                        "polarity": "contradicting",
                        "confidence": 0.8,
                        "reason": "Opposite claim",
                    },
                ]
            }
        ),
    )
    service = PolarityClassifier(ai_client=mock_client)
    result = service.classify_batch(
        "Test question", ["Supporting text", "Contradicting text"]
    )
    assert len(result) == 2
    assert result[0]["polarity"] == "supporting"
    assert result[1]["polarity"] == "contradicting"


def test_classify_tolerates_markdown_fences():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.chat_reply.return_value = (
        True,
        """```json
{"classifications": [{"snippet_index": 0, "polarity": "mentioning", "confidence": 0.5, "reason": ""}]}
```""",
    )
    service = PolarityClassifier(ai_client=mock_client)
    result = service.classify_batch("Q", ["Snippet"])
    assert len(result) == 1
    assert result[0]["polarity"] == "mentioning"


def test_cache_returns_cached():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.chat_reply.return_value = (
        True,
        json.dumps(
            {
                "classifications": [
                    {
                        "snippet_index": 0,
                        "polarity": "supporting",
                        "confidence": 0.9,
                        "reason": "",
                    }
                ]
            }
        ),
    )
    service = PolarityClassifier(ai_client=mock_client)
    result1 = service.classify_batch("Q", ["Snippet 1"])
    result2 = service.classify_batch("Q", ["Snippet 1"])
    assert result1 == result2
    # Should only call LLM once
    assert mock_client.chat_reply.call_count == 1
