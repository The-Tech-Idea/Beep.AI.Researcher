"""Tests for Phase 4 Writing Quality Service."""

import json
from unittest.mock import MagicMock, patch

from app.services.writing_quality_service import WritingQualityService


def test_analyse_no_text():
    service = WritingQualityService()
    result, status = service.analyse("")
    assert status == 400
    assert "error" in result


def test_analyse_text_too_long():
    service = WritingQualityService()
    result, status = service.analyse("x" * 10001)
    assert status == 400
    assert "error" in result


def test_analyse_ai_not_configured():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = False
    service = WritingQualityService(ai_client=mock_client)
    result, status = service.analyse("A short test passage.")
    assert status == 503
    assert "overall_score" in result
    assert result["overall_score"] is None


def test_analyse_returns_scores_and_issues():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.chat_reply.return_value = (
        True,
        json.dumps(
            {
                "overall_score": 72.5,
                "tone_score": 80.0,
                "clarity_score": 65.0,
                "grammar_score": 78.0,
                "issues": [
                    {
                        "type": "passive_voice",
                        "severity": "warning",
                        "text": "was found",
                        "suggestion": "found",
                        "offset": 5,
                        "length": 9,
                    }
                ],
                "suggestions": ["Use more active voice"],
            }
        ),
    )

    service = WritingQualityService(ai_client=mock_client)
    result, status = service.analyse("This was found to be correct.")
    assert status == 200
    assert result["overall_score"] == 72.5
    assert len(result["issues"]) == 1
    assert result["issues"][0]["type"] == "passive_voice"
    assert result["issues"][0]["offset"] == 5


def test_analyse_tolerates_markdown_fences():
    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.chat_reply.return_value = (
        True,
        """```json
{"overall_score": 80.0, "tone_score": 85, "clarity_score": 75, "grammar_score": 90, "issues": [], "suggestions": []}
```""",
    )

    service = WritingQualityService(ai_client=mock_client)
    result, status = service.analyse("Clean academic prose here.")
    assert status == 200
    assert result["overall_score"] == 80.0


def test_apply_fix_valid():
    service = WritingQualityService()
    text = "The result was found to be significant."
    issue = {"offset": 11, "length": 9, "suggestion": "found"}
    patched = service.apply_fix(text, issue)
    assert patched == "The result found to be significant."


def test_apply_fix_invalid_offset():
    service = WritingQualityService()
    text = "Short text."
    issue = {"offset": 999, "length": 5, "suggestion": "fix"}
    patched = service.apply_fix(text, issue)
    assert patched is None


def test_apply_fix_missing_fields():
    service = WritingQualityService()
    patched = service.apply_fix("text", {"suggestion": "fix"})
    assert patched is None


def test_validate_issues_filters_invalid():
    text = "The test sentence is here."
    issues = [
        {
            "type": "passive_voice",
            "severity": "warning",
            "offset": 0,
            "length": 3,
            "suggestion": "X",
        },
        {
            "type": "invalid_type",
            "severity": "bad",
            "offset": 0,
            "length": 3,
            "suggestion": "Y",
        },
        {
            "type": "grammar",
            "severity": "error",
            "offset": 100,
            "length": 10,
            "suggestion": "Z",
        },
        "not a dict",
    ]
    valid = WritingQualityService._validate_issues(issues, text)
    assert len(valid) == 2
    assert valid[0]["type"] == "passive_voice"
    assert valid[1]["type"] == "info"
