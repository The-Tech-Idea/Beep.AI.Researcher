"""ConfigManager — unified, JSON-persisted singleton for ALL application configuration.

This module is the single source of truth for configuration.  The legacy
``app/config/manager.py`` (in-memory runtime manager) has been merged here;
``app/config/manager.py`` is now a thin compatibility shim.

Key design decisions
---------------------
- JSON file ``config/app_config.json`` holds all admin-configured values.
- ``_seed_defaults()`` (called on every ``load()``) writes the declared default
  for any key that is absent from the JSON file.  This fixes the long-standing
  ``smtp_host`` bug where the key was declared but never seeded.
- The in-memory ``features`` / ``hooks`` / ``queue`` / ``cache`` / ``general``
  sub-trees from the old runtime manager are merged into ``self._config`` on top
  of the ``get_default_config()`` base, so runtime callers that go through
  ``app.config.manager.get_config()`` transparently use the same object.
- Environment variables override any persisted value when present.
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG_KEYS  — flat keys persisted to app_config.json
# (type, default) — default is written to JSON on first boot if missing
# ─────────────────────────────────────────────────────────────────────────────
CONFIG_KEYS: Dict[str, Dict[str, Any]] = {
    # ── Core ──────────────────────────────────────────────────────────────────
    'secret_key':               {'type': str,  'label': 'Secret Key',              'default': ''},
    'SQLALCHEMY_DATABASE_URI':  {'type': str,  'label': 'Database URI',            'default': ''},
    'auth_mode':                {'type': str,  'label': 'Auth Mode',               'default': 'local'},
    'app_url':                  {'type': str,  'label': 'Application URL',         'default': 'http://127.0.0.1:5005'},
    'admin_password':           {'type': str,  'label': 'Admin Password (init)',   'default': ''},
    'server_host':              {'type': str,  'label': 'Server Host',             'default': '127.0.0.1'},
    'server_port':              {'type': int,  'label': 'Server Port',             'default': 5005},
    'dashboard_project_limit':  {'type': int,  'label': 'Dashboard Project Limit', 'default': 20},
    'search_result_limit':      {'type': int,  'label': 'Search Result Limit',     'default': 50},
    'project_list_limit':       {'type': int,  'label': 'Project List Limit',      'default': 50},
    'related_docs_limit':       {'type': int,  'label': 'Related Docs Limit',      'default': 10},
    'beep_ai_server_url':       {'type': str,  'label': 'Beep.AI.Server URL',      'default': ''},
    'beep_ai_server_token':     {'type': str,  'label': 'Beep.AI.Server Token',    'default': ''},

    # ── SMTP / Email ──────────────────────────────────────────────────────────
    # FIX: smtp_host was previously absent from defaults → email silently disabled
    'smtp_host':                {'type': str,  'label': 'SMTP Host',               'default': ''},
    'smtp_port':                {'type': int,  'label': 'SMTP Port',               'default': 587},
    'smtp_user':                {'type': str,  'label': 'SMTP Username',           'default': ''},
    'smtp_password':            {'type': str,  'label': 'SMTP Password',           'default': ''},
    'smtp_use_tls':             {'type': bool, 'label': 'SMTP Use TLS',            'default': True},
    'mail_from':                {'type': str,  'label': 'Mail From Address',       'default': ''},
    'mail_auth_method':         {'type': str,  'label': 'Mail Auth Method',        'default': 'smtp'},
    # 'smtp' | 'oauth2_ms365' | 'oauth2_google'
    'mail_oauth2_client_id':    {'type': str,  'label': 'Mail OAuth2 Client ID',   'default': ''},
    'mail_oauth2_client_secret':{'type': str,  'label': 'Mail OAuth2 Client Secret','default': ''},
    'mail_oauth2_tenant_id':    {'type': str,  'label': 'Mail OAuth2 Tenant ID (MS365)','default': ''},
    'mail_oauth2_refresh_token':{'type': str,  'label': 'Mail OAuth2 Refresh Token','default': ''},

    # ── Storage backend ───────────────────────────────────────────────────────
    'storage_backend':               {'type': str,  'label': 'Storage Backend',            'default': 'local'},
    # 'local' | 'smb' | 's3' | 'azure_blob'
    'storage_local_path':            {'type': str,  'label': 'Local Storage Path',         'default': 'data/uploads'},
    'storage_smb_host':              {'type': str,  'label': 'SMB Host',                   'default': ''},
    'storage_smb_share':             {'type': str,  'label': 'SMB Share',                  'default': ''},
    'storage_smb_username':          {'type': str,  'label': 'SMB Username',               'default': ''},
    'storage_smb_password':          {'type': str,  'label': 'SMB Password',               'default': ''},
    'storage_smb_domain':            {'type': str,  'label': 'SMB Domain',                 'default': ''},
    'storage_s3_endpoint_url':       {'type': str,  'label': 'S3 Endpoint URL',            'default': ''},
    # blank = AWS; set for MinIO or other S3-compatible on-prem
    'storage_s3_access_key':         {'type': str,  'label': 'S3 Access Key',              'default': ''},
    'storage_s3_secret_key':         {'type': str,  'label': 'S3 Secret Key',              'default': ''},
    'storage_s3_bucket_name':        {'type': str,  'label': 'S3 Bucket Name',             'default': ''},
    'storage_s3_region':             {'type': str,  'label': 'S3 Region',                  'default': 'us-east-1'},
    'storage_s3_prefix':             {'type': str,  'label': 'S3 Key Prefix',              'default': 'researcher/'},
    'storage_azure_connection_string':{'type': str, 'label': 'Azure Blob Connection String','default': ''},
    'storage_azure_container_name':  {'type': str,  'label': 'Azure Blob Container',       'default': 'researcher'},
    'storage_azure_prefix':          {'type': str,  'label': 'Azure Blob Prefix',          'default': 'uploads/'},

    # ── Quota defaults ────────────────────────────────────────────────────────
    'default_storage_quota_bytes':   {'type': int,  'label': 'Default Storage Quota (bytes)','default': 1_073_741_824},
    # 1 GB
    'default_document_quota':        {'type': int,  'label': 'Default Document Quota',     'default': 500},
    'default_max_upload_size_bytes': {'type': int,  'label': 'Default Max Upload Size (bytes)','default': 52_428_800},
    # 50 MB
    'quota_enforcement_enabled':     {'type': bool, 'label': 'Quota Enforcement Enabled',  'default': True},

    # ── Enterprise / Instance branding ────────────────────────────────────────
    'instance_name':             {'type': str,  'label': 'Instance Name',           'default': 'Beep.AI Researcher'},
    'instance_logo_url':         {'type': str,  'label': 'Instance Logo URL',       'default': ''},
    'instance_base_url':         {'type': str,  'label': 'Instance Base URL',       'default': 'http://localhost:5001'},

    # ── SSO / Identity ────────────────────────────────────────────────────────
    'sso_enabled':               {'type': bool, 'label': 'SSO Enabled',             'default': False},
    'sso_provider':              {'type': str,  'label': 'SSO Provider',            'default': 'none'},
    # 'none' | 'saml2' | 'oidc' | 'ldap'
    'saml_idp_metadata_url':     {'type': str,  'label': 'SAML IdP Metadata URL',   'default': ''},
    'saml_sp_entity_id':         {'type': str,  'label': 'SAML SP Entity ID',       'default': ''},
    'saml_sp_acs_url':           {'type': str,  'label': 'SAML SP ACS URL',         'default': ''},
    'oidc_discovery_url':        {'type': str,  'label': 'OIDC Discovery URL',      'default': ''},
    'oidc_client_id':            {'type': str,  'label': 'OIDC Client ID',          'default': ''},
    'oidc_client_secret':        {'type': str,  'label': 'OIDC Client Secret',      'default': ''},
    'ldap_server':               {'type': str,  'label': 'LDAP Server',             'default': ''},
    'ldap_port':                 {'type': int,  'label': 'LDAP Port',               'default': 389},
    'ldap_bind_dn':              {'type': str,  'label': 'LDAP Bind DN',            'default': ''},
    'ldap_bind_password':        {'type': str,  'label': 'LDAP Bind Password',      'default': ''},
    'ldap_user_search_base':     {'type': str,  'label': 'LDAP User Search Base',   'default': ''},
    'ldap_user_search_filter':   {'type': str,  'label': 'LDAP User Search Filter', 'default': '(sAMAccountName={username})'},
    'ldap_tls_enabled':          {'type': bool, 'label': 'LDAP TLS (LDAPS)',        'default': False},

    # ── External APIs — Admin-Global shared keys ───────────────────────────────
    # Per-user and dual-mode credentials live in GlobalIntegrationService /
    # UserIntegrationCredential DB models (see integrations_registry.py).
    'pubmed_api_key':            {'type': str,  'label': 'PubMed API Key (institutional)', 'default': ''},
    'arxiv_api_email':           {'type': str,  'label': 'arXiv API Contact Email',        'default': ''},
    'crossref_mailto':           {'type': str,  'label': 'Crossref Polite Pool Email',     'default': ''},
    'google_scholar_proxy_url':  {'type': str,  'label': 'Google Scholar Proxy URL',       'default': ''},
    'openai_api_key':            {'type': str,  'label': 'OpenAI API Key (admin fallback)', 'default': ''},
    'openai_model':              {'type': str,  'label': 'OpenAI Model',                   'default': 'gpt-4o-mini'},

    # ── User Registration ─────────────────────────────────────────────────────
    'registration_mode':                       {'type': str,  'label': 'Registration Mode',                    'default': 'open'},
    # 'open' | 'invite_only' | 'domain_allowlist' | 'admin_only'
    'registration_allowed_domains':            {'type': str,  'label': 'Allowed Email Domains (comma-sep)',    'default': ''},
    'registration_require_email_verification': {'type': bool, 'label': 'Require Email Verification',          'default': True},
    'registration_auto_assign_tier':           {'type': str,  'label': 'Auto-Assign Plan Tier on Registration','default': ''},
    'registration_auto_assign_role':           {'type': str,  'label': 'Auto-Assign Role on Registration',    'default': 'user'},
    'registration_auto_tenant':                {'type': str,  'label': 'Auto-Assign Tenant on Registration',  'default': ''},
    'registration_captcha_enabled':            {'type': bool, 'label': 'Registration CAPTCHA',                'default': False},

    # ── Password policy ───────────────────────────────────────────────────────
    'password_min_length':          {'type': int,  'label': 'Min Password Length',              'default': 8},
    'password_require_uppercase':   {'type': bool, 'label': 'Require Uppercase Letter',         'default': True},
    'password_require_lowercase':   {'type': bool, 'label': 'Require Lowercase Letter',         'default': True},
    'password_require_number':      {'type': bool, 'label': 'Require Number',                   'default': True},
    'password_require_special':     {'type': bool, 'label': 'Require Special Character',        'default': False},
    'password_expiry_days':         {'type': int,  'label': 'Password Expiry (days; 0=never)',  'default': 0},
    'password_history_count':       {'type': int,  'label': 'Password History Count',           'default': 5},
    'password_max_failed_attempts': {'type': int,  'label': 'Max Failed Login Attempts',        'default': 5},
    'password_lockout_minutes':     {'type': int,  'label': 'Lockout Duration (minutes)',       'default': 15},

    # ── MFA ───────────────────────────────────────────────────────────────────
    'mfa_enabled':              {'type': bool, 'label': 'MFA Feature Enabled',                  'default': False},
    'mfa_enforcement':          {'type': str,  'label': 'MFA Enforcement',                      'default': 'optional'},
    # 'optional' | 'required_all' | 'required_by_role'
    'mfa_required_roles':       {'type': str,  'label': 'MFA Required Roles (comma-sep)',        'default': 'admin'},
    'mfa_totp_enabled':         {'type': bool, 'label': 'TOTP Authenticator App',               'default': True},
    'mfa_email_otp_enabled':    {'type': bool, 'label': 'Email OTP',                            'default': True},
    'mfa_sms_otp_enabled':      {'type': bool, 'label': 'SMS OTP',                              'default': False},
    'mfa_backup_codes_count':   {'type': int,  'label': 'Backup Code Count',                    'default': 10},
    'mfa_otp_validity_minutes': {'type': int,  'label': 'Email OTP Validity (minutes)',          'default': 10},
    'mfa_totp_issuer':          {'type': str,  'label': 'TOTP Issuer Name',                     'default': 'Beep.AI.Researcher'},
    'mfa_sms_provider':         {'type': str,  'label': 'SMS Provider',                         'default': 'twilio'},
    'mfa_sms_account_sid':      {'type': str,  'label': 'Twilio Account SID',                   'default': ''},
    'mfa_sms_auth_token':       {'type': str,  'label': 'Twilio Auth Token',                    'default': ''},
    'mfa_sms_from_number':      {'type': str,  'label': 'Twilio From Number',                   'default': ''},

    # ── Session management ────────────────────────────────────────────────────
    'session_lifetime_hours':           {'type': int,  'label': 'Session Lifetime (hours)',         'default': 24},
    'session_idle_timeout_minutes':     {'type': int,  'label': 'Session Idle Timeout (minutes; 0=off)', 'default': 0},
    'session_max_concurrent':           {'type': int,  'label': 'Max Concurrent Sessions (0=unlimited)', 'default': 0},
    'session_impersonation_limit_hours':{'type': int,  'label': 'Impersonation Session Limit (hours)', 'default': 1},
}

# ─────────────────────────────────────────────────────────────────────────────
# Runtime-key map — kept for backward compat
# ─────────────────────────────────────────────────────────────────────────────
GENERAL_RUNTIME_KEY_MAP = {k: k for k in CONFIG_KEYS}   # 1:1 after merge


def get_app_directory() -> Path:
    """Return the project root directory."""
    import sys
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


class ConfigManager:
    """Unified, JSON-backed configuration singleton.

    All admin-configurable values live here.  The old ``app/config/manager.py``
    runtime feature-flag/queue/cache manager is merged in; callers that still
    import from ``app.config`` get a compatibility shim that delegates here.
    """

    _instance = None
    _lock = Lock()
    _original: 'ConfigManager | None' = None  # Tracks the first-ever created instance

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'ConfigManager':
        """Return the singleton instance, re-initializing from the original if needed.

        When tests set ``ConfigManager._instance = None`` to force a fresh config,
        this method restores ``_instance`` to the original object and re-runs
        ``__init__`` so callers of both ``get_config()`` and the module-level
        ``config_manager`` always reference the same underlying object.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    if cls._original is not None:
                        # Restore original instance and force re-initialization
                        cls._instance = cls._original
                        cls._instance._initialized = False
                    else:
                        cls._instance = super().__new__(cls)
                        cls._instance._initialized = False
        if not cls._instance._initialized:
            cls._instance.__init__()
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._base_path = get_app_directory()
        self._config_path = self._base_path / 'config' / 'app_config.json'
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config: Dict[str, Any] = {}
        self._tenant_configs: Dict[str, Dict] = {}
        self._last_reload = datetime.now()
        self._validation_errors: List[str] = []
        self.load()

    # ── Paths ─────────────────────────────────────────────────────────────────

    @property
    def base_path(self) -> Path:
        return self._base_path

    @property
    def data_path(self) -> Path:
        p = self._base_path / 'data'
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def logs_path(self) -> Path:
        p = self._base_path / 'logs'
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def uploads_path(self) -> Path:
        """Resolves the active storage local path from config."""
        rel = self.get('storage_local_path', 'data/uploads')
        p = self._base_path / rel
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_path(self) -> Path:
        return self.data_path / 'researcher.db'

    # ── Persistence ───────────────────────────────────────────────────────────

    def load(self):
        """Load JSON config, then seed any missing default keys."""
        # 1. Start with in-memory defaults from the runtime config system.
        #
        # IMPORTANT: We must NOT import via `app.config` package here because
        # `app/config/__init__.py` re-imports `config_manager` from this module.
        # When this method is called during the module-level singleton creation
        # (`config_manager = ConfigManager()` at the bottom of this file), the
        # `app.config_manager` module is still being loaded and `config_manager`
        # is not yet bound — causing a circular ImportError that is silently
        # swallowed, leaving `_config` as an empty dict with no feature flags.
        #
        # Fix: check sys.modules first (fast path after first load), then fall
        # back to a direct file-level import that bypasses __init__.py entirely.
        import sys as _sys
        _defaults_mod = _sys.modules.get('app.config.defaults')
        try:
            if _defaults_mod is None:
                import importlib.util as _ilu
                _spec = _ilu.spec_from_file_location(
                    'app.config.defaults',
                    Path(__file__).parent / 'config' / 'defaults.py',
                )
                _defaults_mod = _ilu.module_from_spec(_spec)
                _spec.loader.exec_module(_defaults_mod)
                _sys.modules['app.config.defaults'] = _defaults_mod
            base = _defaults_mod.get_default_config()
        except Exception:
            base = {}
        self._config = base

        # 2. Merge persisted JSON on top (smart-merge: preserve dict structure for features/hooks)
        # In TESTING mode: load flat keys (e.g. secret_key) but skip features/hooks overrides
        # so tests always start from clean documented defaults for feature flags.
        if self._config_path.exists():
            try:
                with open(self._config_path, 'r') as f:
                    persisted = json.load(f)
                in_testing = bool(os.getenv('TESTING'))
                for key, value in persisted.items():
                    if key in ('features', 'hooks') and in_testing:
                        # In TESTING mode, always use fresh defaults for feature/hook flags
                        continue
                    elif key in ('features', 'hooks') and isinstance(value, dict):
                        # Smart-merge: preserve dict structure from defaults
                        base_section = self._config.get(key, {})
                        for name, val in value.items():
                            if name in base_section and isinstance(base_section[name], dict):
                                if isinstance(val, bool):
                                    base_section[name]['enabled'] = val
                                elif isinstance(val, dict):
                                    base_section[name] = {**base_section[name], **val}
                            else:
                                base_section[name] = val
                        self._config[key] = base_section
                    else:
                        self._config[key] = value
            except Exception as exc:
                logger.warning('app_config.json load failed (%s); using defaults', exc)

        # 3. Seed defaults for any CONFIG_KEYS entry missing from the file
        self._seed_defaults()
        self._last_reload = datetime.now()

    def _seed_defaults(self):
        """Write declared CONFIG_KEYS defaults for any key absent from the JSON.

        This is the fix for the smtp_host bug: because smtp_host had no default
        value previously seeded, email was silently disabled on fresh installs.
        After seeding, every key will appear in app_config.json with its default
        value so admin UI can render it and email_service.is_configured() can
        tell the difference between 'not set' and 'missing'.
        """
        changed = False
        for key, meta in CONFIG_KEYS.items():
            if 'default' not in meta:
                continue
            # Only seed simple top-level keys (not dot-separated paths)
            if '.' in key:
                continue
            if key not in self._config:
                self._config[key] = meta['default']
                changed = True
        if changed and not os.getenv('TESTING'):  # Don't write to disk during tests
            self.save()

    def save(self):
        """Persist the current flat config keys to app_config.json."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path, 'w') as f:
            json.dump(self._config, f, indent=2)

    # ── Generic get / set ─────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value.  Dot-notation supported for nested sub-trees."""
        keys = key.split('.')
        v = self._config
        for k in keys:
            if not isinstance(v, dict):
                return default
            v = v.get(k, {})
        if v != {} and v is not None:
            return v
        # Declared default as last resort
        return CONFIG_KEYS.get(key, {}).get('default', default)

    def set(self, key: str, value: Any) -> None:
        """Set a config value (dot-notation for nested keys)."""
        keys = key.split('.')
        d = self._config
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value

    def get_setting(self, key: str, default: Any = None,
                    env_var: Optional[str] = None) -> Any:
        """Read config → env var → declared default."""
        v = self.get(key)
        if v is not None and v != '':
            return v
        if env_var and os.environ.get(env_var):
            return os.environ[env_var]
        return CONFIG_KEYS.get(key, {}).get('default', default)

    def get_with_env(self, key: str, env_var: Optional[str] = None,
                     default: Any = None) -> Any:
        return self.get_setting(key, default=default, env_var=env_var)

    def get_schema(self) -> Dict[str, Any]:
        """Return the CONFIG_KEYS schema dict (for admin settings pages)."""
        return CONFIG_KEYS.copy()

    # ── Feature flags (merged from runtime ConfigManager) ─────────────────────

    @staticmethod
    def _feature_value(entry: Any) -> bool:
        """Normalise a feature entry: accepts both ``True`` and ``{'enabled': True}``."""
        if isinstance(entry, dict):
            return bool(entry.get('enabled', False))
        return bool(entry)

    def is_feature_enabled(self, feature_name: str,
                            tenant_id: Optional[str] = None) -> bool:
        if tenant_id and tenant_id in self._tenant_configs:
            tc = self._tenant_configs[tenant_id]
            features = tc.get('features', {})
            if feature_name in features:
                return self._feature_value(features[feature_name])
        features = self._config.get('features', {})
        if feature_name in features:
            return self._feature_value(features[feature_name])
        return False

    def set_feature_enabled(self, feature_name: str, enabled: bool) -> bool:
        features = self._config.setdefault('features', {})
        if feature_name not in features:
            return False
        entry = features.get(feature_name, {})
        if isinstance(entry, dict):
            entry['enabled'] = enabled
            features[feature_name] = entry
        else:
            features[feature_name] = enabled
        return True

    def get_feature_config(self, feature_name: str,
                            tenant_id: Optional[str] = None) -> Optional[Any]:
        if tenant_id and tenant_id in self._tenant_configs:
            tc = self._tenant_configs[tenant_id]
            if feature_name in tc.get('features', {}):
                val = tc['features'][feature_name]
                return val if isinstance(val, dict) else {'enabled': bool(val)}
        val = self._config.get('features', {}).get(feature_name)
        if val is None:
            return None
        return val if isinstance(val, dict) else {'enabled': bool(val)}

    def get_all_features(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        features = dict(self._config.get('features', {}))
        if tenant_id and tenant_id in self._tenant_configs:
            features.update(self._tenant_configs[tenant_id].get('features', {}))
        return {
            name: (val if isinstance(val, dict) else {'enabled': bool(val)})
            for name, val in features.items()
        }

    # ── Queue config ──────────────────────────────────────────────────────────

    def get_queue_config(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        cfg = dict(self._config.get('queue', {}))
        if tenant_id and tenant_id in self._tenant_configs:
            cfg.update(self._tenant_configs[tenant_id].get('queue', {}))
        return cfg

    def set_queue_values(self, values: Dict[str, Any]) -> bool:
        if not isinstance(values, dict):
            return False
        queue = self._config.setdefault('queue', {})
        queue.update({k: v for k, v in values.items() if v is not None})
        return True

    def get_max_workers(self, tenant_id: Optional[str] = None) -> int:
        return self.get_queue_config(tenant_id).get('max_workers', 4)

    def get_max_retries(self, tenant_id: Optional[str] = None) -> int:
        return self.get_queue_config(tenant_id).get('max_retries', 3)

    def get_job_timeout_seconds(self, tenant_id: Optional[str] = None) -> int:
        return self.get_queue_config(tenant_id).get('job_timeout_seconds', 3600)

    def get_retry_delay_seconds(self, retry_count: int,
                                 tenant_id: Optional[str] = None) -> int:
        cfg = self.get_queue_config(tenant_id)
        base = cfg.get('exponential_backoff_base', 2)
        initial = cfg.get('initial_retry_delay_seconds', 5)
        max_delay = cfg.get('max_retry_delay_seconds', 300)
        return min(initial * (base ** retry_count), max_delay)

    # ── Cache config ──────────────────────────────────────────────────────────

    def get_cache_config(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        cfg = dict(self._config.get('cache', {}))
        if tenant_id and tenant_id in self._tenant_configs:
            cfg.update(self._tenant_configs[tenant_id].get('cache', {}))
        return cfg

    def set_cache_values(self, values: Dict[str, Any]) -> bool:
        if not isinstance(values, dict):
            return False
        cache = self._config.setdefault('cache', {})
        cache.update({k: v for k, v in values.items() if v is not None})
        return True

    def get_cache_ttl_seconds(self, tenant_id: Optional[str] = None) -> int:
        return self.get_cache_config(tenant_id).get('cache_ttl_seconds', 86400)

    # ── General / runtime config ──────────────────────────────────────────────

    def get_general_config(self) -> Dict[str, Any]:
        return dict(self._config.get('general', {}))

    def get_general_value(self, key: str, default: Any = None) -> Any:
        return self._config.get('general', {}).get(key, default)

    def set_general_values(self, values: Dict[str, Any]) -> bool:
        if not isinstance(values, dict):
            return False
        general = self._config.setdefault('general', {})
        general.update({k: v for k, v in values.items() if v is not None})
        return True

    def get_environment(self) -> str:
        return self._config.get('general', {}).get('environment', 'development')

    def is_debug_mode(self) -> bool:
        return bool(self._config.get('general', {}).get('debug_mode', False))

    def get_log_level(self) -> str:
        return self._config.get('general', {}).get('log_level', 'INFO')

    # ── Hook config ───────────────────────────────────────────────────────────

    def get_hook_config(self, hook_name: str,
                        tenant_id: Optional[str] = None) -> Optional[Dict]:
        if tenant_id and tenant_id in self._tenant_configs:
            tc_hooks = self._tenant_configs[tenant_id].get('hooks', {})
            if hook_name in tc_hooks:
                return tc_hooks[hook_name]
        return self._config.get('hooks', {}).get(hook_name)

    def is_hook_enabled(self, hook_name: str,
                        tenant_id: Optional[str] = None) -> bool:
        cfg = self.get_hook_config(hook_name, tenant_id)
        if cfg is None:
            return False
        if isinstance(cfg, dict):
            return bool(cfg.get('enabled', False))
        return bool(cfg)

    def get_enabled_hooks(self, tenant_id: Optional[str] = None) -> List[tuple]:
        hooks = dict(self._config.get('hooks', {}))
        if tenant_id and tenant_id in self._tenant_configs:
            hooks.update(self._tenant_configs[tenant_id].get('hooks', {}))
        enabled = []
        for n, c in hooks.items():
            if isinstance(c, dict) and c.get('enabled', False):
                enabled.append((n, c))
            elif isinstance(c, bool) and c:
                enabled.append((n, {'enabled': True}))
        return sorted(enabled, key=lambda x: x[1].get('priority', 0), reverse=True)

    def get_hooks_for_event(self, event_name: str,
                             tenant_id: Optional[str] = None) -> List[str]:
        return [
            name for name, cfg in self.get_enabled_hooks(tenant_id)
            if isinstance(cfg, dict) and event_name in cfg.get('trigger_events', [])
        ]

    def set_hook_enabled(self, hook_name: str, enabled: bool) -> bool:
        hooks = self._config.setdefault('hooks', {})
        if hook_name not in hooks:
            return False
        entry = hooks[hook_name]
        if isinstance(entry, dict):
            entry['enabled'] = enabled
        else:
            hooks[hook_name] = enabled
        return True

    # ── Tenant config overrides ───────────────────────────────────────────────

    def set_tenant_config(self, tenant_id: str,
                           config_overrides: Dict[str, Any]) -> bool:
        self._tenant_configs[tenant_id] = config_overrides
        return True

    def get_tenant_config(self, tenant_id: str) -> Optional[Dict]:
        return self._tenant_configs.get(tenant_id)

    def remove_tenant_config(self, tenant_id: str) -> bool:
        if tenant_id in self._tenant_configs:
            del self._tenant_configs[tenant_id]
            return True
        return False

    # ── Validation / health / reload ──────────────────────────────────────────

    def validate_config(self) -> bool:
        self._validation_errors = []
        return True   # Schema-level validation is lightweight; extend as needed

    def get_validation_errors(self) -> List[str]:
        return list(self._validation_errors)

    def reload_config(self) -> bool:
        try:
            old_tenants = dict(self._tenant_configs)
            self.load()
            self._tenant_configs = old_tenants
            return True
        except Exception as exc:
            logger.error('Config reload failed: %s', exc)
            return False

    def get_last_reload_time(self) -> datetime:
        return self._last_reload

    def export_config(self, include_sensitive: bool = False) -> Dict[str, Any]:
        cfg = dict(self._config)
        if not include_sensitive:
            sensitive = {
                'secret_key', 'admin_password', 'smtp_password',
                'mail_oauth2_client_secret', 'mail_oauth2_refresh_token',
                'storage_smb_password', 'storage_s3_secret_key',
                'storage_azure_connection_string', 'oidc_client_secret',
                'ldap_bind_password', 'openai_api_key',
                'mfa_sms_auth_token', 'beep_ai_server_token',
            }
            for k in sensitive:
                if k in cfg:
                    cfg[k] = '***'
        return cfg

    def get_config_summary(self) -> Dict[str, Any]:
        return {
            'environment': self.get_environment(),
            'debug_mode': self.is_debug_mode(),
            'storage_backend': self.get('storage_backend', 'local'),
            'mail_auth_method': self.get('mail_auth_method', 'smtp'),
            'smtp_configured': bool(self.get('smtp_host')),
            'sso_enabled': self.get('sso_enabled', False),
            'quota_enforcement': self.get('quota_enforcement_enabled', True),
            'registration_mode': self.get('registration_mode', 'open'),
            'mfa_enabled': self.get('mfa_enabled', False),
            'max_workers': self.get_max_workers(),
            'enabled_hooks_count': len(self.get_enabled_hooks()),
            'last_reload': self._last_reload.isoformat(),
            'auto_extract_enabled': self.is_feature_enabled('auto_extract'),
            'tenant_configs_count': len(self._tenant_configs),
        }

    # ── Backward-compat ───────────────────────────────────────────────────────

    @property
    def is_configured(self) -> bool:
        """True if the setup wizard has been completed (admin user exists)."""
        try:
            from app.database import db
            from app.models.core import User, Role
            admin_role = Role.query.filter_by(name='Admin').first()
            if admin_role:
                return User.query.filter_by(role_id=admin_role.id).count() > 0
            return User.query.count() > 0
        except Exception:
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Module-level singleton and convenience helpers
# ─────────────────────────────────────────────────────────────────────────────

config_manager: ConfigManager = ConfigManager()
ConfigManager._original = config_manager  # preserve reference for reset-recovery in tests


def get_config() -> ConfigManager:
    """Return the singleton ConfigManager instance."""
    return ConfigManager.get_instance()


def is_feature_enabled(feature_name: str,
                        tenant_id: Optional[str] = None) -> bool:
    return config_manager.is_feature_enabled(feature_name, tenant_id)


def get_max_workers(tenant_id: Optional[str] = None) -> int:
    return config_manager.get_max_workers(tenant_id)


def get_queue_ttl(tenant_id: Optional[str] = None) -> int:
    return config_manager.get_cache_ttl_seconds(tenant_id)
