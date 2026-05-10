"""Phase C — PHI Redaction Routes.

Endpoints for scanning and redacting Protected Health Information from project
documents.  Registered with url_prefix='/projects' in app/__init__.py.
"""

from app.core.time_utils import utcnow_naive

from flask import Blueprint, request, jsonify
from flask_login import login_required

from app.database import db
from app.models.researcher import ResearchProject, ResearcherDocument
from app.routes.route_entity_lookup import get_entity_or_404
from app.services.phi_redaction_service import redact_document, phi_report

phi_bp = Blueprint("phi", __name__)


# ─────────────────────────────────────────────────────────────
#  PHI Report  (scan without modifying)
# ─────────────────────────────────────────────────────────────


@phi_bp.route("/<int:project_id>/documents/<int:doc_id>/phi-report", methods=["GET"])
@login_required
def get_phi_report(project_id, doc_id):
    """Scan a document for PHI and return a report without modifying content.

    Response:
      phi_found, total_findings, entity_type_counts, findings[]
    """
    get_entity_or_404(ResearchProject, project_id)
    doc = ResearcherDocument.query.filter_by(
        id=doc_id, project_id=project_id
    ).first_or_404()

    text = doc.text_content or ""
    report = phi_report(text)
    report["document_id"] = doc_id
    report["project_id"] = project_id
    report["phi_previously_redacted"] = bool(getattr(doc, "phi_redacted", False))
    return jsonify(report)


# ─────────────────────────────────────────────────────────────
#  Redact document  (in-place, saves backup)
# ─────────────────────────────────────────────────────────────


@phi_bp.route("/<int:project_id>/documents/<int:doc_id>/redact", methods=["POST"])
@login_required
def redact_doc(project_id, doc_id):
    """Redact PHI from a document's text_content in place.

    Body (optional):
      replacement   — token to replace PHI with (default '[REDACTED]')
      entity_types  — list of entity types to redact (default: all)

    Backs up original text in phi_backup_json before redacting.
    """
    get_entity_or_404(ResearchProject, project_id)
    doc = ResearcherDocument.query.filter_by(
        id=doc_id, project_id=project_id
    ).first_or_404()

    if getattr(doc, "phi_redacted", False):
        return jsonify(
            {
                "error": "document already redacted — restore from phi_backup_json before re-redacting"
            }
        ), 409

    data = request.get_json() or {}
    replacement = data.get("replacement", "[REDACTED]")

    # Backup original text
    if hasattr(doc, "phi_backup_json") and not doc.phi_backup_json:
        doc.phi_backup_json = {
            "original_text": doc.text_content,
            "redacted_at": utcnow_naive().isoformat(),
            "replacement": replacement,
        }

    result = redact_document(doc, replacement=replacement)

    if result["status"] == "ok":
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            result["status"] = "error"
            result["error"] = "failed to save redaction"
            return jsonify(result), 500

    result["document_id"] = doc_id
    result["project_id"] = project_id
    return jsonify(result), 200 if result["status"] == "ok" else 422


@phi_bp.route("/<int:project_id>/documents/<int:doc_id>/redact", methods=["DELETE"])
@login_required
def restore_doc_from_backup(project_id, doc_id):
    """Restore original text from phi_backup_json (undo redaction).

    Only possible if phi_backup_json was saved during redaction.
    """
    get_entity_or_404(ResearchProject, project_id)
    doc = ResearcherDocument.query.filter_by(
        id=doc_id, project_id=project_id
    ).first_or_404()

    backup = getattr(doc, "phi_backup_json", None)
    if not backup or not backup.get("original_text"):
        return jsonify({"error": "no redaction backup found for this document"}), 404

    doc.text_content = backup["original_text"]
    doc.phi_backup_json = None
    doc.phi_detected = False
    doc.phi_redacted = False
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "failed to restore document"}), 500

    return jsonify({"ok": True, "document_id": doc_id})


# ─────────────────────────────────────────────────────────────
#  Bulk PHI report for a project
# ─────────────────────────────────────────────────────────────


@phi_bp.route("/<int:project_id>/phi-report", methods=["GET"])
@login_required
def project_phi_report(project_id):
    """Return PHI scan summary across all documents in a project.

    Respects query param: ?redacted_only=true|false
    """
    project = get_entity_or_404(ResearchProject, project_id)
    redacted_only = request.args.get("redacted_only", "").lower() == "true"

    q = ResearcherDocument.query.filter_by(project_id=project.id)
    if redacted_only:
        q = q.filter_by(phi_redacted=True)

    docs = q.all()
    summary = {
        "project_id": project_id,
        "total_documents": len(docs),
        "documents_with_phi": sum(1 for d in docs if getattr(d, "phi_detected", False)),
        "documents_redacted": sum(1 for d in docs if getattr(d, "phi_redacted", False)),
        "documents": [
            {
                "document_id": d.id,
                "filename": d.filename,
                "phi_detected": getattr(d, "phi_detected", False),
                "phi_redacted": getattr(d, "phi_redacted", False),
            }
            for d in docs
        ],
    }
    return jsonify(summary)
