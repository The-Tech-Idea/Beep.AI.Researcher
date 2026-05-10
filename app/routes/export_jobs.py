"""Export job routes — trigger and download export bundles (Phase 05)."""

from __future__ import annotations

import os
import pathlib

from flask import Blueprint, jsonify, request, send_file
from flask_login import current_user, login_required

from app.routes.route_entity_lookup import get_entity_or_404, get_project_or_404
from app.models.researcher import ResearchProject

export_jobs_bp = Blueprint("export_jobs", __name__)


def _auth_project(project: ResearchProject):
    if project.owner_id != current_user.id:
        return jsonify({"error": "Not authorized"}), 403
    return None


@export_jobs_bp.route("/projects/<int:project_id>/export-jobs", methods=["GET"])
@login_required
def list_jobs(project_id: int):
    """List the 20 most recent export jobs for the project."""
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    from app.services.export_service import list_export_jobs

    jobs = list_export_jobs(project_id)
    return jsonify({"jobs": [j.to_dict() for j in jobs]})


@export_jobs_bp.route("/projects/<int:project_id>/export-jobs", methods=["POST"])
@login_required
def create_job(project_id: int):
    """Start an export job (runs synchronously in this MVP).

    Request body::

        {
            "format": "markdown_zip",    // or "bibtex"
            "manuscript_id": 1           // optional
        }

    Response: job dict (status will be "done" or "failed" immediately).
    """
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    data = request.get_json() or {}
    fmt = (data.get("format") or "markdown_zip").strip()
    manuscript_id = data.get("manuscript_id")

    from app.services.export_service import create_export_job

    job = create_export_job(project, fmt, manuscript_id=manuscript_id)
    return jsonify(job.to_dict()), 201


@export_jobs_bp.route(
    "/projects/<int:project_id>/export-jobs/<int:job_id>", methods=["GET"]
)
@login_required
def get_job(project_id: int, job_id: int):
    """Get export job status."""
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    from app.services.export_service import get_export_job

    job = get_export_job(job_id, project_id)
    if job is None:
        return jsonify({"error": "Export job not found"}), 404
    return jsonify(job.to_dict())


@export_jobs_bp.route(
    "/projects/<int:project_id>/export-jobs/<int:job_id>/download",
    methods=["GET"],
)
@login_required
def download_job(project_id: int, job_id: int):
    """Download the artifact produced by a completed export job."""
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    from app.services.export_service import get_export_job
    from app.models.researcher.export_jobs import ExportJob

    job = get_export_job(job_id, project_id)
    if job is None:
        return jsonify({"error": "Export job not found"}), 404
    if job.status != ExportJob.STATUS_DONE:
        return jsonify({"error": "Export job not complete", "status": job.status}), 409
    if not job.artifact_path:
        return jsonify({"error": "Artifact path missing"}), 500

    artifact = pathlib.Path(job.artifact_path)
    if not artifact.exists():
        return jsonify({"error": "Artifact file not found on disk"}), 404

    mime = "application/zip" if artifact.suffix == ".zip" else "text/plain"
    return send_file(
        str(artifact),
        mimetype=mime,
        as_attachment=True,
        download_name=artifact.name,
    )
