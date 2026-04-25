"""Phase 1 AI Discovery – research interests settings routes."""
from __future__ import annotations

import logging

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from app.config_manager import is_feature_enabled

research_interests_bp = Blueprint(
    "research_interests", __name__, url_prefix="/settings/research-interests"
)
logger = logging.getLogger(__name__)


def _require_feature():
    if not is_feature_enabled("ai_discovery_enabled"):
        abort(404)


@research_interests_bp.route("", methods=["GET"])
@login_required
def index():
    _require_feature()
    from app.services.interest_profile_service import InterestProfileService

    profile = InterestProfileService().get_or_create_profile(current_user.id)
    return render_template("settings/research_interests.html", profile=profile)


@research_interests_bp.route("", methods=["POST"])
@login_required
def update_interests():
    """Save declared topics and optional preferred source list."""
    _require_feature()
    from app.services.interest_profile_service import InterestProfileService

    payload = request.get_json(silent=True) or {}
    declared_topics = payload.get("declared_topics")
    preferred_sources = payload.get("preferred_sources")

    if declared_topics is not None and not isinstance(declared_topics, list):
        return jsonify({"error": "declared_topics must be a list"}), 400
    if preferred_sources is not None and not isinstance(preferred_sources, list):
        return jsonify({"error": "preferred_sources must be a list"}), 400

    svc = InterestProfileService()
    kwargs = {}
    if declared_topics is not None:
        kwargs["declared_topics"] = declared_topics
    if preferred_sources is not None:
        kwargs["preferred_sources"] = preferred_sources

    profile = svc.update_profile(current_user.id, **kwargs)
    return jsonify({"ok": True, "profile": profile.to_dict()})


@research_interests_bp.route("/trigger-inference", methods=["POST"])
@login_required
def trigger_inference():
    """Enqueue a background job to re-infer topics from the user's library."""
    _require_feature()
    from app.services.interest_profile_service import InterestProfileService

    job_id = InterestProfileService().trigger_inference(current_user.id)
    return jsonify({"ok": True, "job_id": job_id})
