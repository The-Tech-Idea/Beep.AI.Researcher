"""Phase B.2 — Compliance Policy Routes.

Replaces the old config_manager-based retention.py logic with DB-backed
RetentionPolicy rows and a catalogue of built-in CompliancePolicyTemplates.

Registered with url_prefix='/projects' in app/__init__.py.
Legacy /projects/<id>/retention GET+PUT still works (backward compat).
"""
from flask import Blueprint, request, jsonify

from app.core.time_utils import utcnow_naive
from app.database import db
from app.models.researcher import ResearchProject
from app.models.researcher.phase_b_models import (
    RetentionPolicy, CompliancePolicyTemplate, seed_compliance_templates,
)
from app.routes.route_entity_lookup import get_entity_or_404

compliance_bp = Blueprint('compliance', __name__)


def _get_project_or_404(project_id):
    return get_entity_or_404(ResearchProject, project_id)


def _ensure_templates_seeded():
    """Lazy-seed built-in templates if none exist yet."""
    if CompliancePolicyTemplate.query.count() == 0:
        seed_compliance_templates()


# ─── Template catalogue (read-only) ──────────────────────────

@compliance_bp.route('/compliance-templates', methods=['GET'])
def list_compliance_templates():
    """Return all built-in compliance policy templates."""
    _ensure_templates_seeded()
    sector = request.args.get('sector')
    q = CompliancePolicyTemplate.query
    if sector:
        # JSON column: filter rows whose applicable_sectors list contains the value
        q = q.filter(CompliancePolicyTemplate.applicable_sectors.contains(sector))
    templates = q.order_by(CompliancePolicyTemplate.name).all()
    return jsonify({'templates': [t.to_dict() for t in templates]})


@compliance_bp.route('/compliance-templates/<string:name>', methods=['GET'])
def get_compliance_template(name):
    _ensure_templates_seeded()
    tpl = CompliancePolicyTemplate.query.filter_by(name=name).first_or_404()
    return jsonify(tpl.to_dict())


# ─── Per-project policy ──────────────────────────────────────

@compliance_bp.route('/<int:project_id>/compliance-policy', methods=['GET'])
def get_compliance_policy(project_id):
    """Return the active compliance policy for a project."""
    _get_project_or_404(project_id)
    policy = RetentionPolicy.query.filter_by(project_id=project_id).first()
    if not policy:
        return jsonify({'project_id': project_id, 'policy': None}), 200
    return jsonify({'project_id': project_id, 'policy': policy.to_dict()})


@compliance_bp.route('/<int:project_id>/compliance-policy', methods=['PUT'])
def set_compliance_policy(project_id):
    """Create or update a project's compliance policy.

    Body can include:
      template_name, retention_days, auto_destroy, is_legal_hold,
      hold_reason, hold_placed_by, requires_encryption,
      requires_audit_log, notes
    """
    _get_project_or_404(project_id)
    data = request.get_json() or {}

    policy = RetentionPolicy.query.filter_by(project_id=project_id).first()
    if not policy:
        policy = RetentionPolicy(project_id=project_id)
        db.session.add(policy)

    # If a template_name is provided, pre-fill from catalogue
    template_name = data.get('template_name')
    if template_name:
        _ensure_templates_seeded()
        tpl = CompliancePolicyTemplate.query.filter_by(name=template_name).first()
        if tpl:
            policy.template_name = tpl.name
            policy.retention_days = tpl.retention_days
            policy.action = 'delete' if tpl.auto_destroy else 'flag'
            policy.auto_destroy = tpl.auto_destroy
            policy.requires_encryption = tpl.requires_encryption
            policy.requires_audit_log = tpl.requires_audit_log
        else:
            policy.template_name = template_name

    # Allow explicit overrides on top of template defaults
    OVERRIDEABLE = ('retention_days', 'auto_destroy', 'requires_encryption',
                    'requires_audit_log', 'notes', 'is_active')
    for field in OVERRIDEABLE:
        if field in data:
            setattr(policy, field, data[field])

    if 'action' in data:
        action = (data.get('action') or 'flag').strip().lower()
        if action not in {'flag', 'archive', 'delete'}:
            return jsonify({'error': 'invalid action'}), 400
        policy.action = action
        policy.auto_destroy = action == 'delete'

    # Legal-hold management
    if 'is_legal_hold' in data:
        placing_hold = bool(data['is_legal_hold'])
        if placing_hold and not policy.is_legal_hold:
            policy.is_legal_hold = True
            policy.hold_reason = data.get('hold_reason')
            policy.hold_placed_by = data.get('hold_placed_by')
            policy.hold_placed_at = utcnow_naive()
        elif not placing_hold and policy.is_legal_hold:
            policy.is_legal_hold = False
            policy.hold_reason = None
            policy.hold_placed_at = None

    policy.updated_at = utcnow_naive()
    db.session.commit()
    return jsonify(policy.to_dict())


@compliance_bp.route('/<int:project_id>/compliance-policy/hold', methods=['POST'])
def place_legal_hold(project_id):
    """Shortcut: place a legal hold on a project."""
    _get_project_or_404(project_id)
    data = request.get_json() or {}

    policy = RetentionPolicy.query.filter_by(project_id=project_id).first()
    if not policy:
        policy = RetentionPolicy(project_id=project_id)
        db.session.add(policy)

    policy.is_legal_hold = True
    policy.hold_reason = data.get('hold_reason', 'Legal hold placed via API')
    policy.hold_placed_by = data.get('hold_placed_by')
    policy.hold_placed_at = utcnow_naive()
    policy.auto_destroy = False   # Holds must block destruction
    policy.updated_at = utcnow_naive()
    db.session.commit()
    return jsonify(policy.to_dict()), 201


@compliance_bp.route('/<int:project_id>/compliance-policy/hold', methods=['DELETE'])
def release_legal_hold(project_id):
    """Release the legal hold on a project."""
    _get_project_or_404(project_id)
    policy = RetentionPolicy.query.filter_by(project_id=project_id).first_or_404()

    if not policy.is_legal_hold:
        return jsonify({'error': 'no legal hold is active for this project'}), 409

    policy.is_legal_hold = False
    policy.hold_reason = None
    policy.hold_placed_at = None
    policy.updated_at = utcnow_naive()
    db.session.commit()
    return jsonify({'ok': True, 'policy': policy.to_dict()})


@compliance_bp.route('/<int:project_id>/compliance-policy/destruction-certificate', methods=['POST'])
def issue_destruction_certificate(project_id):
    """Record that data was destroyed, storing a destruction certificate."""
    _get_project_or_404(project_id)
    policy = RetentionPolicy.query.filter_by(project_id=project_id).first_or_404()

    if policy.is_legal_hold:
        return jsonify({'error': 'cannot issue destruction certificate while legal hold is active'}), 409

    data = request.get_json() or {}
    cert = {
        'issued_at': utcnow_naive().isoformat(),
        'issued_by': data.get('issued_by'),
        'method': data.get('method', 'secure_erase'),
        'scope': data.get('scope', 'all_project_data'),
        'notes': data.get('notes'),
    }
    policy.destruction_certificate_json = cert
    policy.is_active = False
    policy.updated_at = utcnow_naive()
    db.session.commit()
    return jsonify({'ok': True, 'certificate': cert})


# ─── Backward-compat: legacy /retention GET+PUT ──────────────

@compliance_bp.route('/<int:project_id>/retention', methods=['GET'])
def get_retention_compat(project_id):
    """Legacy compat — returns retention_days (now sourced from DB)."""
    _get_project_or_404(project_id)
    policy = RetentionPolicy.query.filter_by(project_id=project_id).first()
    return jsonify({
        'project_id': project_id,
        'retention_days': policy.retention_days if policy else None,
        'action': policy.action if policy and getattr(policy, 'action', None) else 'flag',
    })


@compliance_bp.route('/<int:project_id>/retention', methods=['PUT'])
def set_retention_compat(project_id):
    """Legacy compat — sets only retention_days (upserts DB row)."""
    _get_project_or_404(project_id)
    data = request.get_json() or {}
    retention_days = data.get('retention_days')
    action = (data.get('action') or 'flag').strip().lower()
    if action not in {'flag', 'archive', 'delete'}:
        return jsonify({'error': 'invalid action'}), 400

    policy = RetentionPolicy.query.filter_by(project_id=project_id).first()
    if not policy:
        policy = RetentionPolicy(project_id=project_id)
        db.session.add(policy)

    policy.retention_days = retention_days
    policy.action = action
    policy.updated_at = utcnow_naive()
    db.session.commit()
    return jsonify({'project_id': project_id, 'retention_days': retention_days, 'action': action})
