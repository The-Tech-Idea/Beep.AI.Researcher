"""Tests for admin settings and governance routes."""
import copy
from pathlib import Path
import uuid
from unittest.mock import PropertyMock, patch

import pytest

from app.config import get_config
from app.config_manager import config_manager
from app.database import db
from app.models.core import AuditLog, Role, User
from app.services import mfa_service


RESEARCHER_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def admin_client(app):
    """Authenticated admin client for admin route testing."""
    with app.app_context():
        role = Role.query.filter_by(name="Admin").first()
        if not role:
            role = Role(name="Admin")
            db.session.add(role)
            db.session.flush()

        user = User(
            username=f"admin_{uuid.uuid4().hex[:8]}",
            email=f"admin_{uuid.uuid4().hex[:8]}@example.com",
            role_id=role.id,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True
            sess["user_id"] = user.id
        yield client


def test_admin_settings_page_loads(admin_client):
    response = admin_client.get("/admin/settings")
    assert response.status_code == 200
    assert b"Research Service Connection" in response.data
    assert b"Service URL" in response.data
    assert b"Beep.AI.Server Integration" not in response.data
    assert b"Feature Flags" in response.data
    assert b"Runtime Tuning" in response.data
    assert b"Local Services Status" in response.data
    assert b"css/admin_settings_page.css" in response.data
    assert b"js/admin_settings_page.js" in response.data
    assert b'id="admin-settings-config"' in response.data
    assert b"sessionStorage.getItem('adminSettingsTab')" not in response.data
    assert b"style.display" not in response.data
    assert b'style="display:none"' not in response.data
    assert b"alert alert-" not in response.data
    assert b"alert alert-info" not in response.data
    assert b"text-muted" not in response.data
    assert b"btn btn-outline-secondary" not in response.data
    assert b"btn btn-sm btn-outline-secondary" not in response.data
    assert b"btn btn-outline-primary" not in response.data


def test_admin_index_uses_plain_language_service_badge(admin_client):
    response = admin_client.get("/admin/")

    assert response.status_code == 200
    assert b"Service, Email, Limits" in response.data
    assert b"Beep.AI.Server, Email, Limits" not in response.data


def test_admin_index_uses_asset_based_workflow(admin_client):
    response = admin_client.get("/admin/")

    assert response.status_code == 200
    assert b"css/admin_dashboard_page.css" in response.data
    assert b"border-primary border-opacity-25" not in response.data
    assert b"badge bg-primary" not in response.data
    assert b"badge bg-secondary" not in response.data
    assert b"badge bg-info text-dark" not in response.data
    assert b"badge bg-warning text-dark" not in response.data
    assert b"badge bg-light text-dark border" not in response.data
    assert b"border-0 bg-light" not in response.data
    assert b"text-success" not in response.data
    assert b"text-warning" not in response.data
    assert b'style="width:140px"' not in response.data
    assert b"btn btn-outline-info" not in response.data
    assert b"btn btn-outline-warning" not in response.data


def test_admin_localization_page_uses_asset_based_workflow(admin_client):
    response = admin_client.get("/admin/localization")

    assert response.status_code == 200
    assert b"css/admin_localization_page.css" in response.data
    assert b"btn btn-primary" not in response.data
    assert b"btn btn-outline-primary" not in response.data


def test_admin_users_page_uses_asset_based_workflow(admin_client):
    response = admin_client.get("/admin/users")

    assert response.status_code == 200
    assert b"css/admin_users_page.css" in response.data
    assert b"js/admin_user_management_page.js" in response.data
    assert b'onchange="this.form.submit()"' not in response.data
    assert b'style="min-width:160px"' not in response.data
    assert b'style="width:auto;"' not in response.data
    assert b"alert alert-" not in response.data
    assert b"badge bg-success" not in response.data
    assert b"badge bg-danger" not in response.data
    assert b"badge bg-primary" not in response.data
    assert b"badge bg-warning text-dark" not in response.data
    assert b"btn btn-sm btn-outline-warning" not in response.data
    assert b"btn btn-sm btn-outline-success" not in response.data
    assert b"btn btn-sm btn-outline-primary" not in response.data


def test_admin_document_management_page_uses_asset_based_workflow(admin_client):
    response = admin_client.get("/admin/documents")

    assert response.status_code == 200
    assert b"css/admin_document_management_page.css" in response.data
    assert b"js/admin_document_management_page.js" in response.data
    assert b"onsubmit=" not in response.data
    assert b"alert alert-" not in response.data
    assert b"text-bg-primary" not in response.data
    assert b"text-bg-secondary" not in response.data
    assert b"table-dark" not in response.data
    assert b"badge bg-secondary" not in response.data
    assert b"badge bg-light text-dark border" not in response.data
    assert b"btn btn-sm btn-outline-danger" not in response.data


def test_admin_invites_page_uses_asset_based_workflow(admin_client):
    response = admin_client.get("/admin/invites")

    assert response.status_code == 200
    assert b"css/admin_invites_page.css" in response.data
    assert b"js/admin_invites_page.js" in response.data
    assert b"onclick=" not in response.data
    assert b"alert alert-" not in response.data
    assert b"badge bg-secondary" not in response.data
    assert b"badge bg-danger" not in response.data
    assert b"badge bg-success" not in response.data
    assert b"btn btn-sm btn-outline-danger" not in response.data
    assert b"navigator.clipboard.writeText" not in response.data


def test_admin_user_create_page_uses_asset_based_workflow(admin_client):
    response = admin_client.get("/admin/users/create")

    assert response.status_code == 200
    assert b"css/admin_user_create_page.css" in response.data
    assert b'style="max-width:600px"' not in response.data
    assert b"alert alert-" not in response.data
    assert b"text-danger" not in response.data


def test_admin_user_import_page_uses_asset_based_workflow(admin_client):
    response = admin_client.get("/admin/users/import")

    assert response.status_code == 200
    assert b"css/admin_user_import_page.css" in response.data
    assert b"alert alert-" not in response.data
    assert b"text-danger" not in response.data
    assert b"bg-light" not in response.data
    assert b"text-muted" not in response.data


def test_admin_user_detail_page_uses_asset_based_workflow(admin_client, app):
    with app.app_context():
        role = Role.query.filter_by(name="Member").first()
        if not role:
            role = Role(name="Member")
            db.session.add(role)
            db.session.flush()

        user = User(
            username=f"detail_user_{uuid.uuid4().hex[:8]}",
            email=f"detail_user_{uuid.uuid4().hex[:8]}@example.com",
            role_id=role.id,
            is_active=True,
        )
        user.email_verified = True
        user.mfa_enabled = True
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    response = admin_client.get(f"/admin/users/{user_id}")

    assert response.status_code == 200
    assert b"css/admin_user_detail_page.css" in response.data
    assert b"js/admin_user_management_page.js" in response.data
    assert b"onclick=" not in response.data
    assert b"onsubmit=" not in response.data
    assert b"alert alert-" not in response.data
    assert b"badge bg-success" not in response.data
    assert b"badge bg-danger" not in response.data
    assert b"badge bg-info text-dark" not in response.data
    assert b"badge bg-warning text-dark" not in response.data
    assert b"badge bg-primary" not in response.data
    assert b"badge bg-secondary" not in response.data
    assert b"border-warning" not in response.data
    assert b"bg-warning text-dark" not in response.data
    assert b"border-danger" not in response.data
    assert b"bg-danger text-white" not in response.data
    assert b"text-muted" not in response.data
    assert b"btn btn-outline-secondary" not in response.data


def test_setup_page_uses_plain_language_setup_copy(app):
    with patch.object(type(config_manager), "is_configured", new_callable=PropertyMock, return_value=False):
        response = app.test_client().get("/setup/")

    assert response.status_code == 200
    assert b"Initial workspace setup" in response.data
    assert b"Administrator account" in response.data
    assert b"External sign-in (OpenID Connect)" in response.data
    assert b"Finish and open app" in response.data
    assert b"css/setup.css" in response.data
    assert b"js/setup.js" in response.data
    assert b"js/base_shell.js" in response.data
    assert b"js/flow_notifications.js" in response.data
    assert b"onclick=" not in response.data
    assert b"function goToStep2()" not in response.data
    assert b"const themeBtns = document.querySelectorAll('.theme-btn');" not in response.data
    assert b"<style>" not in response.data
    assert b"Initial Setup Wizard" not in response.data
    assert b"IdentityServer (OIDC)" not in response.data


def test_setup_script_uses_shared_ui_feedback_helper():
    setup_js = (RESEARCHER_ROOT / "static/js/setup.js").read_text(encoding="utf-8")

    assert "window.alert(" not in setup_js
    assert "spinner-border" not in setup_js
    assert "window.beepUI.notify(" in setup_js
    assert "window.beepUI.setButtonLoading(" in setup_js


def test_live_admin_route_files_avoid_legacy_primary_key_query_helpers():
    auth_routes = (RESEARCHER_ROOT / "app/routes/auth_routes.py").read_text(encoding="utf-8")
    # admin_routes.py was split; user management moved to admin/admin_users.py
    admin_users_routes = (RESEARCHER_ROOT / "app/routes/admin/admin_users.py").read_text(encoding="utf-8")
    admin_integrations_routes = (RESEARCHER_ROOT / "app/routes/admin_integrations.py").read_text(encoding="utf-8")

    assert ".query.get_or_404(" not in auth_routes
    assert ".query.get(" not in auth_routes
    assert "def user_detail(user_id):" in admin_users_routes
    assert "user = get_entity_or_404(User, user_id)" in admin_users_routes
    assert "target = get_entity_or_404(User, user_id)" in admin_users_routes
    assert ".query.get_or_404(" not in admin_integrations_routes


def test_mfa_backup_codes_page_uses_asset_based_workflow(admin_client):
    response = admin_client.get("/auth/mfa/backup-codes")

    assert response.status_code == 200
    assert b"css/mfa_backup_codes.css" in response.data
    assert b"js/mfa_backup_codes.js" in response.data
    assert b'id="mfa-backup-codes-config"' in response.data
    assert b'onclick=' not in response.data
    assert b'function copyAllCodes()' not in response.data
    assert b'style="max-width:540px"' not in response.data
    assert b'text-warning fs-5' not in response.data


def test_mfa_setup_page_uses_asset_based_workflow(admin_client):
    response = admin_client.get("/auth/mfa/setup")

    assert response.status_code == 200
    assert b"css/mfa_setup.css" in response.data
    assert b"js/mfa_setup.js" in response.data
    assert b'id="mfa-setup-config"' in response.data
    assert b"onclick=" not in response.data
    assert b"navigator.clipboard.writeText" not in response.data
    assert b'style="max-width:520px"' not in response.data
    assert b'style="max-width:220px;"' not in response.data
    assert b"text-success fs-5" not in response.data


def test_mfa_setup_sms_page_uses_asset_based_workflow(admin_client):
    response = admin_client.get("/auth/mfa/setup/sms")

    assert response.status_code == 200
    assert b"css/mfa_setup_sms.css" in response.data
    assert b'style="max-width:520px"' not in response.data
    assert b"letter-spacing:.4em; font-size:1.3rem;" not in response.data
    assert b"text-primary fs-5" not in response.data


def test_mfa_challenge_page_uses_asset_based_workflow(app):
    with app.app_context():
        role = Role.query.filter_by(name="Member").first()
        if not role:
            role = Role(name="Member")
            db.session.add(role)
            db.session.flush()

        user = User(
            username=f"mfa_user_{uuid.uuid4().hex[:8]}",
            email=f"mfa_user_{uuid.uuid4().hex[:8]}@example.com",
            role_id=role.id,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    client = app.test_client()
    with client.session_transaction() as sess:
        sess[mfa_service._SESSION_PENDING_USER] = user_id

    response = client.get("/auth/mfa")

    assert response.status_code == 200
    assert b"css/mfa_challenge.css" in response.data
    assert b'style="max-width:460px"' not in response.data
    assert b"text-primary fs-5" not in response.data
    assert b"Authenticator" not in response.data
    assert b"Email Code" in response.data


def test_change_password_page_uses_asset_based_workflow(admin_client):
    response = admin_client.get("/change-password")

    assert response.status_code == 200
    assert b"css/change_password.css" in response.data
    assert b'style="max-width:480px"' not in response.data
    assert b"card-header bg-warning text-dark" not in response.data
    assert b"btn btn-warning w-100 fw-semibold" not in response.data


def test_profile_page_uses_asset_based_workflow(admin_client):
    response = admin_client.get("/profile")

    assert response.status_code == 200
    assert b"css/profile.css" in response.data
    assert b"js/profile.js" in response.data
    assert b'id="profile-config"' in response.data
    assert b"onclick=" not in response.data
    assert b"confirm('Disable MFA? Your account will be less secure.')" not in response.data
    assert b"badge bg-primary" not in response.data
    assert b"badge bg-secondary" not in response.data


def test_my_sessions_page_uses_asset_based_workflow(admin_client):
    response = admin_client.get("/auth/sessions")

    assert response.status_code == 200
    assert b"css/my_sessions.css" in response.data
    assert b"js/my_sessions.js" in response.data
    assert b"my-sessions-container" in response.data
    assert b"my-sessions-header-icon" in response.data
    assert b'style="max-width:780px"' not in response.data
    assert b'bi bi-display me-2 text-primary' not in response.data
    assert b"onsubmit=" not in response.data


def test_login_page_uses_asset_based_workflow(app):
    with patch.object(type(config_manager), "is_configured", new_callable=PropertyMock, return_value=True):
        response = app.test_client().get("/login")

    assert response.status_code == 200
    assert b"css/auth_entry.css" in response.data
    assert b"<style>" not in response.data
    assert b"bg-danger-subtle" not in response.data
    assert b"text-danger" not in response.data
    assert b"rgba(var(--bs-primary-rgb), 0.05)" not in response.data


def test_register_page_uses_asset_based_workflow(app):
    with patch.object(type(config_manager), "is_configured", new_callable=PropertyMock, return_value=True):
        response = app.test_client().get("/register")

    assert response.status_code == 200
    assert b"css/auth_entry.css" in response.data
    assert b"<style>" not in response.data
    assert b"bg-danger-subtle" not in response.data
    assert b"text-danger" not in response.data
    assert b"rgba(var(--bs-primary-rgb), 0.05)" not in response.data


def test_admin_integrations_page_uses_asset_based_workflow(admin_client, app):
    with app.app_context():
        try:
            from app.services.integration_service import seed_default_services
            seed_default_services()
        except Exception:
            pass

    response = admin_client.get("/admin/integrations/")

    assert response.status_code == 200
    assert b"css/admin_integrations_page.css" in response.data
    assert b"js/admin_integrations_page.js" in response.data
    assert b'id="admin-integrations-config"' in response.data
    assert b"onclick=" not in response.data
    assert b"async function testService" not in response.data
    assert b"async function disableService" not in response.data
    assert b"alert alert-" not in response.data
    assert b"badge bg-success" not in response.data
    assert b"btn btn-sm btn-outline-secondary" not in response.data
    assert b"btn btn-sm btn-outline-info" not in response.data
    assert b"btn btn-sm btn-outline-primary" not in response.data
    assert b"btn btn-outline-danger btn-sm" not in response.data
    assert b"text-muted" not in response.data
    assert b"text-success" not in response.data
    assert b"text-danger" not in response.data


def test_admin_integration_users_page_uses_asset_based_workflow(admin_client, app):
    with app.app_context():
        try:
            from app.services.integration_service import seed_default_services
            from app.models.integrations_registry import GlobalIntegrationService

            seed_default_services()
            service = GlobalIntegrationService.query.order_by(GlobalIntegrationService.id.asc()).first()
            assert service is not None
            service_id = service.id
        except Exception as exc:
            pytest.fail(f"Failed to prepare integration users page test: {exc}")

    response = admin_client.get(f"/admin/integrations/{service_id}/users")

    assert response.status_code == 200
    assert b"css/admin_integration_users_page.css" in response.data
    assert b"js/admin_integration_users_page.js" in response.data
    assert b"onclick=" not in response.data
    assert b"alert alert-" not in response.data
    assert b"btn btn-sm btn-outline-danger" not in response.data
    assert b"text-muted" not in response.data


def test_admin_quota_management_page_uses_asset_based_workflow(admin_client):
    response = admin_client.get("/admin/quota")

    assert response.status_code == 200
    assert b"css/admin_quota_management_page.css" in response.data
    assert b"js/admin_quota_management_page.js" in response.data
    assert b'id="admin-quota-config"' in response.data
    assert b"onsubmit=" not in response.data
    assert b"sessionStorage.getItem('adminQuotaTab')" not in response.data
    assert b"style=\"height:6px\"" not in response.data
    assert b"style=\"width:200px\"" not in response.data
    assert b"alert alert-" not in response.data
    assert b"border-0 bg-light" not in response.data
    assert b"table-light" not in response.data
    assert b"btn btn-sm btn-outline-danger" not in response.data
    assert b"badge bg-warning" not in response.data
    assert b"progress-bar bg-" not in response.data
    assert b"text-muted" not in response.data


def test_admin_settings_update_applies_runtime_overrides(admin_client):
    runtime = get_config()
    original_features = copy.deepcopy(runtime.get_all_features())
    original_queue = copy.deepcopy(runtime.get_queue_config())
    original_cache = copy.deepcopy(runtime.get_cache_config())
    original_legacy_features = copy.deepcopy(config_manager.get("features", {}))
    original_legacy_queue = copy.deepcopy(config_manager.get("queue", {}))
    original_legacy_cache = copy.deepcopy(config_manager.get("cache", {}))

    try:
        payload = {
            "queue_max_workers": "6",
            "queue_max_retries": "2",
            "queue_job_timeout_seconds": "4000",
            "cache_cache_ttl_seconds": "1800",
            "cache_max_cache_entries": "2222",
            "cache_max_cache_size_mb": "333",
            "feature_auto_extract": "on",
            "feature_chat_enabled": "on",
        }
        response = admin_client.post("/admin/settings/update", data=payload, follow_redirects=False)
        assert response.status_code in (302, 303)

        assert runtime.get_queue_config()["max_workers"] == 6
        assert runtime.get_queue_config()["max_retries"] == 2
        assert runtime.get_queue_config()["job_timeout_seconds"] == 4000
        assert runtime.get_cache_config()["cache_ttl_seconds"] == 1800
        assert runtime.get_cache_config()["max_cache_entries"] == 2222
        assert runtime.get_cache_config()["max_cache_size_mb"] == 333

        persisted_features = config_manager.get("features", {})
        assert isinstance(persisted_features, dict)
        assert persisted_features.get("auto_extract") is True
    finally:
        for name, cfg in original_features.items():
            enabled = cfg.get("enabled", False) if isinstance(cfg, dict) else bool(cfg)
            runtime.set_feature_enabled(name, enabled)
        runtime.set_queue_values(original_queue)
        runtime.set_cache_values(original_cache)
        config_manager.set("features", original_legacy_features if isinstance(original_legacy_features, dict) else {})
        config_manager.set("queue", original_legacy_queue if isinstance(original_legacy_queue, dict) else {})
        config_manager.set("cache", original_legacy_cache if isinstance(original_legacy_cache, dict) else {})


def test_admin_governance_renders_audit_entries(admin_client):
    # Insert a synthetic audit row directly; user_id is optional in UI rendering.
    row = AuditLog(action="export.bundle", resource="project", resource_id="42", project_id=1)
    db.session.add(row)
    db.session.commit()

    response = admin_client.get("/admin/governance")
    assert response.status_code == 200
    assert b"css/admin_governance_page.css" in response.data
    assert b'class="badge"' not in response.data
    assert b"btn btn-outline-light" not in response.data
    assert b"export.bundle" in response.data
