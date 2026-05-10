"""Video source routes — YouTube ingest and summarisation (Phase 03)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.routes.route_entity_lookup import get_entity_or_404, get_project_or_404
from app.models.researcher import ResearchProject

video_sources_bp = Blueprint("video_sources", __name__)


@video_sources_bp.route(
    "/projects/<int:project_id>/video-sources/ingest", methods=["POST"]
)
@login_required
def ingest_video(project_id: int):
    """Ingest a YouTube URL into the project.

    Request body::

        {
            "url": "https://www.youtube.com/watch?v=...",
            "create_reference": true   // optional, default true
        }

    Response::

        {
            "ok": true,
            "video_id": "...",
            "document_id": 42,
            "reference_id": 7,
            "transcript_available": true,
            "captions_unavailable": false,
            "stt_hint": false,
            "title": "...",
            "thumbnail_url": "..."
        }
    """
    project = get_project_or_404(project_id)

    if project.owner_id != current_user.id:
        return jsonify({"error": "Not authorized"}), 403

    data = request.get_json() or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400

    create_ref = bool(data.get("create_reference", True))

    try:
        from app.services.youtube_ingester_service import ingest_youtube_url

        result = ingest_youtube_url(
            project,
            url,
            user_id=current_user.id,
            create_reference_record=create_ref,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    if not result["ok"]:
        return jsonify({"error": result.get("error", "Ingest failed")}), 422

    doc = result.get("document")
    ref = result.get("reference")
    return jsonify(
        {
            "ok": True,
            "video_id": result.get("video_id"),
            "document_id": doc.id if doc else None,
            "reference_id": ref.id if ref else None,
            "transcript_available": result.get("transcript_available", False),
            "captions_unavailable": result.get("captions_unavailable", True),
            "stt_hint": result.get("stt_hint", False),
            "title": result.get("title"),
            "thumbnail_url": result.get("thumbnail_url"),
        }
    ), 201


@video_sources_bp.route(
    "/projects/<int:project_id>/video-sources/<int:document_id>/summarise",
    methods=["POST"],
)
@login_required
def summarise_video(project_id: int, document_id: int):
    """Summarise the transcript of a previously ingested video document.

    The document must have ``text_content`` set (transcript).
    Requires Beep.AI.Server to be configured for chat completions.

    Response::

        {
            "ok": true,
            "summary": "...",
            "note_document_id": 43
        }
    """
    project = get_project_or_404(project_id)

    if project.owner_id != current_user.id:
        return jsonify({"error": "Not authorized"}), 403

    from app.models.researcher import ResearcherDocument

    document = ResearcherDocument.query.filter_by(
        id=document_id, project_id=project.id
    ).first_or_404()

    if not document.text_content:
        return jsonify(
            {
                "error": "Document has no transcript text.",
                "stt_hint": document.source_type == "youtube",
            }
        ), 422

    try:
        from app.services.video_summary_service import summarize_video_document

        result = summarize_video_document(project, document, user_id=current_user.id)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    if not result["ok"]:
        return jsonify({"error": result.get("error", "Summarisation failed")}), 502

    return jsonify(
        {
            "ok": True,
            "summary": result.get("summary"),
            "note_document_id": result.get("note_document_id"),
        }
    )
