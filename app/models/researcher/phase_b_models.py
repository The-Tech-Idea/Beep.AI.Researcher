"""Phase B.2 DB Models — Compliance Policies & Templates.

Replaces the old config_manager-based retention storage with proper DB rows.
"""
from app.core.time_utils import utcnow_naive
from app.database import db


# ─────────────────────────────────────────────────────────────
#  CompliancePolicyTemplate  (seeded built-ins, read-only)
# ─────────────────────────────────────────────────────────────

class CompliancePolicyTemplate(db.Model):
    """Catalogue of built-in compliance policy definitions."""
    __tablename__ = 'compliance_policy_templates'

    id = db.Column(db.Integer, primary_key=True)

    # hipaa | ferpa | gdpr | soc2 | foia | records_retention
    name = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    retention_days = db.Column(db.Integer)          # None = indefinite
    auto_destroy = db.Column(db.Boolean, default=False)
    requires_encryption = db.Column(db.Boolean, default=False)
    requires_audit_log = db.Column(db.Boolean, default=False)
    applicable_sectors = db.Column(db.JSON)         # ['medical', 'education', …]
    regulatory_reference = db.Column(db.String(255))
    is_builtin = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'retention_days': self.retention_days,
            'auto_destroy': self.auto_destroy,
            'requires_encryption': self.requires_encryption,
            'requires_audit_log': self.requires_audit_log,
            'applicable_sectors': self.applicable_sectors or [],
            'regulatory_reference': self.regulatory_reference,
            'is_builtin': self.is_builtin,
        }


# ─────────────────────────────────────────────────────────────
#  RetentionPolicy  (per-project DB row, replaces config_manager)
# ─────────────────────────────────────────────────────────────

class RetentionPolicy(db.Model):
    """Per-project retention & compliance policy (DB-backed)."""
    __tablename__ = 'retention_policies'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey('research_projects.id', ondelete='CASCADE'),
        nullable=False, unique=True, index=True,
    )

    # Which built-in template was applied (nullable = custom)
    template_name = db.Column(db.String(50))

    retention_days = db.Column(db.Integer)      # None = indefinite
    action = db.Column(db.String(20), default='flag')
    auto_destroy = db.Column(db.Boolean, default=False)

    # Legal-hold overrides auto-destroy
    is_legal_hold = db.Column(db.Boolean, default=False, index=True)
    hold_reason = db.Column(db.Text)
    hold_placed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    hold_placed_at = db.Column(db.DateTime)

    requires_encryption = db.Column(db.Boolean, default=False)
    requires_audit_log = db.Column(db.Boolean, default=False)

    # Stored JSON: {'issued_at': '...', 'issued_by': 1, 'method': 'secure_erase'}
    destruction_certificate_json = db.Column(db.JSON)

    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    project = db.relationship('ResearchProject', backref=db.backref('retention_policy', uselist=False))

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'template_name': self.template_name,
            'retention_days': self.retention_days,
            'action': self.action,
            'auto_destroy': self.auto_destroy,
            'is_legal_hold': self.is_legal_hold,
            'hold_reason': self.hold_reason,
            'hold_placed_by': self.hold_placed_by,
            'hold_placed_at': self.hold_placed_at.isoformat() if self.hold_placed_at else None,
            'requires_encryption': self.requires_encryption,
            'requires_audit_log': self.requires_audit_log,
            'destruction_certificate_json': self.destruction_certificate_json,
            'notes': self.notes,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


# ─────────────────────────────────────────────────────────────
#  Built-in seed helper
# ─────────────────────────────────────────────────────────────

BUILTIN_TEMPLATES = [
    {
        'name': 'hipaa',
        'display_name': 'HIPAA',
        'description': 'Health Insurance Portability and Accountability Act — PHI retention rules.',
        'retention_days': 2190,  # 6 years
        'auto_destroy': False,
        'requires_encryption': True,
        'requires_audit_log': True,
        'applicable_sectors': ['medical'],
        'regulatory_reference': '45 CFR Parts 160 and 164',
    },
    {
        'name': 'ferpa',
        'display_name': 'FERPA',
        'description': 'Family Educational Rights and Privacy Act — student education record rules.',
        'retention_days': 1825,  # 5 years
        'auto_destroy': False,
        'requires_encryption': True,
        'requires_audit_log': True,
        'applicable_sectors': ['education'],
        'regulatory_reference': '20 U.S.C. § 1232g; 34 CFR Part 99',
    },
    {
        'name': 'gdpr',
        'display_name': 'GDPR',
        'description': 'General Data Protection Regulation — EU data minimization & erasure.',
        'retention_days': 1095,  # 3 years default; varies by activity
        'auto_destroy': True,
        'requires_encryption': True,
        'requires_audit_log': True,
        'applicable_sectors': [],
        'regulatory_reference': 'Regulation (EU) 2016/679',
    },
    {
        'name': 'soc2',
        'display_name': 'SOC 2',
        'description': 'Service Organization Control 2 — security, availability, and confidentiality.',
        'retention_days': 2555,  # 7 years
        'auto_destroy': False,
        'requires_encryption': True,
        'requires_audit_log': True,
        'applicable_sectors': [],
        'regulatory_reference': 'AICPA TSP 100-A',
    },
    {
        'name': 'foia',
        'display_name': 'FOIA',
        'description': 'Freedom of Information Act — federal government record disclosure rules.',
        'retention_days': None,  # governs access, not destruction
        'auto_destroy': False,
        'requires_encryption': False,
        'requires_audit_log': True,
        'applicable_sectors': ['government'],
        'regulatory_reference': '5 U.S.C. § 552',
    },
    {
        'name': 'records_retention',
        'display_name': 'General Records Retention',
        'description': 'Standard organisation-level data lifecycle control.',
        'retention_days': 2555,  # 7 years
        'auto_destroy': True,
        'requires_encryption': False,
        'requires_audit_log': False,
        'applicable_sectors': [],
        'regulatory_reference': None,
    },
]


def seed_compliance_templates():
    """Idempotent: insert missing built-in template rows."""
    for tpl in BUILTIN_TEMPLATES:
        existing = CompliancePolicyTemplate.query.filter_by(name=tpl['name']).first()
        if not existing:
            row = CompliancePolicyTemplate(**tpl, is_builtin=True)
            db.session.add(row)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
