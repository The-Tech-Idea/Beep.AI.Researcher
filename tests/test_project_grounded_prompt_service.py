from app.services.project_grounded_prompt_service import (
    build_grounded_user_prompt,
    merge_supporting_sources,
)


def test_build_grounded_user_prompt_returns_base_prompt_without_context():
    assert build_grounded_user_prompt("Base prompt", None, "Guidance") == "Base prompt"


def test_build_grounded_user_prompt_appends_guidance_and_context():
    prompt = build_grounded_user_prompt(
        "Base prompt",
        {"context_text": "Supporting library evidence:\n[1] Paper A: Evidence."},
        "Use grounded evidence.",
    )

    assert "Base prompt" in prompt
    assert "Use grounded evidence." in prompt
    assert "Supporting library evidence:" in prompt


def test_merge_supporting_sources_deduplicates_entries():
    merged = merge_supporting_sources(
        [{"source": "Paper A", "document_id": "10", "snippet": "Evidence."}],
        {
            "sources": [
                {"source": "Paper A", "document_id": "10", "snippet": "Evidence."},
                {"source": "Paper B", "document_id": "11", "snippet": "More evidence."},
            ]
        },
    )

    assert len(merged) == 2
    assert merged[0]["document_id"] == "10"
    assert merged[1]["document_id"] == "11"
