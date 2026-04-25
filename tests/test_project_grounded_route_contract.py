from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _route_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_project_generation_routes_use_grounded_context_builder():
    route_paths = [
        "app/routes/ai_coding.py",
        "app/routes/dashboard.py",
        "app/routes/extraction.py",
        "app/routes/report_writing.py",
        "app/routes/training.py",
    ]

    for route_path in route_paths:
        contents = _route_text(route_path)
        assert "build_project_grounded_context(" in contents, route_path


def test_project_chat_route_uses_project_scoped_rag_query_instead_of_free_chat_only():
    contents = _route_text("app/routes/chat.py")
    assert "query_project_rag(" in contents
    assert "grounded_only=grounded_only" in contents


def test_related_and_contradiction_routes_use_dedicated_retrieval_helpers():
    related_contents = _route_text("app/routes/related.py")
    contradiction_contents = _route_text("app/routes/contradiction.py")

    assert "beep_ai_client.query_with_context(" in related_contents
    assert "beep_ai_client.find_citations_for_draft(" in related_contents
    assert "beep_ai_client.detect_contradictions(" in contradiction_contents


def test_global_chat_route_remains_intentionally_global_only():
    contents = _route_text("app/routes/global_chat.py")

    assert "build_project_grounded_context(" not in contents
    assert "query_project_rag(" not in contents
    assert "chat_reply(" in contents
