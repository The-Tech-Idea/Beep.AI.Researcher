"""Phase 3: Retention policies. Uses config_manager for storage."""

import json
from flask import Blueprint, request, jsonify
from flask_login import login_required

from app.models.researcher import ResearchProject
from app.config_manager import config_manager
from app.routes.route_entity_lookup import get_entity_or_404, get_project_or_404

retention_bp = Blueprint("retention", __name__)


def _get_policies():
    return config_manager.get("retention.policies") or {}


def _set_policies(policies):
    config_manager.set("retention.policies", policies)
    config_manager.save()


@retention_bp.route("/<int:project_id>/retention", methods=["GET"])
@login_required
def get_retention(project_id):
    project = get_project_or_404(project_id)
    policies = _get_policies()
    proj_policy = policies.get(
        str(project_id), {"retention_days": None, "action": "flag"}
    )
    if "action" not in proj_policy or not proj_policy.get("action"):
        proj_policy["action"] = "flag"
    return jsonify({"project_id": project_id, **proj_policy})


@retention_bp.route("/<int:project_id>/retention", methods=["PUT"])
@login_required
def set_retention(project_id):
    project = get_project_or_404(project_id)
    data = request.get_json() or {}
    retention_days = data.get("retention_days")
    action = (data.get("action") or "flag").strip().lower()
    if action not in {"flag", "archive", "delete"}:
        return jsonify({"error": "invalid action"}), 400
    policies = _get_policies()
    policies[str(project_id)] = {"retention_days": retention_days, "action": action}
    _set_policies(policies)
    return jsonify(
        {"project_id": project_id, "retention_days": retention_days, "action": action}
    )
