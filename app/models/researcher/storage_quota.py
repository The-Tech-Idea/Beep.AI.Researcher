"""Storage quota models — PlanTier, TenantQuota, UserStorageStats.

These models underpin the hierarchical quota system:
  User override → Tenant pool → Plan tier → Global defaults (config_manager)

Alembic migration: migrations/add_quota_user_management_integrations.py
"""
from app.database import db
from app.core.time_utils import utcnow_naive


class PlanTier(db.Model):
    """Defines storage/document limits for a subscription tier or enterprise plan."""
    __tablename__ = 'plan_tiers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    # "Free", "Standard", "Enterprise", "Custom"

    # Quota limits — NULL means unlimited
    storage_quota_bytes = db.Column(db.BigInteger, default=1_073_741_824)   # default 1 GB
    document_quota = db.Column(db.Integer, default=500)
    project_quota = db.Column(db.Integer, default=10)
    api_calls_per_day = db.Column(db.Integer, default=1000)
    max_upload_size_bytes = db.Column(db.BigInteger, default=52_428_800)    # default 50 MB

    # Display / billing
    price_display = db.Column(db.String(40))    # display only, e.g. "$0/mo"
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    # Relationships
    users = db.relationship('User', backref='plan_tier', lazy='dynamic',
                            foreign_keys='User.plan_tier_id')
    tenant_quotas = db.relationship('TenantQuota', backref='plan_tier', lazy='dynamic')
    user_invites = db.relationship('UserInvite', backref='plan_tier', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'storage_quota_bytes': self.storage_quota_bytes,
            'document_quota': self.document_quota,
            'project_quota': self.project_quota,
            'api_calls_per_day': self.api_calls_per_day,
            'max_upload_size_bytes': self.max_upload_size_bytes,
            'price_display': self.price_display,
            'description': self.description,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class TenantQuota(db.Model):
    """Per-tenant pool quota. Members draw from this pool unless overridden at user level."""
    __tablename__ = 'tenant_quotas'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), unique=True, nullable=False)
    plan_tier_id = db.Column(db.Integer, db.ForeignKey('plan_tiers.id'), nullable=True)

    # Explicit overrides (NULL = use plan tier or global default)
    storage_quota_bytes = db.Column(db.BigInteger, nullable=True)
    document_quota = db.Column(db.Integer, nullable=True)
    max_upload_size_bytes = db.Column(db.BigInteger, nullable=True)

    # Live usage (updated atomically on upload/delete)
    used_storage_bytes = db.Column(db.BigInteger, default=0)
    document_count = db.Column(db.Integer, default=0)

    last_recalculated_at = db.Column(db.DateTime)

    tenant = db.relationship('Tenant', backref=db.backref('quota', uselist=False))

    def to_dict(self):
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'plan_tier_id': self.plan_tier_id,
            'storage_quota_bytes': self.storage_quota_bytes,
            'document_quota': self.document_quota,
            'used_storage_bytes': self.used_storage_bytes,
            'document_count': self.document_count,
            'last_recalculated_at': self.last_recalculated_at.isoformat()
            if self.last_recalculated_at else None,
        }


class UserStorageStats(db.Model):
    """Live usage tracker per user. Updated atomically on every upload/delete."""
    __tablename__ = 'user_storage_stats'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)

    used_storage_bytes = db.Column(db.BigInteger, default=0)
    document_count = db.Column(db.Integer, default=0)

    last_upload_at = db.Column(db.DateTime)
    last_recalculated_at = db.Column(db.DateTime)

    user = db.relationship('User', backref=db.backref('storage_stats', uselist=False))

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'used_storage_bytes': self.used_storage_bytes,
            'document_count': self.document_count,
            'last_upload_at': self.last_upload_at.isoformat() if self.last_upload_at else None,
            'last_recalculated_at': self.last_recalculated_at.isoformat()
            if self.last_recalculated_at else None,
        }
