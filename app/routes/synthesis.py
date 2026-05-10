"""Phase 2 — Evidence Synthesis routes."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.config_manager import is_feature_enabled
from app.models.researcher import (
    EvidenceItem,
    ResearchProject,
    ResearchBrief,
    SynthesisReport,
)
from app.routes.route_entity_lookup import get_entity_or_404, get_project_or_404

logger = logging.getLogger(__name__)

synthesis_bp = Blueprint("synthesis", __name__)


def _require_feature():
    if not is_feature_enabled("evidence_synthesis_enabled"):
        from flask import abort

        abort(404)


# ---------------------------------------------------------------------------
# Synthesis main page
# ---------------------------------------------------------------------------


@synthesis_bp.route("/synthesis", methods=["GET"])
@login_required
def index():
    """Synthesis main page."""
    _require_feature()
    from flask import render_template

    return render_template("synthesis/synthesis.html")


# ---------------------------------------------------------------------------
# Run a synthesis query
# ---------------------------------------------------------------------------


@synthesis_bp.route("/projects/<int:project_id>/synthesis/query", methods=["POST"])
@login_required
def run_query(project_id):
    """Submit a research question for synthesis.

    Request body::

        {"question": "Does X cause Y?", "max_evidence": 10}

    Returns the synthesized answer with evidence table.
    """
    _require_feature()
    project = get_project_or_404(project_id)
    if project.owner_id != current_user.id:
        return jsonify({"error": "Not authorized"}), 403

    from app.services.evidence_synthesis_service import EvidenceSynthesisService

    data = request.get_json() or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "question is required"}), 400

    max_evidence = min(int(data.get("max_evidence", 10)), 30)
    quality_mode = data.get("quality_mode", "balanced")

    payload, status = EvidenceSynthesisService().synthesise(
        project, question, max_evidence=max_evidence, quality_mode=quality_mode
    )
    return jsonify(payload), status


# ---------------------------------------------------------------------------
# List synthesis reports for a project
# ---------------------------------------------------------------------------


@synthesis_bp.route("/projects/<int:project_id>/synthesis", methods=["GET"])
@login_required
def list_reports(project_id):
    """List all synthesis reports for the project."""
    _require_feature()
    project = get_project_or_404(project_id)

    reports = (
        SynthesisReport.query.filter_by(project_id=project.id)
        .order_by(SynthesisReport.created_at.desc())
        .all()
    )

    return jsonify({"reports": [r.to_dict() for r in reports]})


# ---------------------------------------------------------------------------
# View a single synthesis report
# ---------------------------------------------------------------------------


@synthesis_bp.route(
    "/projects/<int:project_id>/synthesis/<int:report_id>", methods=["GET"]
)
@login_required
def view_report(project_id, report_id):
    """View a single synthesis report with full evidence table."""
    _require_feature()
    project = get_project_or_404(project_id)

    report = SynthesisReport.query.filter_by(
        id=report_id, project_id=project.id
    ).first()
    if report is None:
        return jsonify({"error": "Report not found"}), 404

    return jsonify({"report": report.to_dict()})


# ---------------------------------------------------------------------------
# Literature Review Draft
# ---------------------------------------------------------------------------


@synthesis_bp.route(
    "/projects/<int:project_id>/synthesis/literature-review", methods=["POST"]
)
@login_required
def literature_review(project_id):
    """Generate a literature review draft from project evidence.

    Request body::

        {"theme": "optional theme filter"}
    """
    _require_feature()
    project = get_project_or_404(project_id)
    if project.owner_id != current_user.id:
        return jsonify({"error": "Not authorized"}), 403

    from app.services.literature_review_draft_service import (
        LiteratureReviewDraftService,
    )

    # Gather all evidence snippets
    items = EvidenceItem.query.filter_by(project_id=project.id).all()
    snippets = [
        {
            "text": item.claim_text
            + (": " + item.verbatim_quote if item.verbatim_quote else ""),
            "document_id": item.document_id,
            "doi": "",
        }
        for item in items
    ]

    if not snippets:
        return jsonify(
            {"error": "No evidence items in this project. Add evidence first."}
        ), 400

    data = request.get_json() or {}
    payload, status = LiteratureReviewDraftService().generate_draft(
        project, snippets, max_themes=int(data.get("max_themes", 5))
    )
    return jsonify(payload), status


# ---------------------------------------------------------------------------
# Flag incorrect polarity in evidence row
# ---------------------------------------------------------------------------


@synthesis_bp.route(
    "/projects/<int:project_id>/synthesis/<int:report_id>/evidence/<int:row>/flag",
    methods=["POST"],
)
@login_required
def flag_evidence(project_id, report_id, row):
    """Flag an evidence row as having incorrect polarity.

    Request body::

        {"correct_polarity": "supporting"}
    """
    _require_feature()
    project = get_project_or_404(project_id)

    report = SynthesisReport.query.filter_by(
        id=report_id, project_id=project.id
    ).first()
    if report is None:
        return jsonify({"error": "Report not found"}), 404

    data = request.get_json() or {}
    correct_polarity = data.get("correct_polarity", "mentioning")

    evidence = report.evidence_json or []
    if 0 <= row < len(evidence):
        evidence[row]["polarity"] = correct_polarity
        evidence[row]["flagged_by"] = current_user.id
        report.evidence_json = evidence
        from app.database import db

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({"error": "Failed to flag evidence"}), 500

    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Retraction check
# ---------------------------------------------------------------------------


@synthesis_bp.route(
    "/projects/<int:project_id>/synthesis/check-retractions", methods=["POST"]
)
@login_required
def check_retractions(project_id):
    """Check all project references for retractions."""
    _require_feature()
    project = get_project_or_404(project_id)
    if project.owner_id != current_user.id:
        return jsonify({"error": "Not authorized"}), 403

    from app.services.retraction_alert_service import RetractionAlertService

    alerts = RetractionAlertService().check_project_references(project_id)
    return jsonify(
        {
            "ok": True,
            "new_retractions": len(alerts),
            "retractions": alerts,
        }
    )
