"""Integration service — Phase 9b of Admin Enhancement Plan.

Responsibilities
----------------
1. AES-256-GCM encrypt / decrypt for all stored credentials (uses app SECRET_KEY).
2. seed_default_services() — idempotent boot-time seed of well-known services.
3. Credential resolution (user override → global fallback → config key).
4. Admin CRUD helpers: save service settings, save global API key / OAuth2 app.
5. User CRUD helpers: connect with API key, OAuth2 token save, disconnect.
6. Connection test stub (basic HTTP or service-specific ping).

Security notes
--------------
* Raw credentials are NEVER returned from public-facing methods.
  Encrypted blobs are returned only for internal use (e.g. when building an
  OAuth2 Authorization header).
* AES-256-GCM nonce (12 bytes) is stored prepended to the ciphertext:
  stored = nonce(12) + ciphertext + tag(16)  — all base64url encoded.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from typing import TYPE_CHECKING, Optional

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.models.integrations_registry import (
        GlobalIntegrationService,
        UserIntegrationCredential,
    )

# ---------------------------------------------------------------------------
# AES-256-GCM helpers
# ---------------------------------------------------------------------------

def _derive_key() -> bytes:
    """Derive a 32-byte AES key from the Flask app SECRET_KEY."""
    from flask import current_app
    import hashlib
    secret = current_app.config.get('SECRET_KEY') or 'fallback-dev-key-change-me'
    return hashlib.sha256(secret.encode()).digest()


def encrypt_secret(plaintext: str) -> str:
    """Encrypt *plaintext* with AES-256-GCM. Returns base64url-encoded blob."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        key = _derive_key()
        nonce = os.urandom(12)
        ct = AESGCM(key).encrypt(nonce, plaintext.encode(), None)
        return base64.urlsafe_b64encode(nonce + ct).decode()
    except Exception as exc:
        log.error(f'encrypt_secret failed: {exc}')
        raise


def decrypt_secret(blob: str) -> str:
    """Decrypt a blob produced by encrypt_secret."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        key = _derive_key()
        raw = base64.urlsafe_b64decode(blob.encode())
        nonce, ct = raw[:12], raw[12:]
        return AESGCM(key).decrypt(nonce, ct, None).decode()
    except Exception as exc:
        log.error(f'decrypt_secret failed: {exc}')
        raise


# ---------------------------------------------------------------------------
# Boot-time seed
# ---------------------------------------------------------------------------

_SEED_SERVICES = [
    {
        'service_type': 'google_drive',
        'name': 'Google Drive',
        'description': 'Connect your personal Google Drive to import / export documents.',
        'scope': 'user_personal',
        'oauth2_auth_url': 'https://accounts.google.com/o/oauth2/v2/auth',
        'oauth2_token_url': 'https://oauth2.googleapis.com/token',
        'oauth2_scopes': 'https://www.googleapis.com/auth/drive.file',
    },
    {
        'service_type': 'dropbox',
        'name': 'Dropbox',
        'description': 'Connect your personal Dropbox account.',
        'scope': 'user_personal',
        'oauth2_auth_url': 'https://www.dropbox.com/oauth2/authorize',
        'oauth2_token_url': 'https://api.dropboxapi.com/oauth2/token',
        'oauth2_scopes': 'files.content.read files.content.write',
    },
    {
        'service_type': 'onedrive',
        'name': 'Microsoft OneDrive',
        'description': 'Connect your personal OneDrive / SharePoint.',
        'scope': 'user_personal',
        'oauth2_auth_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
        'oauth2_token_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/token',
        'oauth2_scopes': 'Files.ReadWrite offline_access',
    },
    {
        'service_type': 'github',
        'name': 'GitHub',
        'description': 'Connect your personal GitHub account.',
        'scope': 'user_personal',
        'oauth2_auth_url': 'https://github.com/login/oauth/authorize',
        'oauth2_token_url': 'https://github.com/login/oauth/access_token',
        'oauth2_scopes': 'repo read:user',
    },
    {
        'service_type': 'zotero',
        'name': 'Zotero',
        'description': 'Personal Zotero library access via API key.',
        'scope': 'dual',
    },
    {
        'service_type': 'openai',
        'name': 'OpenAI / LLM API',
        'description': 'Personal OpenAI API key. Overrides the global admin key when set.',
        'scope': 'dual',
    },
    {
        'service_type': 'pubmed',
        'name': 'PubMed / NCBI',
        'description': 'Personal NCBI API key for higher rate limits.',
        'scope': 'dual',
    },
]


def seed_default_services() -> None:
    """Create default GlobalIntegrationService rows if they don't exist.

    Call this once from app/__init__.py after db creation.
    """
    try:
        from app.database import db
        from app.models.integrations_registry import GlobalIntegrationService
        for defn in _SEED_SERVICES:
            existing = GlobalIntegrationService.query.filter_by(
                service_type=defn['service_type']).first()
            if not existing:
                svc = GlobalIntegrationService(
                    service_type=defn['service_type'],
                    name=defn['name'],
                    description=defn.get('description'),
                    scope=defn.get('scope', 'user_personal'),
                    is_enabled=False,
                    allow_user_override=True,
                    oauth2_auth_url=defn.get('oauth2_auth_url'),
                    oauth2_token_url=defn.get('oauth2_token_url'),
                    oauth2_scopes=defn.get('oauth2_scopes'),
                )
                db.session.add(svc)
        db.session.commit()
        log.debug('integration_service: default services seeded')
    except Exception as exc:
        log.warning(f'seed_default_services failed (non-fatal): {exc}')


def _get_global_integration_service_or_raise(service_id: int):
    from app.database import db
    from app.models.integrations_registry import GlobalIntegrationService

    svc = db.session.get(GlobalIntegrationService, service_id)
    if svc is None:
        raise ValueError(f'Integration service {service_id} not found')
    return svc


# ---------------------------------------------------------------------------
# Admin CRUD
# ---------------------------------------------------------------------------

def admin_update_service(service_id: int, data: dict) -> GlobalIntegrationService:
    """Update a GlobalIntegrationService from admin form data."""
    from app.database import db
    svc = _get_global_integration_service_or_raise(service_id)

    for field in ('name', 'description', 'scope', 'oauth2_client_id',
                  'oauth2_auth_url', 'oauth2_token_url', 'oauth2_scopes',
                  'oauth2_redirect_uri'):
        if field in data and data[field] is not None:
            setattr(svc, field, data[field] or None)

    svc.is_enabled = bool(data.get('is_enabled'))
    svc.allow_user_override = bool(data.get('allow_user_override', True))

    # Handle secret fields — only update if a non-empty value was submitted
    if data.get('oauth2_client_secret'):
        svc.oauth2_client_secret_encrypted = encrypt_secret(data['oauth2_client_secret'])
    if data.get('global_api_key'):
        svc.global_api_key_encrypted = encrypt_secret(data['global_api_key'])

    # Global extra config (arbitrary JSON)
    if 'global_extra_config' in data and data['global_extra_config']:
        svc.global_extra_config = data['global_extra_config']

    db.session.commit()
    return svc


def admin_test_service(service_id: int) -> tuple[bool, str, Optional[int]]:
    """Run a basic connectivity test for a service.

    Returns (success, message, latency_ms).
    """
    import time
    from app.database import db
    from app.core.time_utils import utcnow_naive
    svc = _get_global_integration_service_or_raise(service_id)

    start = time.monotonic()
    success = False
    message = 'No test logic defined for this service type.'
    latency_ms: Optional[int] = None

    try:
        import requests as rq
        # For OAuth2 services: ping the token endpoint
        if svc.oauth2_token_url:
            resp = rq.head(svc.oauth2_token_url, timeout=5)
            latency_ms = int((time.monotonic() - start) * 1000)
            success = resp.status_code < 500
            message = f'HTTP {resp.status_code} from token endpoint ({latency_ms} ms)'
        elif svc.service_type == 'zotero':
            resp = rq.get('https://api.zotero.org/', timeout=5)
            latency_ms = int((time.monotonic() - start) * 1000)
            success = resp.status_code == 200
            message = f'Zotero API reachable ({latency_ms} ms)'
        elif svc.service_type == 'pubmed':
            resp = rq.get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi', timeout=5)
            latency_ms = int((time.monotonic() - start) * 1000)
            success = resp.status_code == 200
            message = f'PubMed API reachable ({latency_ms} ms)'
        else:
            message = 'No test URL configured for this service.'
    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        message = f'Connection failed: {exc}'

    svc.last_tested_at = utcnow_naive()
    svc.last_test_ok = success
    svc.last_test_error = message if not success else None
    svc.last_test_latency_ms = latency_ms
    db.session.commit()
    return success, message, latency_ms


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

def get_user_credential(user_id: int, service_id: int) -> Optional[UserIntegrationCredential]:
    """Return the active credential for (user, service), or None."""
    from app.models.integrations_registry import UserIntegrationCredential
    return (UserIntegrationCredential.query
            .filter_by(user_id=user_id, service_id=service_id, is_active=True)
            .first())


def connect_api_key(user_id: int, service_id: int, api_key: str,
                    display_name: str = '',
                    extra_data: dict | None = None) -> UserIntegrationCredential:
    """Store (or update) a personal API key credential for a user."""
    from app.database import db
    from app.models.integrations_registry import UserIntegrationCredential

    existing = (UserIntegrationCredential.query
                .filter_by(user_id=user_id, service_id=service_id)
                .first())
    extra_payload = json.dumps(extra_data) if isinstance(extra_data, dict) and extra_data else None
    if existing:
        existing.api_key_encrypted = encrypt_secret(api_key)
        existing.is_active = True
        existing.display_name = display_name or existing.display_name
        existing.disconnected_at = None
        existing.extra_data = extra_payload
        cred = existing
    else:
        cred = UserIntegrationCredential(
            user_id=user_id,
            service_id=service_id,
            api_key_encrypted=encrypt_secret(api_key),
            display_name=display_name,
            extra_data=extra_payload,
            is_active=True,
        )
        db.session.add(cred)
        # Increment connected_user_count on service
        from app.models.integrations_registry import GlobalIntegrationService
        svc = db.session.get(GlobalIntegrationService, service_id)
        if svc:
            svc.connected_user_count = (svc.connected_user_count or 0) + 1

    db.session.commit()
    return cred


def disconnect_service(user_id: int, service_id: int) -> bool:
    """Deactivate the user's credential for a service."""
    from app.database import db
    from app.models.integrations_registry import UserIntegrationCredential, GlobalIntegrationService
    from app.core.time_utils import utcnow_naive
    cred = (UserIntegrationCredential.query
            .filter_by(user_id=user_id, service_id=service_id, is_active=True)
            .first())
    if not cred:
        return False
    cred.is_active = False
    cred.disconnected_at = utcnow_naive()
    svc = db.session.get(GlobalIntegrationService, service_id)
    if svc and svc.connected_user_count and svc.connected_user_count > 0:
        svc.connected_user_count -= 1
    db.session.commit()
    return True


def get_user_integrations(user_id: int) -> list[dict]:
    """Return all enabled services with a flag indicating whether the user is connected."""
    from app.models.integrations_registry import GlobalIntegrationService, UserIntegrationCredential
    services = GlobalIntegrationService.query.filter_by(is_enabled=True).order_by(
        GlobalIntegrationService.name).all()
    creds_by_svc = {
        c.service_id: c
        for c in UserIntegrationCredential.query.filter_by(user_id=user_id, is_active=True).all()
    }
    result = []
    for svc in services:
        cred = creds_by_svc.get(svc.id)
        result.append({
            'service': svc.to_dict(),
            'connected': bool(cred),
            'credential': cred.to_dict() if cred else None,
        })
    return result


def resolve_api_key(user_id: int, service_type: str) -> Optional[str]:
    """Resolve the effective API key for a user + service type.

    Priority: user personal key → global admin key.
    Returns the plaintext key or None.
    """
    from app.models.integrations_registry import GlobalIntegrationService, UserIntegrationCredential
    svc = GlobalIntegrationService.query.filter_by(service_type=service_type).first()
    if not svc:
        return None
    # 1. User personal credential
    cred = get_user_credential(user_id, svc.id)
    if cred and cred.api_key_encrypted:
        try:
            return decrypt_secret(cred.api_key_encrypted)
        except Exception:
            pass
    # 2. Global admin key
    if svc.global_api_key_encrypted:
        try:
            return decrypt_secret(svc.global_api_key_encrypted)
        except Exception:
            pass
    # 3. Config fallback
    from app.config_manager import config_manager
    key_map = {
        'openai': 'openai_api_key',
        'pubmed': 'pubmed_api_key',
        'arxiv': 'arxiv_api_key',
        'crossref': 'crossref_api_key',
    }
    config_key = key_map.get(service_type)
    if config_key:
        return config_manager.get(config_key) or None
    return None
