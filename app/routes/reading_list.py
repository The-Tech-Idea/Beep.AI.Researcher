"""Phase 1 AI Discovery – reading list routes."""

from __future__ import annotations

import logging

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from app.config_manager import is_feature_enabled
from app.routes.route_entity_lookup import _base_template
from app.services.ai_discovery_payloads import reading_list_item_to_payload

reading_list_bp = Blueprint("reading_list", __name__, url_prefix="/reading-list")
logger = logging.getLogger(__name__)

_VALID_STATUSES = {"unread", "reading", "done"}


def _require_feature():
    if not is_feature_enabled("ai_discovery_enabled"):
        abort(404)


_VALID_STATUSES = {"unread", "reading", "done"}


@reading_list_bp.route("", methods=["GET"])
@login_required
def index():
    _require_feature()
    return render_template(
        "reading_list/reading_list.html", base_template=_base_template()
    )


@reading_list_bp.route("/data", methods=["GET"])
@login_required
def list_items():
    """Return reading list items as JSON, optionally filtered by status or tag."""
    _require_feature()
    from app.services.reading_list_service import ReadingListService

    status = request.args.get("status") or None
    tag = request.args.get("tag") or None
    items = ReadingListService().list_items(
        current_user.id, status=status, topic_tag=tag
    )
    return jsonify({"items": [reading_list_item_to_payload(item) for item in items]})


@reading_list_bp.route("", methods=["POST"])
@login_required
def add_item():
    _require_feature()
    from app.services.reading_list_service import ReadingListService

    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    item = ReadingListService().save_item(
        current_user.id,
        title=title,
        external_id=payload.get("external_id"),
        reference_id=payload.get("reference_id"),
        topic_tags=payload.get("topic_tags"),
    )
    return jsonify({"item": reading_list_item_to_payload(item)}), 201


@reading_list_bp.route("/<int:item_id>/status", methods=["PUT"])
@login_required
def update_status(item_id: int):
    _require_feature()
    from app.services.reading_list_service import ReadingListService

    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").strip()
    if status not in _VALID_STATUSES:
        return jsonify(
            {"error": f"status must be one of {sorted(_VALID_STATUSES)}"}
        ), 400

    try:
        ReadingListService().update_status(current_user.id, item_id, status)
        return jsonify({"ok": True})
    except LookupError:
        return jsonify({"error": "not found"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400


@reading_list_bp.route("/<int:item_id>/move", methods=["POST"])
@login_required
def move_to_project(item_id: int):
    _require_feature()
    from app.services.reading_list_service import ReadingListService

    payload = request.get_json(silent=True) or {}
    project_id = payload.get("project_id")
    if project_id in (None, ""):
        return jsonify({"error": "project_id is required"}), 400

    try:
        project_id = int(project_id)
    except (TypeError, ValueError):
        return jsonify({"error": "project_id must be an integer"}), 400

    try:
        ref = ReadingListService().move_to_project(current_user.id, item_id, project_id)
        from app.services.reference_service import reference_to_dict

        return jsonify({"ok": True, "reference": reference_to_dict(ref)})
    except LookupError as exc:
        return jsonify({"error": str(exc)}), 404


@reading_list_bp.route("/<int:item_id>", methods=["DELETE"])
@login_required
def delete_item(item_id: int):
    _require_feature()
    from app.services.reading_list_service import ReadingListService

    try:
        ReadingListService().delete_item(current_user.id, item_id)
        return jsonify({"ok": True})
    except LookupError:
        return jsonify({"error": "not found"}), 404
