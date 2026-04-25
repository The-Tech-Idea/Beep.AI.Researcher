"""Integration registry models — GlobalIntegrationService, UserIntegrationCredential.

These models implement the three-tier integration ownership model (Phase 9):

  Tier              | Credential home
  ------------------|------------------------------------------------
  Admin-Global      | config_manager (config keys, not this model)
  User-Personal     | UserIntegrationCredential (this model)
  Dual-Mode         | GlobalIntegrationService (shared) +
                    | UserIntegrationCredential (per-user override)

Credential resolution order (implemented in integration_service.py):
  1. User's personal UserIntegrationCredential (if present and active)
  2. GlobalIntegrationService.global_api_key_encrypted  (dual-mode fallback)
  3. config_manager admin-global keys (for services that have one)

All token/secret columns are stored AES-256-GCM encrypted using the
app SECRET_KEY. Admin routes NEVER expose raw token values.

Alembic migration: migrations/add_quota_user_management_integrations.py
"""
from app.database import db
from app.core.time_utils import utcnow_naive

# ── Service type constants ────────────────────────────────────────────────────
SERVICE_TYPE_GOOGLE_DRIVE = 'google_drive'
SERVICE_TYPE_DROPBOX = 'dropbox'
SERVICE_TYPE_ONEDRIVE = 'onedrive'
SERVICE_TYPE_ZOTERO = 'zotero'
SERVICE_TYPE_MENDELEY = 'mendeley'
SERVICE_TYPE_GITHUB = 'github'
SERVICE_TYPE_GITLAB = 'gitlab'
SERVICE_TYPE_PUBMED = 'pubmed'
SERVICE_TYPE_ARXIV = 'arxiv'
SERVICE_TYPE_CROSSREF = 'crossref'
SERVICE_TYPE_OPENAI = 'openai'
SERVICE_TYPE_YOUTUBE = 'youtube'
SERVICE_TYPE_GOOGLE_BOOKS = 'google_books'
SERVICE_TYPE_CUSTOM = 'custom'

# ── Scope constants ───────────────────────────────────────────────────────────
SCOPE_ADMIN_ONLY = 'admin_only'         # admin uses; NOT shown to users
SCOPE_USER_PERSONAL = 'user_personal'   # only users connect personal accounts; no shared key
SCOPE_DUAL = 'dual'                     # admin sets global fallback; users may also connect personal

# Default OAuth2 URL templates for well-known services
SERVICE_DEFAULTS = {
    SERVICE_TYPE_GOOGLE_DRIVE: {
        'oauth2_auth_url': 'https://accounts.google.com/o/oauth2/v2/auth',
        'oauth2_token_url': 'https://oauth2.googleapis.com/token',
        'oauth2_scopes': 'https://www.googleapis.com/auth/drive.file',
    },
    SERVICE_TYPE_DROPBOX: {
        'oauth2_auth_url': 'https://www.dropbox.com/oauth2/authorize',
        'oauth2_token_url': 'https://api.dropboxapi.com/oauth2/token',
        'oauth2_scopes': 'files.content.read files.content.write',
    },
    SERVICE_TYPE_ONEDRIVE: {
        'oauth2_auth_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
        'oauth2_token_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/token',
        'oauth2_scopes': 'Files.ReadWrite offline_access',
    },
    SERVICE_TYPE_GITHUB: {
        'oauth2_auth_url': 'https://github.com/login/oauth/authorize',
        'oauth2_token_url': 'https://github.com/login/oauth/access_token',
        'oauth2_scopes': 'repo read:user',
    },
    SERVICE_TYPE_GITLAB: {
        'oauth2_auth_url': 'https://gitlab.com/oauth/authorize',
        'oauth2_token_url': 'https://gitlab.com/oauth/token',
        'oauth2_scopes': 'read_api write_repository',
    },
    SERVICE_TYPE_MENDELEY: {
        'oauth2_auth_url': 'https://api.mendeley.com/oauth/authorize',
        'oauth2_token_url': 'https://api.mendeley.com/oauth/token',
        'oauth2_scopes': 'all',
    },
}


class GlobalIntegrationService(db.Model):
    """Admin-registered integration service.

    Acts as the runtime registry of which external services are available in this
    deployment. Each entry represents one service that users may or may not be
    able to connect their personal accounts to.

    Admins manage these via Admin → Integrations.
    On startup, seed_default_services() (in integration_service.py) creates
    entries for well-known services in a disabled state if they don't already exist.
    """
    __tablename__ = 'global_integration_services'

    id = db.Column(db.Integer, primary_key=True)
    service_type = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(100), nullable=False)        # "Google Drive", "Personal Zotero", …
    description = db.Column(db.Text)
    scope = db.Column(db.String(20), default=SCOPE_USER_PERSONAL)
    is_enabled = db.Column(db.Boolean, default=False)       # disabled until admin explicitly enables
    allow_user_override = db.Column(db.Boolean, default=True)
    # For dual-mode: if False, users see "Available via institution" but cannot connect personal account

    # ── OAuth2 app registration (for services using OAuth2) ───────────────────
    oauth2_client_id = db.Column(db.String(255))
    oauth2_client_secret_encrypted = db.Column(db.Text)     # AES-256-GCM encrypted
    oauth2_scopes = db.Column(db.String(500))               # space/comma separated
    oauth2_auth_url = db.Column(db.String(500))
    oauth2_token_url = db.Column(db.String(500))
    oauth2_redirect_uri = db.Column(db.String(500))

    # ── Global / shared credential (admin-global or dual-mode fallback) ───────
    global_api_key_encrypted = db.Column(db.Text)           # AES-256-GCM encrypted
    global_extra_config = db.Column(db.Text)                # JSON for service-specific extras

    # ── Health / test ────────────────────────────────────────────────────────
    last_tested_at = db.Column(db.DateTime)
    last_test_ok = db.Column(db.Boolean)
    last_test_error = db.Column(db.String(500))
    last_test_latency_ms = db.Column(db.Integer)

    # ── Metadata ─────────────────────────────────────────────────────────────
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    updated_at = db.Column(db.DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    # Cached count; updated on connect/disconnect (to avoid expensive COUNT queries)
    connected_user_count = db.Column(db.Integer, default=0)

    created_by = db.relationship('User', foreign_keys=[created_by_id],
                                 backref='created_integration_services')
    user_credentials = db.relationship('UserIntegrationCredential',
                                       back_populates='service',
                                       lazy='dynamic',
                                       cascade='all, delete-orphan')

    def to_dict(self, include_secrets=False):
        """Serialize for API responses. Secrets are masked by default."""
        data = {
            'id': self.id,
            'service_type': self.service_type,
            'name': self.name,
            'description': self.description,
            'scope': self.scope,
            'is_enabled': self.is_enabled,
            'allow_user_override': self.allow_user_override,
            'oauth2_client_id': self.oauth2_client_id,
            'has_oauth2_secret': bool(self.oauth2_client_secret_encrypted),
            'oauth2_scopes': self.oauth2_scopes,
            'oauth2_auth_url': self.oauth2_auth_url,
            'oauth2_token_url': self.oauth2_token_url,
            'oauth2_redirect_uri': self.oauth2_redirect_uri,
            'has_global_api_key': bool(self.global_api_key_encrypted),
            'last_tested_at': self.last_tested_at.isoformat() if self.last_tested_at else None,
            'last_test_ok': self.last_test_ok,
            'last_test_error': self.last_test_error,
            'last_test_latency_ms': self.last_test_latency_ms,
            'connected_user_count': self.connected_user_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        # Secrets included only for internal service calls, never user-facing API
        if include_secrets:
            data['oauth2_client_secret_encrypted'] = self.oauth2_client_secret_encrypted
            data['global_api_key_encrypted'] = self.global_api_key_encrypted
            data['global_extra_config'] = self.global_extra_config
        return data


class UserIntegrationCredential(db.Model):
    """Per-user credential for a GlobalIntegrationService.

    Stores the user's personal OAuth2 tokens or API key.
    Admin routes can see: display_name, connected_at, is_active, last_used_at.
    Admin routes NEVER expose raw token/key values.

    Supersedes the legacy IntegrationCredential model for user-personal and dual-
    mode services. The legacy model is retained for backward compatibility during
    the migration window.
    """
    __tablename__ = 'user_integration_credentials'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'service_id', name='uq_user_service_credential'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('global_integration_services.id'),
                           nullable=False)

    # ── OAuth2 tokens (all AES-256-GCM encrypted at rest) ────────────────────
    access_token_encrypted = db.Column(db.Text)
    refresh_token_encrypted = db.Column(db.Text)
    token_expires_at = db.Column(db.DateTime)
    token_scopes = db.Column(db.String(500))

    # ── API key alternative (for key-based services, e.g. personal Zotero) ──
    api_key_encrypted = db.Column(db.Text)                  # AES-256-GCM encrypted

    # ── Connection metadata (admin-visible, no token data) ───────────────────
    is_active = db.Column(db.Boolean, default=True)
    display_name = db.Column(db.String(200))
    # e.g. "john@gmail.com (Google Drive)"

    connected_at = db.Column(db.DateTime, default=utcnow_naive)
    last_used_at = db.Column(db.DateTime)
    last_sync_at = db.Column(db.DateTime)
    disconnected_at = db.Column(db.DateTime, nullable=True)

    # ── Service-specific extra data (e.g. Zotero user ID, Dropbox account ID) ─
    extra_data = db.Column(db.Text)                         # JSON

    user = db.relationship('User', foreign_keys=[user_id],
                           backref='integration_credentials_v2')
    service = db.relationship('GlobalIntegrationService', back_populates='user_credentials')

    def to_dict(self, include_tokens=False):
        """Serialize for API responses. Token fields are excluded by default."""
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'service_id': self.service_id,
            'display_name': self.display_name,
            'is_active': self.is_active,
            'connected_at': self.connected_at.isoformat() if self.connected_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'last_sync_at': self.last_sync_at.isoformat() if self.last_sync_at else None,
            'disconnected_at': self.disconnected_at.isoformat() if self.disconnected_at else None,
            'token_expires_at': self.token_expires_at.isoformat()
            if self.token_expires_at else None,
            'has_access_token': bool(self.access_token_encrypted),
            'has_refresh_token': bool(self.refresh_token_encrypted),
            'has_api_key': bool(self.api_key_encrypted),
        }
        # Encrypted blobs are included only for internal service calls (decryption in service layer)
        if include_tokens:
            data['access_token_encrypted'] = self.access_token_encrypted
            data['refresh_token_encrypted'] = self.refresh_token_encrypted
            data['api_key_encrypted'] = self.api_key_encrypted
            data['extra_data'] = self.extra_data
        return data
