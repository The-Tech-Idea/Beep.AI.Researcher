"""Admin Integrations routes — Phase 9c of Admin Enhancement Plan.

Blueprint: admin_integrations_bp  (url_prefix=/admin/integrations)
Registered in: app/__init__.py alongside admin_bp.

Routes
------
GET  /admin/integrations              → integrations_list
POST /admin/integrations/<id>/update  → integration_update
POST /admin/integrations/<id>/test    → integration_test     (returns JSON)
POST /admin/integrations/<id>/disable → integration_disable
GET  /admin/integrations/<id>/users   → integration_users    (connected users)
POST /admin/integrations/<id>/users/<uid>/disconnect → admin_disconnect_user
"""
from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user

from app.database import db
from app.routes.route_entity_lookup import get_entity_or_404

admin_integrations_bp = Blueprint(
    'admin_integrations', __name__, url_prefix='/admin/integrations')


def admin_required(f):
    @wraps(f)
    def inner(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not getattr(current_user, 'is_admin', False):
            flash('Admin access required.', 'danger')
            return redirect(url_for('researcher.index'))
        return f(*args, **kwargs)
    return inner


@admin_integrations_bp.route('/')
@login_required
@admin_required
def integrations_list():
    """Admin: overview of all registered integration services."""
    from app.models.integrations_registry import GlobalIntegrationService
    services = GlobalIntegrationService.query.order_by(
        GlobalIntegrationService.scope,
        GlobalIntegrationService.name,
    ).all()
    return render_template('admin/integrations.html', services=services)


@admin_integrations_bp.route('/<int:service_id>/update', methods=['POST'])
@login_required
@admin_required
def integration_update(service_id):
    """Admin: save service settings (name, OAuth2 app, global key, enabled flag)."""
    from app.services.integration_service import admin_update_service
    data = {
        'name': request.form.get('name', '').strip(),
        'description': request.form.get('description', '').strip() or None,
        'is_enabled': 'is_enabled' in request.form,
        'allow_user_override': 'allow_user_override' in request.form,
        'scope': request.form.get('scope', '').strip() or None,
        'oauth2_client_id': request.form.get('oauth2_client_id', '').strip() or None,
        'oauth2_client_secret': request.form.get('oauth2_client_secret', '').strip() or None,
        'oauth2_auth_url': request.form.get('oauth2_auth_url', '').strip() or None,
        'oauth2_token_url': request.form.get('oauth2_token_url', '').strip() or None,
        'oauth2_scopes': request.form.get('oauth2_scopes', '').strip() or None,
        'oauth2_redirect_uri': request.form.get('oauth2_redirect_uri', '').strip() or None,
        'global_api_key': request.form.get('global_api_key', '').strip() or None,
        'global_extra_config': request.form.get('global_extra_config', '').strip() or None,
    }
    try:
        admin_update_service(service_id, data)
        flash('Integration settings saved.', 'success')
    except Exception as exc:
        flash(f'Error saving settings: {exc}', 'danger')
    return redirect(url_for('admin_integrations.integrations_list'))


@admin_integrations_bp.route('/<int:service_id>/test', methods=['POST'])
@login_required
@admin_required
def integration_test(service_id):
    """Admin: test connectivity for a service. Returns JSON."""
    from app.services.integration_service import admin_test_service
    try:
        ok, message, latency_ms = admin_test_service(service_id)
        return jsonify({'success': ok, 'message': message, 'latency_ms': latency_ms})
    except Exception as exc:
        return jsonify({'success': False, 'message': str(exc), 'latency_ms': None})


@admin_integrations_bp.route('/<int:service_id>/disable', methods=['POST'])
@login_required
@admin_required
def integration_disable(service_id):
    """Admin: quickly disable a service (without changing other settings)."""
    from app.models.integrations_registry import GlobalIntegrationService
    svc = get_entity_or_404(GlobalIntegrationService, service_id)
    svc.is_enabled = False
    db.session.commit()
    flash(f'"{svc.name}" disabled.', 'success')
    return redirect(url_for('admin_integrations.integrations_list'))


@admin_integrations_bp.route('/<int:service_id>/users')
@login_required
@admin_required
def integration_users(service_id):
    """Admin: list users connected to a service."""
    from app.models.integrations_registry import GlobalIntegrationService, UserIntegrationCredential
    from app.models.core import User
    svc = get_entity_or_404(GlobalIntegrationService, service_id)
    creds = (UserIntegrationCredential.query
             .filter_by(service_id=service_id, is_active=True)
             .order_by(UserIntegrationCredential.connected_at.desc())
             .all())
    annotated = []
    for c in creds:
        u = db.session.get(User, c.user_id)
        annotated.append({'cred': c, 'user': u})
    return render_template(
        'admin/integration_users.html', svc=svc, connections=annotated)


@admin_integrations_bp.route('/<int:service_id>/users/<int:user_id>/disconnect',
                              methods=['POST'])
@login_required
@admin_required
def admin_disconnect_user(service_id, user_id):
    """Admin: force-disconnect a user from a service."""
    from app.services.integration_service import disconnect_service
    done = disconnect_service(user_id, service_id)
    if done:
        flash(f'User #{user_id} disconnected from service #{service_id}.', 'success')
    else:
        flash('No active credential found.', 'warning')
    return redirect(url_for('admin_integrations.integration_users', service_id=service_id))
