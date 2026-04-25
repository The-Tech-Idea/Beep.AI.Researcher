"""User-facing integration routes — /integrations.

Allows authenticated users to:
- View all enabled integration services (Phase 9d)
- Connect a personal API key to a user_personal / dual-mode service
- Connect via OAuth2 (authorization-code flow)
- Disconnect their personal credential

Blueprint: user_integrations_bp  — prefix /integrations
"""
from flask import (
    Blueprint, render_template, redirect, url_for,
    request, flash, session, current_app
)
from flask_login import login_required, current_user
from urllib.parse import urlencode
import secrets

from app.models.integrations_registry import (
    GlobalIntegrationService, UserIntegrationCredential,
    SCOPE_ADMIN_ONLY,
)
from app.routes.route_entity_lookup import get_entity_or_404
from app.services.integration_service import (
    connect_api_key, disconnect_service,
)

user_integrations_bp = Blueprint('user_integrations', __name__, url_prefix='/integrations')


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _services_for_user() -> list[GlobalIntegrationService]:
    """Return enabled services that are visible to regular users."""
    return GlobalIntegrationService.query.filter(
        GlobalIntegrationService.is_enabled == True,
        GlobalIntegrationService.scope != SCOPE_ADMIN_ONLY,
    ).order_by(GlobalIntegrationService.name).all()


def _user_cred(service_id: int) -> UserIntegrationCredential | None:
    return UserIntegrationCredential.query.filter_by(
        user_id=current_user.id,
        service_id=service_id,
        is_active=True,
    ).first()


def _extract_service_extra_data(svc: GlobalIntegrationService) -> dict:
    """Extract provider-specific connection metadata from the submitted form."""
    if svc.service_type != 'zotero':
        return {}

    user_id = (request.form.get('zotero_user_id') or '').strip()
    library_type = (request.form.get('zotero_library_type') or 'user').strip().lower() or 'user'
    group_id = (request.form.get('zotero_group_id') or '').strip()

    if not user_id:
        raise ValueError('Zotero user ID is required.')
    if library_type not in {'user', 'group'}:
        raise ValueError('Zotero library type must be user or group.')
    if library_type == 'group' and not group_id:
        raise ValueError('Zotero group ID is required for group libraries.')

    return {
        'user_id': user_id,
        'library_type': library_type,
        'group_id': group_id or None,
    }


def _build_display_name(
    svc: GlobalIntegrationService,
    display_name: str | None,
    extra_data: dict,
) -> str | None:
    if display_name:
        return display_name
    if svc.service_type != 'zotero':
        return None

    library_type = extra_data.get('library_type', 'user')
    if library_type == 'group' and extra_data.get('group_id'):
        return f"Zotero group {extra_data['group_id']} (user {extra_data['user_id']})"
    return f"Zotero user {extra_data['user_id']}"


# ─────────────────────────────────────────────────────────────────────────────
# My integrations list
# ─────────────────────────────────────────────────────────────────────────────

@user_integrations_bp.route('/')
@login_required
def my_integrations():
    """Show all enabled integration services with connected/disconnected status."""
    services = _services_for_user()
    cred_map: dict[int, UserIntegrationCredential] = {}
    for svc in services:
        c = _user_cred(svc.id)
        if c:
            cred_map[svc.id] = c
    return render_template(
        'integrations/my_integrations.html',
        services=services,
        cred_map=cred_map,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Connect via API key
# ─────────────────────────────────────────────────────────────────────────────

@user_integrations_bp.route('/<int:service_id>/connect', methods=['POST'])
@login_required
def connect_service(service_id):
    svc = get_entity_or_404(GlobalIntegrationService, service_id)
    if not svc.is_enabled or svc.scope == SCOPE_ADMIN_ONLY:
        flash('Service is not available.', 'error')
        return redirect(url_for('user_integrations.my_integrations'))
    if not svc.allow_user_override:
        flash('You cannot connect a personal account to this service.', 'error')
        return redirect(url_for('user_integrations.my_integrations'))

    api_key = request.form.get('api_key', '').strip()
    display_name = request.form.get('display_name', '').strip() or None
    if not api_key:
        flash('API key is required.', 'error')
        return redirect(url_for('user_integrations.my_integrations'))

    try:
        extra_data = _extract_service_extra_data(svc)
        connect_api_key(
            current_user.id,
            service_id,
            api_key,
            _build_display_name(svc, display_name, extra_data),
            extra_data=extra_data,
        )
        flash(f'Connected to {svc.name}.', 'success')
    except ValueError as exc:
        flash(str(exc), 'error')
    except Exception as exc:
        current_app.logger.exception('connect_api_key failed for user %s svc %s', current_user.id, service_id)
        flash(f'Connection failed: {exc}', 'error')

    return redirect(url_for('user_integrations.my_integrations'))


# ─────────────────────────────────────────────────────────────────────────────
# Disconnect
# ─────────────────────────────────────────────────────────────────────────────

@user_integrations_bp.route('/<int:service_id>/disconnect', methods=['POST'])
@login_required
def disconnect_service_route(service_id):
    svc = get_entity_or_404(GlobalIntegrationService, service_id)
    disconnect_service(current_user.id, service_id)
    flash(f'Disconnected from {svc.name}.', 'success')
    return redirect(url_for('user_integrations.my_integrations'))


# ─────────────────────────────────────────────────────────────────────────────
# OAuth2 — start (redirect to provider)
# ─────────────────────────────────────────────────────────────────────────────

@user_integrations_bp.route('/<int:service_id>/oauth2/start')
@login_required
def oauth2_start(service_id):
    svc = get_entity_or_404(GlobalIntegrationService, service_id)
    if not svc.is_enabled or svc.scope == SCOPE_ADMIN_ONLY:
        flash('Service is not available.', 'error')
        return redirect(url_for('user_integrations.my_integrations'))
    if not svc.oauth2_auth_url or not svc.oauth2_client_id:
        flash('OAuth2 is not configured for this service.', 'error')
        return redirect(url_for('user_integrations.my_integrations'))

    state = secrets.token_urlsafe(24)
    session['oauth2_state'] = state
    session['oauth2_service_id'] = service_id

    redirect_uri = (
        svc.oauth2_redirect_uri
        or url_for('user_integrations.oauth2_callback', _external=True)
    )
    params = {
        'client_id': svc.oauth2_client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': svc.oauth2_scopes or '',
        'state': state,
        'access_type': 'offline',
        'prompt': 'consent',
    }
    return redirect(f"{svc.oauth2_auth_url}?{urlencode(params)}")


# ─────────────────────────────────────────────────────────────────────────────
# OAuth2 — callback (exchange code for tokens)
# ─────────────────────────────────────────────────────────────────────────────

@user_integrations_bp.route('/oauth2/callback')
@login_required
def oauth2_callback():
    import requests as req_lib

    error = request.args.get('error')
    if error:
        flash(f'OAuth2 error: {error}', 'error')
        return redirect(url_for('user_integrations.my_integrations'))

    state = request.args.get('state')
    if not state or state != session.pop('oauth2_state', None):
        flash('OAuth2 state mismatch — please try again.', 'error')
        return redirect(url_for('user_integrations.my_integrations'))

    service_id = session.pop('oauth2_service_id', None)
    if not service_id:
        flash('Session expired — please try again.', 'error')
        return redirect(url_for('user_integrations.my_integrations'))

    code = request.args.get('code')
    if not code:
        flash('No authorization code received.', 'error')
        return redirect(url_for('user_integrations.my_integrations'))

    svc = get_entity_or_404(GlobalIntegrationService, service_id)
    redirect_uri = (
        svc.oauth2_redirect_uri
        or url_for('user_integrations.oauth2_callback', _external=True)
    )

    # Exchange code for token
    try:
        resp = req_lib.post(
            svc.oauth2_token_url,
            data={
                'code': code,
                'client_id': svc.oauth2_client_id,
                'client_secret': _get_oauth2_secret(svc),
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            },
            timeout=10,
        )
        resp.raise_for_status()
        token_data = resp.json()
    except Exception as exc:
        current_app.logger.exception('OAuth2 token exchange failed svc %s', service_id)
        flash(f'OAuth2 token exchange failed: {exc}', 'error')
        return redirect(url_for('user_integrations.my_integrations'))

    access_token = token_data.get('access_token', '')
    refresh_token = token_data.get('refresh_token', '')
    token_blob = access_token
    if refresh_token:
        token_blob = f"{access_token}::{refresh_token}"

    connect_api_key(current_user.id, service_id, token_blob, display_name=None)
    flash(f'Connected to {svc.name} via OAuth2.', 'success')
    return redirect(url_for('user_integrations.my_integrations'))


def _get_oauth2_secret(svc: GlobalIntegrationService) -> str:
    """Decrypt the client secret — returns empty string if not set."""
    if not svc.oauth2_client_secret_encrypted:
        return ''
    try:
        from app.services.integration_service import decrypt_secret
        return decrypt_secret(svc.oauth2_client_secret_encrypted)
    except Exception:
        return ''
