"""Search API — local text search or Beep.AI.Server RAG when configured via config_manager."""

from flask import Blueprint, request, jsonify, session
from flask_login import login_required

from app.config_manager import config_manager
from app.models.researcher import ResearchProject, ResearcherDocument
from app.routes.route_entity_lookup import get_entity_or_404, get_project_or_404
from app.services.beep_ai_client import is_configured, query_project_rag

search_bp = Blueprint("search", __name__)


def _local_search(project, q):
    limit = int(config_manager.get_setting("search_result_limit", default=50))
    docs = ResearcherDocument.query.filter_by(project_id=project.id).all()
    results, q_lower = [], q.lower()
    for d in docs:
        if not d.text_content:
            continue
        text, idx = d.text_content, d.text_content.lower().find(q_lower)
        if idx < 0:
            continue
        start, end = max(0, idx - 50), min(len(text), idx + len(q) + 100)
        snippet = (text[start:end] or "").replace("\n", " ")
        results.append(
            {
                "document_id": d.id,
                "filename": d.filename,
                "snippet": snippet,
                "offset": idx,
            }
        )
    return results[:limit]


def _rag_search(project, q):
    """Perform RAG search with proper project scoping."""
    if not is_configured() or not project.collection_id:
        return None

    # Get current user from session for scoped access
    user_id = session.get("user_id")

    # Use project-scoped RAG query
    ok, results = query_project_rag(
        project=project, query=q, max_results=20, user_id=user_id
    )

    if not ok or not isinstance(results, list):
        return None

    limit = int(config_manager.get_setting("search_result_limit", default=50))
    entries = []
    for r in results:
        if not isinstance(r, dict):
            continue
        entries.append(
            {
                "document_id": r.get("document_id")
                or r.get("metadata", {}).get("researcher_doc_id"),
                "filename": r.get("source") or r.get("filename"),
                "snippet": (r.get("content") or r.get("text") or "")[:300],
                "offset": 0,
                "relevance_score": r.get("score") or r.get("relevance_score") or 0,
            }
        )
    return entries[:limit]


@search_bp.route("/<int:project_id>/search", methods=["POST", "GET"])
@login_required
def run_search(project_id):
    project = get_project_or_404(project_id)
    payload = request.get_json(silent=True) or {}
    query_args = request.args or {}
    q = (payload.get("q") or query_args.get("q") or "").strip()
    source_hint = (
        (payload.get("source") or query_args.get("source") or "").strip().lower()
    )
    if not q:
        return jsonify({"results": [], "source": "none"})

    if source_hint == "local":
        return jsonify({"results": _local_search(project, q), "source": "local"})

    rag_results = _rag_search(project, q)
    if rag_results is not None and source_hint != "local":
        return jsonify({"results": rag_results, "source": "rag"})

    local_results = _local_search(project, q)
    if source_hint == "rag":
        return jsonify(
            {
                "results": local_results,
                "source": "local",
                "note": "Document library search is unavailable, so these are local file matches.",
            }
        )
    return jsonify({"results": local_results, "source": "local"})
