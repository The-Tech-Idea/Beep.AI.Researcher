"""Phase 1 AI Discovery – paper alert routes."""
from __future__ import annotations

import logging

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from app.config_manager import is_feature_enabled
from app.services.ai_discovery_payloads import paper_alert_to_payload

alerts_bp = Blueprint("alerts", __name__, url_prefix="/alerts")
logger = logging.getLogger(__name__)


def _require_feature():
    if not is_feature_enabled("ai_discovery_enabled"):
        abort(404)


def _is_partial() -> bool:
    partial_flag = (request.args.get("partial") or "").strip().lower()
    return partial_flag in {"1", "true"} or request.headers.get("X-Requested-With") == "SPA"


def _base_template() -> str:
    return "base_embed.html" if _is_partial() else "base.html"


@alerts_bp.route("", methods=["GET"])
@login_required
def index():
    _require_feature()
    return render_template("alerts/alerts.html", base_template=_base_template())


@alerts_bp.route("/data", methods=["GET"])
@login_required
def list_alerts():
    """Return alert items; pass ?unread=1 to filter unread only."""
    _require_feature()
    from app.services.alert_service import AlertService

    unread_only = request.args.get("unread", "false").lower() in ("1", "true")
    items = AlertService().list_alerts(current_user.id, unread_only=unread_only)
    return jsonify({"alerts": [paper_alert_to_payload(item) for item in items]})


@alerts_bp.route("/count", methods=["GET"])
@login_required
def unread_count():
    _require_feature()
    from app.models.researcher import PaperAlert

    count = PaperAlert.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({"count": count})


@alerts_bp.route("/<int:alert_id>/read", methods=["POST"])
@login_required
def mark_read(alert_id: int):
    _require_feature()
    from app.services.alert_service import AlertService

    try:
        AlertService().mark_read(current_user.id, alert_id)
        return jsonify({"ok": True})
    except LookupError:
        return jsonify({"error": "not found"}), 404


@alerts_bp.route("/mark-all-read", methods=["POST"])
@login_required
def mark_all_read():
    _require_feature()
    from app.services.alert_service import AlertService

    updated = AlertService().mark_all_read(current_user.id)
    return jsonify({"ok": True, "updated": updated})
