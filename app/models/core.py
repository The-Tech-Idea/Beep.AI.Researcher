"""Core models — User, Role (py-web skill)."""
from datetime import timedelta
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from app.database import db
from app.core.time_utils import utcnow_naive


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    permissions = db.Column(db.Text)

    def get_permissions(self):
        import json
        return json.loads(self.permissions or '[]')

    def set_permissions(self, perms):
        import json
        self.permissions = json.dumps(perms)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255))
    email = db.Column(db.String(120))
    is_active = db.Column(db.Boolean, default=True)
    email_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(120), nullable=True)
    verification_token_expires = db.Column(db.DateTime, nullable=True)
    display_name = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))

    # ── Quota / plan tier (Phase 1.2) ─────────────────────────────────────────
    # NULL = inherit quota from plan tier → tenant pool → global config defaults
    storage_quota_bytes = db.Column(db.BigInteger, nullable=True)
    document_quota = db.Column(db.Integer, nullable=True)
    plan_tier_id = db.Column(db.Integer, db.ForeignKey('plan_tiers.id'), nullable=True)

    # Invite tracking (Phase 8.1)
    invite_id = db.Column(db.Integer, db.ForeignKey('user_invites.id'), nullable=True)

    # ── Account lockout (Phase 8.1) ───────────────────────────────────────────
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    # ── Password policy (Phase 8.2) ───────────────────────────────────────────
    password_changed_at = db.Column(db.DateTime)
    must_change_password = db.Column(db.Boolean, default=False)

    # ── Profile (Phase 8.3) ───────────────────────────────────────────────────
    avatar_url = db.Column(db.String(255))
    bio = db.Column(db.Text)
    phone_number = db.Column(db.String(30))
    locale = db.Column(db.String(10), default='en')
    timezone = db.Column(db.String(50), default='UTC')

    # ── MFA (Phase 8.3) ───────────────────────────────────────────────────────
    mfa_enabled = db.Column(db.Boolean, default=False)
    mfa_methods = db.Column(db.String(100), default='')
    # Comma-separated active methods: e.g. 'totp,email'
    mfa_totp_secret = db.Column(db.String(64))
    # AES-256-GCM encrypted TOTP seed (base32); NULL if TOTP not enrolled
    mfa_backup_codes_hash = db.Column(db.Text)
    # JSON list of bcrypt hashes; each hash consumed at most once
    mfa_backup_codes_remaining = db.Column(db.Integer, default=0)
    mfa_last_used_at = db.Column(db.DateTime)

    role = db.relationship('Role', backref='users')

    @property
    def is_admin(self):
        """True if user has Admin role."""
        return self.role and self.role.name == 'Admin'

    def generate_verification_token(self, expires_hours=24):
        """Generate token for email verification."""
        import secrets
        self.verification_token = secrets.token_urlsafe(32)
        self.verification_token_expires = utcnow_naive() + timedelta(hours=expires_hours)

    def set_password(self, password: str) -> None:
        """Hash and store a user password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Validate password against stored hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


class AuditLog(db.Model):
    """Phase 3: Audit logging for researcher actions."""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    resource = db.Column(db.String(255))
    resource_id = db.Column(db.String(100))
    project_id = db.Column(db.Integer)  # FK to research_projects, no relation to avoid circular
    created_at = db.Column(db.DateTime, default=utcnow_naive)
