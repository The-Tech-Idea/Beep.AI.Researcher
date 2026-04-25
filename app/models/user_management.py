"""User management models — UserInvite, PasswordHistory, UserSession.

These models support Phase 8 of the admin enhancement plan:
  - UserInvite:       Token-based invite system for invite_only registration mode.
  - PasswordHistory:  Stores hashed previous passwords to enforce history policy.
  - UserSession:      Server-side session tracking for visibility and remote revocation.

Alembic migration: migrations/add_quota_user_management_integrations.py
"""
from app.database import db
from app.core.time_utils import utcnow_naive


class UserInvite(db.Model):
    """Invite token for invite_only registration mode.

    An admin (or the system) creates an invite with an optional pre-filled email,
    role, and plan tier. The invite URL is /register?invite=<token>.
    The token can be single-use (max_uses=1) or multi-use (max_uses>1 or NULL=unlimited).
    """
    __tablename__ = 'user_invites'

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)   # secrets.token_urlsafe(32)

    # Pre-fill / restrictions
    email = db.Column(db.String(120), nullable=True)                # restrict to this address if set
    role_name = db.Column(db.String(80), nullable=True)             # role to auto-assign on use
    plan_tier_id = db.Column(db.Integer, db.ForeignKey('plan_tiers.id'), nullable=True)

    # Audit
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    expires_at = db.Column(db.DateTime, nullable=True)              # NULL = never expires

    # Usage tracking
    max_uses = db.Column(db.Integer, default=1)                     # NULL = unlimited
    use_count = db.Column(db.Integer, default=0)

    # Populated when a single-use invite is consumed
    used_at = db.Column(db.DateTime, nullable=True)
    used_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Revocation
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_invites')
    used_by = db.relationship('User', foreign_keys=[used_by_id], backref='used_invite')
    revoked_by = db.relationship('User', foreign_keys=[revoked_by_id], backref='revoked_invites')

    @property
    def is_valid(self):
        """True if the invite can still be used."""
        from app.core.time_utils import utcnow_naive as _now
        if self.revoked_at:
            return False
        if self.expires_at and _now() > self.expires_at:
            return False
        if self.max_uses is not None and self.use_count >= self.max_uses:
            return False
        return True

    def to_dict(self):
        return {
            'id': self.id,
            'token': self.token,
            'email': self.email,
            'role_name': self.role_name,
            'plan_tier_id': self.plan_tier_id,
            'created_by_id': self.created_by_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'max_uses': self.max_uses,
            'use_count': self.use_count,
            'is_valid': self.is_valid,
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'revoked_at': self.revoked_at.isoformat() if self.revoked_at else None,
        }


class PasswordHistory(db.Model):
    """Stores hashed previous passwords to enforce the password_history_count policy.

    Before accepting a new password, password_policy_service checks that its bcrypt
    hash does NOT match any of the user's last N hashes stored here.
    Records are pruned to the N most recent entries per user.
    """
    __tablename__ = 'password_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow_naive)

    user = db.relationship('User', foreign_keys=[user_id], backref='password_history_entries')


class UserSession(db.Model):
    """Tracks active sessions for session management and remote logout.

    A record is created on every successful login. The Flask session cookie holds
    the raw session ID; only its SHA-256 hash is stored here so that a DB dump
    does not expose valid session tokens.

    Admin and user self-service can revoke a session (set is_active=False, revoked_at=now).
    The session middleware checks is_active and last_seen_at on every request.
    """
    __tablename__ = 'user_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_token_hash = db.Column(db.String(255), unique=True, nullable=False)
    # SHA-256 of the Flask session ID

    # Device / network metadata
    ip_address = db.Column(db.String(45))           # supports IPv6
    user_agent = db.Column(db.String(255))
    device_label = db.Column(db.String(100))        # e.g. "Chrome 122 on Windows 11"

    # Lifecycle
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    last_seen_at = db.Column(db.DateTime, default=utcnow_naive)
    expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    # Revocation
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    # NULL = self-revoked; set to admin user ID when forced out by admin

    user = db.relationship('User', foreign_keys=[user_id], backref='sessions')
    revoked_by = db.relationship('User', foreign_keys=[revoked_by_id])

    def to_dict(self, include_token_hash=False):
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'device_label': self.device_label,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_seen_at': self.last_seen_at.isoformat() if self.last_seen_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': self.is_active,
            'revoked_at': self.revoked_at.isoformat() if self.revoked_at else None,
            'revoked_by_id': self.revoked_by_id,
        }
        if include_token_hash:
            data['session_token_hash'] = self.session_token_hash
        return data
