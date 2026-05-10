"""Chat routes — chat with documents (Beep.AI.Server when configured via config_manager)."""

from flask import Blueprint, request, jsonify, session as flask_session
from flask_login import login_required

from app.services.beep_ai_client import (
    is_configured,
    query_project_rag,
    chat_reply,
    get_scope_context,
)
from app.services import chat_service
from app.services.project_rag_preferences_service import (
    resolve_project_generation_temperature,
    resolve_project_quality_mode,
)
from app.routes.project_api_guard import (
    guard_project_blueprint,
    get_guarded_project_or_404 as get_project_or_404,
)

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/<int:project_id>/chat", methods=["POST"])
@login_required
def post_message(project_id):
    project = get_project_or_404(project_id)
    data = request.get_json() or {}
    data["resolve_project_quality_mode_fn"] = resolve_project_quality_mode
    data["resolve_project_generation_temperature_fn"] = (
        resolve_project_generation_temperature
    )
    payload, status_code = chat_service.post_project_message(
        project,
        data,
        user_id=flask_session.get("user_id"),
        get_chat_reply_fn=_get_chat_reply,
    )
    return jsonify(payload), status_code


def _get_chat_reply(
    project,
    session,
    user_content,
    use_context=True,
    user_id=None,
    quality_mode="balanced",
    rewrite_query=None,
    hybrid_search=None,
    rerank=None,
    grounded_only=True,
    research_mode=True,
    temperature=None,
):
    """Get reply from Beep.AI.Server RAG+LLM with project scoping."""
    # query_project_rag(...) remains the project-scoped retrieval primitive; the service receives it via injection.
    return chat_service.get_chat_reply(
        project,
        session,
        user_content,
        use_context=use_context,
        user_id=user_id,
        quality_mode=quality_mode,
        rewrite_query=rewrite_query,
        hybrid_search=hybrid_search,
        rerank=rerank,
        grounded_only=grounded_only,
        research_mode=research_mode,
        temperature=temperature,
        is_configured_fn=is_configured,
        query_project_rag_fn=query_project_rag,
        chat_reply_fn=chat_reply,
        get_scope_context_fn=get_scope_context,
    )


@chat_bp.route("/<int:project_id>/chat/history", methods=["GET"])
@login_required
def get_history(project_id):
    project = get_project_or_404(project_id)
    payload, status_code = chat_service.get_history(
        project, request.args.get("session_id")
    )
    return jsonify(payload), status_code


# ---------------------------------------------------------------------------
# Chat tool actions (Phase 07 — insert citation, search library, summarize)
# ---------------------------------------------------------------------------


@chat_bp.route("/<int:project_id>/chat/tools/search-library", methods=["POST"])
@login_required
def tool_search_library(project_id):
    """Search the project document library and return formatted results.

    Request body::

        {
            "query": "neural networks in medical imaging",
            "style": "apa",          // optional citation style
            "max_results": 5         // optional
        }

    Response::

        {
            "results": [
                {
                    "source": "filename or title",
                    "snippet": "…",
                    "score": 0.82,
                    "reference_id": 3,
                    "citation": "Smith, J. (2020)…"
                }
            ]
        }
    """
    project = get_project_or_404(project_id)
    payload, status_code = chat_service.search_library(
        project,
        request.get_json() or {},
        user_id=flask_session.get("user_id"),
        is_configured_fn=is_configured,
        query_project_rag_fn=query_project_rag,
    )
    return jsonify(payload), status_code


@chat_bp.route("/<int:project_id>/chat/tools/summarize-source", methods=["POST"])
@login_required
def tool_summarize_source(project_id):
    """Summarize a specific reference or document using the project LLM.

    Request body::

        {
            "reference_id": 3,    // reference to summarize (uses abstract + title)
            "focus": "methods"    // optional focus hint
        }

    Response::

        {
            "reference_id": 3,
            "citation_key": "Smith2020",
            "summary": "…"
        }
    """
    project = get_project_or_404(project_id)
    payload, status_code = chat_service.summarize_source(
        project,
        request.get_json() or {},
        user_id=flask_session.get("user_id"),
        is_configured_fn=is_configured,
        chat_reply_fn=chat_reply,
        get_scope_context_fn=get_scope_context,
        resolve_project_generation_temperature_fn=resolve_project_generation_temperature,
    )
    return jsonify(payload), status_code


@chat_bp.route("/<int:project_id>/chat/tools/insert-citation", methods=["POST"])
@login_required
def tool_insert_citation(project_id):
    """Return a formatted citation string ready to paste into a manuscript.

    Request body::

        {
            "reference_ids": [1, 2, 3],   // one or more ref ids
            "style": "apa"                // apa | mla | chicago | bibtex
        }

    Response::

        {
            "citations": [
                {"reference_id": 1, "citation_key": "Smith2020", "formatted": "Smith, J. (2020)…"}
            ]
        }
    """
    project = get_project_or_404(project_id)
    payload, status_code = chat_service.insert_citation(
        project, request.get_json() or {}
    )
    return jsonify(payload), status_code


guard_project_blueprint(chat_bp)
