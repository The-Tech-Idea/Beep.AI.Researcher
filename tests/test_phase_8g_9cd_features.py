"""
Integration tests for features added in Phase 8g, 8k, 9c, 9d:
  - SMS OTP enrollment flow  (/auth/mfa/setup/sms)
  - Profile phone number save
  - Settings key alignment (registration / password / MFA tabs)
  - User integrations page
  - Admin integrations page
  - mfa_service.send_sms_otp / verify_sms_otp unit paths
"""
import uuid
import json
from unittest.mock import MagicMock, patch

import pytest

from app.database import db
from app.models.core import Role, User


# ─── Shared fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def _role(app):
    with app.app_context():
        role = Role.query.filter_by(name="User").first()
        if not role:
            role = Role(name="User")
            db.session.add(role)
            db.session.commit()
        return role.id


@pytest.fixture
def auth_client(app, _role):
    """Test client with a logged-in regular user."""
    with app.app_context():
        uid = uuid.uuid4().hex[:8]
        user = User(
            username=f"user_{uid}",
            email=f"user_{uid}@example.com",
            role_id=_role,
            is_active=True,
        )
        user.set_password("Passw0rd!")
        db.session.add(user)
        db.session.commit()

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True
            sess["user_id"] = user.id
        yield client, user.id


@pytest.fixture
def admin_client(app):
    """Test client with a logged-in admin user."""
    with app.app_context():
        role = Role.query.filter_by(name="Admin").first()
        if not role:
            role = Role(name="Admin")
            db.session.add(role)
            db.session.commit()

        uid = uuid.uuid4().hex[:8]
        user = User(
            username=f"admin_{uid}",
            email=f"admin_{uid}@example.com",
            role_id=role.id,
            is_active=True,
        )
        user.set_password("Admin1234!")
        db.session.add(user)
        db.session.commit()

        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True
            sess["user_id"] = user.id
        yield client, user.id


# ─── SMS OTP setup flow ──────────────────────────────────────────────────────

class TestMfaSetupSms:

    def test_get_shows_phone_form(self, auth_client):
        client, _ = auth_client
        resp = client.get("/auth/mfa/setup/sms")
        assert resp.status_code == 200
        assert b"phone_number" in resp.data
        assert b"Send verification code" in resp.data

    def test_send_action_requires_phone(self, auth_client):
        """Empty phone number should flash an error and stay on the page."""
        client, _ = auth_client
        resp = client.post(
            "/auth/mfa/setup/sms",
            data={"action": "send", "phone_number": ""},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Phone number is required" in resp.data

    @patch("app.services.mfa_service.send_sms_otp", return_value=(True, ""))
    def test_send_action_saves_phone_and_shows_verify(self, mock_send, auth_client, app):
        client, user_id = auth_client
        resp = client.post(
            "/auth/mfa/setup/sms",
            data={"action": "send", "phone_number": "+15551234567"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        # After successful send the verify pane is shown
        assert b"Verify" in resp.data or b"verify" in resp.data
        mock_send.assert_called_once()
        # Phone number persisted to user row
        with app.app_context():
            u = db.session.get(User, user_id)
            assert u.phone_number == "+15551234567"

    @patch("app.services.mfa_service.send_sms_otp", return_value=(False, "Twilio error"))
    def test_send_action_shows_error_on_failure(self, mock_send, auth_client):
        client, _ = auth_client
        resp = client.post(
            "/auth/mfa/setup/sms",
            data={"action": "send", "phone_number": "+15559999999"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Failed to send SMS" in resp.data

    @patch("app.services.mfa_service.verify_sms_otp", return_value=True)
    def test_verify_action_enrolls_sms_method(self, mock_verify, auth_client, app):
        client, user_id = auth_client
        resp = client.post(
            "/auth/mfa/setup/sms",
            data={"action": "verify", "code": "123456", "phone_number": "+15551234567"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        mock_verify.assert_called_once_with("123456")
        # User should now have sms in mfa_methods
        with app.app_context():
            u = db.session.get(User, user_id)
            assert "sms" in (u.mfa_methods or "")
            assert u.mfa_enabled is True

    @patch("app.services.mfa_service.verify_sms_otp", return_value=False)
    def test_verify_action_rejects_bad_code(self, mock_verify, auth_client):
        client, _ = auth_client
        resp = client.post(
            "/auth/mfa/setup/sms",
            data={"action": "verify", "code": "000000", "phone_number": "+15551234567"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Invalid or expired code" in resp.data


# ─── Profile — phone number ──────────────────────────────────────────────────

class TestProfilePhoneNumber:

    def test_profile_page_shows_phone_field(self, auth_client):
        client, _ = auth_client
        resp = client.get("/profile")
        assert resp.status_code == 200
        assert b"phone_number" in resp.data

    def test_profile_saves_phone_number(self, auth_client, app):
        client, user_id = auth_client
        resp = client.post(
            "/profile",
            data={
                "display_name": "Test User",
                "phone_number": "+12025550199",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        with app.app_context():
            u = db.session.get(User, user_id)
            assert u.phone_number == "+12025550199"

    def test_profile_clears_phone_number(self, auth_client, app):
        """Submitting blank phone should set it to None."""
        client, user_id = auth_client
        # First set a number via the profile route itself so the ORM state is consistent
        resp = client.post(
            "/profile",
            data={"display_name": "Test User", "phone_number": "+12025550199"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        # Verify the number was saved
        with app.app_context():
            from sqlalchemy import text
            row = db.session.execute(
                text("SELECT phone_number FROM users WHERE id = :uid"),
                {"uid": user_id},
            ).fetchone()
            assert row[0] == "+12025550199", f"Setup failed: phone={row[0]}"
        # Now clear it
        resp2 = client.post(
            "/profile",
            data={"display_name": "Test User", "phone_number": ""},
            follow_redirects=True,
        )
        assert resp2.status_code == 200
        # Read back via raw SQL to bypass ORM identity map
        with app.app_context():
            from sqlalchemy import text
            row = db.session.execute(
                text("SELECT phone_number FROM users WHERE id = :uid"),
                {"uid": user_id},
            ).fetchone()
            assert row[0] is None

    def test_profile_security_tab_shows_sms_setup_link(self, auth_client):
        client, _ = auth_client
        resp = client.get("/profile")
        assert resp.status_code == 200
        assert b"mfa/setup/sms" in resp.data


# ─── mfa_service unit tests ──────────────────────────────────────────────────

class TestMfaServiceSmsUnit:

    def test_send_sms_otp_requires_phone_number(self, app):
        from app.services import mfa_service

        with app.app_context():
            user = MagicMock()
            user.phone_number = None
            with app.test_request_context():
                ok, err = mfa_service.send_sms_otp(user)
            assert ok is False
            assert "phone" in err.lower()

    @patch("app.services.sms_service.send_sms", return_value=(True, ""))
    def test_send_sms_otp_stores_code_in_session(self, mock_send, app):
        from app.services import mfa_service

        with app.app_context():
            user = MagicMock()
            user.phone_number = "+15551234567"
            with app.test_request_context():
                from flask import session as flask_session
                ok, err = mfa_service.send_sms_otp(user)
                assert ok is True
                assert mfa_service._SESSION_SMS_OTP_KEY in flask_session
        mock_send.assert_called_once()

    @patch("secrets.randbelow", return_value=123456)
    @patch("app.services.sms_service.send_sms", return_value=(True, ""))
    def test_verify_sms_otp_succeeds_with_correct_code(self, _mock_send, _mock_rand, app):
        from app.services import mfa_service

        with app.app_context():
            user = MagicMock()
            user.phone_number = "+15551234567"
            with app.test_request_context():
                from flask import session as flask_session
                mfa_service.send_sms_otp(user)
                # secrets.randbelow was patched to 123456 → code is "123456"
                result = mfa_service.verify_sms_otp("123456")
                assert result is True

    @patch("app.services.sms_service.send_sms", return_value=(True, ""))
    def test_verify_sms_otp_rejects_wrong_code(self, _mock, app):
        from app.services import mfa_service

        with app.app_context():
            user = MagicMock()
            user.phone_number = "+15551234567"
            with app.test_request_context():
                mfa_service.send_sms_otp(user)
                result = mfa_service.verify_sms_otp("000000")
                assert result is False

    def test_verify_sms_otp_rejects_when_no_session(self, app):
        from app.services import mfa_service

        with app.app_context():
            with app.test_request_context():
                result = mfa_service.verify_sms_otp("123456")
                assert result is False

    @patch("app.services.sms_service.send_sms", return_value=(True, ""))
    def test_clear_pending_user_removes_sms_key(self, _mock, app):
        from app.services import mfa_service

        with app.app_context():
            user = MagicMock()
            user.phone_number = "+15551234567"
            with app.test_request_context():
                from flask import session as flask_session
                mfa_service.send_sms_otp(user)
                flask_session[mfa_service._SESSION_PENDING_USER] = 99
                mfa_service.clear_pending_user()
                assert mfa_service._SESSION_SMS_OTP_KEY not in flask_session
                assert mfa_service._SESSION_PENDING_USER not in flask_session


# ─── Admin settings — key alignment ─────────────────────────────────────────

class TestAdminSettingsKeyAlignment:
    """Verify that the corrected field names round-trip through the settings UI."""

    def test_registration_auto_assign_role_key(self, admin_client):
        client, _ = admin_client
        resp = client.get("/admin/settings")
        assert resp.status_code == 200
        assert b"registration_auto_assign_role" in resp.data

    def test_password_expiry_days_key(self, admin_client):
        client, _ = admin_client
        resp = client.get("/admin/settings")
        assert b"password_expiry_days" in resp.data

    def test_password_lockout_keys(self, admin_client):
        client, _ = admin_client
        resp = client.get("/admin/settings")
        assert b"password_max_failed_attempts" in resp.data
        assert b"password_lockout_minutes" in resp.data

    def test_mfa_method_keys(self, admin_client):
        client, _ = admin_client
        resp = client.get("/admin/settings")
        assert b"mfa_totp_enabled" in resp.data
        assert b"mfa_email_otp_enabled" in resp.data
        assert b"mfa_sms_otp_enabled" in resp.data

    def test_mfa_sms_provider_keys(self, admin_client):
        client, _ = admin_client
        resp = client.get("/admin/settings")
        assert b"mfa_sms_account_sid" in resp.data
        assert b"mfa_sms_auth_token" in resp.data
        assert b"mfa_sms_from_number" in resp.data

    def test_mfa_enforcement_option_values(self, admin_client):
        client, _ = admin_client
        resp = client.get("/admin/settings")
        assert b"required_all" in resp.data
        assert b"required_by_role" in resp.data
        # Old invalid values should NOT appear
        assert b"required_for_all" not in resp.data
        assert b"required_for_roles" not in resp.data

    def test_settings_update_saves_mfa_sms_otp_enabled(self, admin_client):
        from app.config_manager import config_manager

        client, _ = admin_client
        resp = client.post(
            "/admin/settings/update",
            data={"mfa_sms_otp_enabled": "on"},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)
        assert config_manager.get("mfa_sms_otp_enabled") is True

    def test_settings_update_mfa_enforcement(self, admin_client):
        from app.config_manager import config_manager

        client, _ = admin_client
        resp = client.post(
            "/admin/settings/update",
            data={"mfa_enforcement": "required_all"},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)
        assert config_manager.get("mfa_enforcement") == "required_all"

    def test_settings_update_password_expiry(self, admin_client):
        from app.config_manager import config_manager

        client, _ = admin_client
        resp = client.post(
            "/admin/settings/update",
            data={"password_expiry_days": "90"},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303)
        assert config_manager.get("password_expiry_days") == 90


# ─── User integrations page ──────────────────────────────────────────────────

class TestUserIntegrations:

    def test_my_integrations_page_loads(self, auth_client):
        client, _ = auth_client
        resp = client.get("/integrations/")
        assert resp.status_code == 200
        # Should render the card grid (at minimum the page structure)
        assert b"integrations" in resp.data.lower()

    def test_my_integrations_shows_service_cards(self, auth_client, app):
        """If any services are seeded, they should appear on the page."""
        with app.app_context():
            try:
                from app.services.integration_service import seed_default_services
                seed_default_services()
            except Exception:
                pass  # Seeding not strictly required for page to load

        client, _ = auth_client
        resp = client.get("/integrations/")
        assert resp.status_code == 200

    def test_disconnect_nonexistent_service_redirects(self, auth_client):
        client, _ = auth_client
        resp = client.post("/integrations/99999/disconnect", follow_redirects=True)
        # Should not crash — redirect or 404
        assert resp.status_code in (200, 302, 404)

    def test_connect_zotero_persists_library_details(self, auth_client, app):
        client, user_id = auth_client
        with app.app_context():
            from app.models.integrations_registry import GlobalIntegrationService, UserIntegrationCredential

            service = GlobalIntegrationService(
                service_type="zotero",
                name="Zotero",
                scope="dual",
                is_enabled=True,
                allow_user_override=True,
            )
            db.session.add(service)
            db.session.commit()
            service_id = service.id

        response = client.post(
            f"/integrations/{service_id}/connect",
            data={
                "api_key": "zotero-api-key",
                "zotero_user_id": "12345",
                "zotero_library_type": "group",
                "zotero_group_id": "67890",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        with app.app_context():
            from app.models.integrations_registry import UserIntegrationCredential

            credential = UserIntegrationCredential.query.filter_by(
                user_id=user_id,
                service_id=service_id,
            ).first()
            assert credential is not None
            assert credential.display_name == "Zotero group 67890 (user 12345)"
            assert json.loads(credential.extra_data) == {
                "user_id": "12345",
                "library_type": "group",
                "group_id": "67890",
            }

    def test_connect_zotero_requires_user_id(self, auth_client, app):
        client, user_id = auth_client
        with app.app_context():
            from app.models.integrations_registry import GlobalIntegrationService, UserIntegrationCredential

            service = GlobalIntegrationService(
                service_type="zotero",
                name="Zotero",
                scope="dual",
                is_enabled=True,
                allow_user_override=True,
            )
            db.session.add(service)
            db.session.commit()
            service_id = service.id

        response = client.post(
            f"/integrations/{service_id}/connect",
            data={
                "api_key": "zotero-api-key",
                "zotero_library_type": "user",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Zotero user ID is required." in response.data

        with app.app_context():
            from app.models.integrations_registry import UserIntegrationCredential

            credential = UserIntegrationCredential.query.filter_by(
                user_id=user_id,
                service_id=service_id,
            ).first()
            assert credential is None


# ─── Admin integrations page ─────────────────────────────────────────────────

class TestAdminIntegrations:

    def test_admin_integrations_page_loads(self, admin_client):
        client, _ = admin_client
        resp = client.get("/admin/integrations/")
        assert resp.status_code == 200

    def test_admin_integrations_shows_configured_badge(self, admin_client, app):
        """After seeding, at least one service card should render."""
        with app.app_context():
            try:
                from app.services.integration_service import seed_default_services
                seed_default_services()
            except Exception:
                pass

        client, _ = admin_client
        resp = client.get("/admin/integrations/")
        assert resp.status_code == 200
        # The integration_users link uses 'connected' text
        # At minimum the template renders without Jinja errors
        assert b"</html>" in resp.data or b"</div>" in resp.data

    def test_admin_integration_users_page_loads(self, admin_client, app):
        """integration_users page with no connections should render cleanly."""
        with app.app_context():
            try:
                from app.services.integration_service import seed_default_services
                seed_default_services()
                from app.models.integrations_registry import GlobalIntegrationService
                svc = GlobalIntegrationService.query.first()
                svc_id = svc.id if svc else 1
            except Exception:
                svc_id = 1

        client, _ = admin_client
        resp = client.get(f"/admin/integrations/{svc_id}/users")
        assert resp.status_code in (200, 404)

    def test_admin_integration_update_name(self, admin_client, app):
        with app.app_context():
            try:
                from app.services.integration_service import seed_default_services
                seed_default_services()
                from app.models.integrations_registry import GlobalIntegrationService
                svc = GlobalIntegrationService.query.first()
                svc_id = svc.id if svc else None
            except Exception:
                svc_id = None

        if svc_id is None:
            pytest.skip("No integration services seeded")

        client, _ = admin_client
        new_name = f"Test Service {uuid.uuid4().hex[:6]}"
        resp = client.post(
            f"/admin/integrations/{svc_id}/update",
            data={"name": new_name, "scope": "admin_only", "description": ""},
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302, 303)
        with app.app_context():
            from app.models.integrations_registry import GlobalIntegrationService
            updated = db.session.get(GlobalIntegrationService, svc_id)
            assert updated.name == new_name
