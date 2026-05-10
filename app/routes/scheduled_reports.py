"""Scheduled report routes backed by the job queue runtime."""

from flask import Blueprint, request, jsonify
from flask_login import login_required

from app.routes.project_api_guard import (
    guard_project_blueprint,
    get_guarded_project_or_404 as get_project_or_404,
)
from app.services import scheduled_report_service

reports_bp = Blueprint("scheduled_reports", __name__)


@reports_bp.route("/<int:project_id>/reports/schedule", methods=["POST"])
@login_required
def create_scheduled_report(project_id):
    project = get_project_or_404(project_id)
    payload, status_code = scheduled_report_service.create_scheduled_report(
        project, request.get_json() or {}
    )
    return jsonify(payload), status_code


@reports_bp.route("/<int:project_id>/reports/scheduled", methods=["GET"])
@login_required
def list_scheduled_reports(project_id):
    project = get_project_or_404(project_id)
    payload, status_code = scheduled_report_service.list_scheduled_reports(project)
    return jsonify(payload), status_code


guard_project_blueprint(reports_bp)
