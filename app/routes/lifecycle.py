"""Phase B.1 — Research Lifecycle Routes.

CRUD for ResearchBrief, Claim, EvidenceItem, and ReviewStep.
All blueprints are registered under /projects in app/__init__.py.
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required
from app.core.time_utils import utcnow_naive

from app.database import db
from app.models.researcher import (
    ResearchProject,
    ResearchBrief,
    Claim,
    ClaimEvidence,
    EvidenceItem,
    ReviewStep,
)
from app.routes.route_entity_lookup import get_entity_or_404, get_project_or_404

lifecycle_bp = Blueprint("lifecycle", __name__)


# ─────────────────────────────────────────────────────────────
#  ResearchBrief  GET/POST  /projects/<id>/briefs
# ─────────────────────────────────────────────────────────────


@lifecycle_bp.route("/<int:project_id>/briefs", methods=["GET"])
@login_required
def list_briefs(project_id):
    project = get_project_or_404(project_id)
    sector = request.args.get("sector")
    status = request.args.get("status")

    q = ResearchBrief.query.filter_by(project_id=project.id)
    if sector:
        q = q.filter_by(sector=sector)
    if status:
        q = q.filter_by(status=status)

    return jsonify(
        {
            "briefs": [
                b.to_dict() for b in q.order_by(ResearchBrief.created_at.desc()).all()
            ]
        }
    )


@lifecycle_bp.route("/<int:project_id>/briefs", methods=["POST"])
@login_required
def create_brief(project_id):
    project = get_project_or_404(project_id)
    data = request.get_json() or {}

    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title required"}), 400

    brief = ResearchBrief(
        project_id=project.id,
        title=title,
        sector=data.get("sector"),
        summary_text=data.get("summary_text") or data.get("summary"),
        status=data.get("status", "draft"),
        compliance_frameworks=data.get("compliance_frameworks"),
        key_findings=data.get("key_findings"),
        llm_model_used=data.get("llm_model_used"),
    )
    db.session.add(brief)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to create brief"}), 500
    return jsonify(brief.to_dict()), 201


@lifecycle_bp.route("/<int:project_id>/briefs/<int:brief_id>", methods=["GET"])
@login_required
def get_brief(project_id, brief_id):
    get_project_or_404(project_id)
    brief = ResearchBrief.query.filter_by(
        id=brief_id, project_id=project_id
    ).first_or_404()
    return jsonify(brief.to_dict())


@lifecycle_bp.route("/<int:project_id>/briefs/<int:brief_id>", methods=["PUT"])
@login_required
def update_brief(project_id, brief_id):
    get_project_or_404(project_id)
    brief = ResearchBrief.query.filter_by(
        id=brief_id, project_id=project_id
    ).first_or_404()
    data = request.get_json() or {}

    ALLOWED = (
        "title",
        "sector",
        "summary_text",
        "status",
        "compliance_frameworks",
        "key_findings",
        "llm_model_used",
    )
    for field in ALLOWED:
        if field in data:
            setattr(brief, field, data[field])

    brief.updated_at = utcnow_naive()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to update brief"}), 500
    return jsonify(brief.to_dict())


@lifecycle_bp.route("/<int:project_id>/briefs/<int:brief_id>", methods=["DELETE"])
@login_required
def delete_brief(project_id, brief_id):
    get_project_or_404(project_id)
    brief = ResearchBrief.query.filter_by(
        id=brief_id, project_id=project_id
    ).first_or_404()
    db.session.delete(brief)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to delete brief"}), 500
    return jsonify({"ok": True}), 204


# ─────────────────────────────────────────────────────────────
#  Claim  GET/POST  /projects/<id>/claims
# ─────────────────────────────────────────────────────────────


@lifecycle_bp.route("/<int:project_id>/claims", methods=["GET"])
@login_required
def list_claims(project_id):
    project = get_project_or_404(project_id)
    verdict = request.args.get("verdict")
    sector = request.args.get("sector")

    q = Claim.query.filter_by(project_id=project.id)
    if verdict:
        q = q.filter_by(verdict=verdict)
    if sector:
        q = q.filter_by(sector=sector)

    claims = q.order_by(Claim.created_at.desc()).all()
    return jsonify({"claims": [c.to_dict() for c in claims]})


@lifecycle_bp.route("/<int:project_id>/claims", methods=["POST"])
@login_required
def create_claim(project_id):
    project = get_project_or_404(project_id)
    data = request.get_json() or {}

    claim_text = (data.get("claim_text") or "").strip()
    if not claim_text:
        return jsonify({"error": "claim_text required"}), 400

    claim = Claim(
        project_id=project.id,
        claim_text=claim_text,
        claim_type=data.get("claim_type", "factual"),
        sector=data.get("sector"),
        verdict=data.get("verdict", "unclear"),
        confidence_score=data.get("confidence_score"),
        source_brief_id=data.get("source_brief_id"),
        created_by=data.get("created_by"),
    )
    db.session.add(claim)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to create claim"}), 500
    return jsonify(claim.to_dict()), 201


@lifecycle_bp.route("/<int:project_id>/claims/<int:claim_id>", methods=["GET"])
@login_required
def get_claim(project_id, claim_id):
    get_project_or_404(project_id)
    claim = Claim.query.filter_by(id=claim_id, project_id=project_id).first_or_404()

    d = claim.to_dict()
    links = ClaimEvidence.query.filter_by(claim_id=claim_id).all()
    d["evidence_links"] = [lnk.to_dict() for lnk in links]
    return jsonify(d)


@lifecycle_bp.route("/<int:project_id>/claims/<int:claim_id>", methods=["PUT"])
@login_required
def update_claim(project_id, claim_id):
    get_project_or_404(project_id)
    claim = Claim.query.filter_by(id=claim_id, project_id=project_id).first_or_404()
    data = request.get_json() or {}

    ALLOWED = (
        "claim_text",
        "claim_type",
        "sector",
        "verdict",
        "confidence_score",
        "source_brief_id",
    )
    for field in ALLOWED:
        if field in data:
            setattr(claim, field, data[field])

    claim.updated_at = utcnow_naive()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to update claim"}), 500
    return jsonify(claim.to_dict())


@lifecycle_bp.route("/<int:project_id>/claims/<int:claim_id>", methods=["DELETE"])
@login_required
def delete_claim(project_id, claim_id):
    get_project_or_404(project_id)
    claim = Claim.query.filter_by(id=claim_id, project_id=project_id).first_or_404()
    db.session.delete(claim)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to delete claim"}), 500
    return jsonify({"ok": True}), 204


@lifecycle_bp.route(
    "/<int:project_id>/claims/<int:claim_id>/evidence", methods=["POST"]
)
@login_required
def link_evidence_to_claim(project_id, claim_id):
    get_project_or_404(project_id)
    Claim.query.filter_by(id=claim_id, project_id=project_id).first_or_404()
    data = request.get_json() or {}

    evidence_id = data.get("evidence_id")
    if not evidence_id:
        return jsonify({"error": "evidence_id required"}), 400

    EvidenceItem.query.filter_by(id=evidence_id, project_id=project_id).first_or_404()

    existing = ClaimEvidence.query.filter_by(
        claim_id=claim_id, evidence_id=evidence_id
    ).first()
    if existing:
        existing.role = data.get("role", existing.role)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({"error": "Failed to update evidence link"}), 500
        return jsonify(existing.to_dict())

    link = ClaimEvidence(
        claim_id=claim_id,
        evidence_id=evidence_id,
        role=data.get("role", "supporting"),
        added_by=data.get("added_by"),
    )
    db.session.add(link)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to link evidence"}), 500
    return jsonify(link.to_dict()), 201


# ─────────────────────────────────────────────────────────────
#  EvidenceItem  GET/POST  /projects/<id>/evidence
# ─────────────────────────────────────────────────────────────


@lifecycle_bp.route("/<int:project_id>/evidence", methods=["GET"])
@login_required
def list_evidence(project_id):
    project = get_project_or_404(project_id)
    strength = request.args.get("strength")
    direction = request.args.get("direction")
    doc_id = request.args.get("document_id", type=int)

    q = EvidenceItem.query.filter_by(project_id=project.id)
    if strength:
        q = q.filter_by(strength=strength)
    if direction:
        q = q.filter_by(direction=direction)
    if doc_id:
        q = q.filter_by(document_id=doc_id)

    items = q.order_by(EvidenceItem.created_at.desc()).all()
    return jsonify({"evidence": [e.to_dict() for e in items]})


@lifecycle_bp.route("/<int:project_id>/evidence", methods=["POST"])
@login_required
def create_evidence(project_id):
    project = get_project_or_404(project_id)
    data = request.get_json() or {}

    claim_text = (data.get("claim_text") or "").strip()
    if not claim_text:
        return jsonify({"error": "claim_text required"}), 400

    item = EvidenceItem(
        project_id=project.id,
        document_id=data.get("document_id"),
        claim_text=claim_text,
        verbatim_quote=data.get("verbatim_quote"),
        strength=data.get("strength", "moderate"),
        direction=data.get("direction", "neutral"),
        evidence_type=data.get("evidence_type", "document"),
        source_location=data.get("source_location"),
        extraction_method=data.get("extraction_method", "manual"),
        confidence_score=data.get("confidence_score"),
        tags=data.get("tags", []),
    )
    db.session.add(item)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to create evidence"}), 500
    return jsonify(item.to_dict()), 201


@lifecycle_bp.route("/<int:project_id>/evidence/<int:ev_id>", methods=["GET"])
@login_required
def get_evidence(project_id, ev_id):
    get_project_or_404(project_id)
    item = EvidenceItem.query.filter_by(id=ev_id, project_id=project_id).first_or_404()
    return jsonify(item.to_dict())


@lifecycle_bp.route("/<int:project_id>/evidence/<int:ev_id>", methods=["PUT"])
@login_required
def update_evidence(project_id, ev_id):
    get_project_or_404(project_id)
    item = EvidenceItem.query.filter_by(id=ev_id, project_id=project_id).first_or_404()
    data = request.get_json() or {}

    ALLOWED = (
        "claim_text",
        "verbatim_quote",
        "strength",
        "direction",
        "evidence_type",
        "source_location",
        "extraction_method",
        "confidence_score",
        "tags",
        "document_id",
    )
    for field in ALLOWED:
        if field in data:
            setattr(item, field, data[field])

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to update evidence"}), 500
    return jsonify(item.to_dict())


@lifecycle_bp.route("/<int:project_id>/evidence/<int:ev_id>", methods=["DELETE"])
@login_required
def delete_evidence(project_id, ev_id):
    get_project_or_404(project_id)
    item = EvidenceItem.query.filter_by(id=ev_id, project_id=project_id).first_or_404()
    db.session.delete(item)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to delete evidence"}), 500
    return jsonify({"ok": True}), 204


# ─────────────────────────────────────────────────────────────
#  ReviewStep  GET/POST  /projects/<id>/reviews
# ─────────────────────────────────────────────────────────────


@lifecycle_bp.route("/<int:project_id>/reviews", methods=["GET"])
@login_required
def list_reviews(project_id):
    project = get_project_or_404(project_id)
    stage = request.args.get("stage")
    decision = request.args.get("decision")
    doc_id = request.args.get("document_id", type=int)

    q = ReviewStep.query.filter_by(project_id=project.id)
    if stage:
        q = q.filter_by(stage=stage)
    if decision:
        q = q.filter_by(decision=decision)
    if doc_id:
        q = q.filter_by(document_id=doc_id)

    steps = q.order_by(ReviewStep.created_at.desc()).all()
    return jsonify({"reviews": [s.to_dict() for s in steps]})


@lifecycle_bp.route("/<int:project_id>/reviews", methods=["POST"])
@login_required
def create_review(project_id):
    project = get_project_or_404(project_id)
    data = request.get_json() or {}

    stage = (data.get("stage") or "").strip()
    if not stage:
        return jsonify({"error": "stage required"}), 400

    VALID_STAGES = (
        "identification",
        "screening",
        "eligibility",
        "included",
        "excluded",
    )
    if stage not in VALID_STAGES:
        return jsonify({"error": f"stage must be one of {VALID_STAGES}"}), 400

    step = ReviewStep(
        project_id=project.id,
        document_id=data.get("document_id"),
        stage=stage,
        decision=data.get("decision", "uncertain"),
        exclusion_reason=data.get("exclusion_reason"),
        notes=data.get("notes"),
        performed_by=data.get("performed_by"),
        is_automated=data.get("is_automated", False),
        automation_confidence=data.get("automation_confidence"),
    )
    db.session.add(step)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to create review"}), 500
    return jsonify(step.to_dict()), 201


@lifecycle_bp.route("/<int:project_id>/reviews/<int:step_id>", methods=["GET"])
@login_required
def get_review(project_id, step_id):
    get_project_or_404(project_id)
    step = ReviewStep.query.filter_by(id=step_id, project_id=project_id).first_or_404()
    return jsonify(step.to_dict())


@lifecycle_bp.route("/<int:project_id>/reviews/<int:step_id>/sign-off", methods=["PUT"])
@login_required
def sign_off_review(project_id, step_id):
    get_project_or_404(project_id)
    step = ReviewStep.query.filter_by(id=step_id, project_id=project_id).first_or_404()

    if getattr(step, "is_signed_off", False):
        return jsonify({"error": "review step already signed off"}), 409

    data = request.get_json() or {}
    decision = data.get("decision", step.decision)

    VALID_DECISIONS = ("pass", "exclude", "uncertain")
    if decision not in VALID_DECISIONS:
        return jsonify({"error": f"decision must be one of {VALID_DECISIONS}"}), 400

    step.decision = decision
    if data.get("notes"):
        step.notes = data["notes"]
    if data.get("performed_by"):
        step.performed_by = data["performed_by"]

    if hasattr(step, "signature_ip"):
        step.signature_ip = request.remote_addr

    if hasattr(step, "is_signed_off"):
        step.is_signed_off = True
    if hasattr(step, "signed_off_at"):
        step.signed_off_at = utcnow_naive()

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to sign off review"}), 500
    return jsonify(step.to_dict())
