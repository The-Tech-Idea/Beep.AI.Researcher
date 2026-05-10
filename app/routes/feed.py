"""Phase 1 AI Discovery – personalised feed routes."""

from __future__ import annotations

import logging

from flask import Blueprint, Response, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from app.config_manager import is_feature_enabled
from app.routes.route_entity_lookup import _base_template
from app.services.ai_discovery_payloads import (
    feed_recommendation_to_payload,
    reading_list_item_to_payload,
)

feed_bp = Blueprint("feed", __name__, url_prefix="/feed")
logger = logging.getLogger(__name__)


def _require_feature():
    if not is_feature_enabled("ai_discovery_enabled"):
        abort(404)


@feed_bp.route("", methods=["GET"])
@login_required
def index():
    _require_feature()
    return render_template("feed/feed.html", base_template=_base_template())


@feed_bp.route("/data", methods=["GET"])
@login_required
def get_feed():
    """Return cached feed items for today without re-fetching."""
    _require_feature()
    from app.services.recommendation_service import RecommendationService

    items = RecommendationService().refresh_feed(current_user.id, force=False)
    return jsonify({"items": [feed_recommendation_to_payload(item) for item in items]})


@feed_bp.route("/refresh", methods=["POST"])
@login_required
def refresh_feed():
    """Force-rebuild the personalised feed for today."""
    _require_feature()
    from app.services.recommendation_service import RecommendationService

    try:
        items = RecommendationService().refresh_feed(current_user.id, force=True)
        return jsonify(
            {
                "items": [feed_recommendation_to_payload(item) for item in items],
                "count": len(items),
            }
        )
    except Exception:
        logger.exception("Feed refresh failed for user %s", current_user.id)
        return jsonify({"error": "Feed refresh failed"}), 500


@feed_bp.route("/<int:item_id>/dismiss", methods=["POST"])
@login_required
def dismiss_item(item_id: int):
    _require_feature()
    from app.services.recommendation_service import RecommendationService

    try:
        RecommendationService().dismiss_recommendation(
            current_user.id, recommendation_id=item_id
        )
        return jsonify({"ok": True})
    except LookupError:
        return jsonify({"error": "not found"}), 404


@feed_bp.route("/<int:item_id>/save", methods=["POST"])
@login_required
def save_to_reading_list(item_id: int):
    _require_feature()
    from app.services.reading_list_service import ReadingListService

    try:
        item = ReadingListService().save_recommendation(current_user.id, item_id)
        return jsonify({"ok": True, "item": reading_list_item_to_payload(item)})
    except LookupError:
        return jsonify({"error": "not found"}), 404


@feed_bp.route("/<int:item_id>/save-to-project", methods=["POST"])
@login_required
def save_to_project(item_id: int):
    _require_feature()
    from app.services.reading_list_service import ReadingListService
    from app.services.reference_service import reference_to_dict

    payload = request.get_json(silent=True) or {}
    project_id = payload.get("project_id")
    if project_id in (None, ""):
        return jsonify({"error": "project_id is required"}), 400

    try:
        project_id = int(project_id)
    except (TypeError, ValueError):
        return jsonify({"error": "project_id must be an integer"}), 400

    try:
        reference = ReadingListService().save_recommendation_to_project(
            current_user.id,
            item_id,
            project_id,
        )
        return jsonify({"ok": True, "reference": reference_to_dict(reference)})
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404


@feed_bp.route("/<int:item_id>/audio-summary", methods=["GET"])
@login_required
def get_audio_summary(item_id: int):
    _require_feature()
    from app.services.audio_summary_service import AudioSummaryService

    voice = request.args.get("voice") or None
    service = AudioSummaryService()
    try:
        result = service.generate_recommendation_audio_summary(
            item_id,
            current_user.id,
            voice=voice,
        )
    except LookupError:
        return jsonify({"error": "not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 502

    audio_data = service.extract_audio_bytes(result)
    if not audio_data:
        return jsonify({"error": "No audio returned from TTS service"}), 502

    content_type = result.get("content_type") if isinstance(result, dict) else None
    return Response(audio_data, mimetype=content_type or "audio/mpeg")
