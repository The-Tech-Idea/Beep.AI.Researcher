"""Phase 3: Multi-tenancy — Tenant (org/workspace) and TenantMember."""
from app.database import db
from app.core.time_utils import utcnow_naive


class Tenant(db.Model):
    """Organization/workspace with isolation."""
    __tablename__ = 'tenants'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)

    # ── Quota / plan tier (Phase 1.2) ─────────────────────────────────────────
    # Members draw from TenantQuota pool unless overridden at the user level.
    plan_tier_id = db.Column(db.Integer, db.ForeignKey('plan_tiers.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow_naive)

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name, 'slug': self.slug,
            'plan_tier_id': self.plan_tier_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class TenantMember(db.Model):
    """Tenant membership (admin, member)."""
    __tablename__ = 'tenant_members'
    __table_args__ = (db.UniqueConstraint('tenant_id', 'user_id', name='uq_tenant_member'),)

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(50), default='member')  # admin | member
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    tenant = db.relationship('Tenant', backref='members')
    user = db.relationship('User', backref='tenant_memberships')
