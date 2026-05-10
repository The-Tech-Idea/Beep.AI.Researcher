"""Admin API connection-status and infrastructure self-test routes."""

import uuid

from flask import jsonify
from flask_login import login_required

from app.config_manager import config_manager
from app.routes.admin_routes import admin_bp, admin_required


def _connection_result_payload(ok, result):
    """Shape Researcher connectivity checks as explicit JSON objects."""
    if ok:
        payload = result if isinstance(result, dict) else {"result": result}
        payload.setdefault("success", True)
        return payload
    return {
        "success": False,
        "error": result,
    }


@admin_bp.route("/api/connection/status")
@login_required
@admin_required
def api_connection_status():
    """Get full connection status to Beep.AI.Server."""
    from app.services.beep_ai_client import get_connection_status

    status = get_connection_status()
    return jsonify(status)


@admin_bp.route("/api/connection/check-token")
@login_required
@admin_required
def api_check_token():
    """Check if the configured API token is valid."""
    from app.services.beep_ai_client import check_token

    ok, result = check_token()
    return jsonify(_connection_result_payload(ok, result))


@admin_bp.route("/api/connection/health")
@login_required
@admin_required
def api_check_health():
    """Check if Beep.AI.Server is reachable."""
    from app.services.beep_ai_client import check_health

    ok, result = check_health()
    return jsonify(_connection_result_payload(ok, result))


@admin_bp.route("/api/storage/test", methods=["POST"])
@login_required
@admin_required
def api_storage_test():
    """Test the currently configured storage backend."""
    from app.services.storage import get_storage_backend, reset_backend, StorageError

    try:
        reset_backend()
        backend = get_storage_backend()
        test_key = f"_healthcheck/{uuid.uuid4().hex}.txt"
        test_data = b"beep-storage-healthcheck"
        backend.save(test_key, test_data, "text/plain")
        backend.delete(test_key)
        backend_name = config_manager.get("storage_backend") or "local"
        return jsonify(
            {
                "success": True,
                "message": f'Storage backend "{backend_name}" is operational ✓',
            }
        )
    except StorageError as exc:
        return jsonify({"success": False, "message": f"Storage error: {exc}"})
    except Exception as exc:
        return jsonify({"success": False, "message": f"Unexpected error: {exc}"})


@admin_bp.route("/api/email/test", methods=["POST"])
@login_required
@admin_required
def api_email_test():
    """Send a test email to the currently logged-in admin."""
    from flask_login import current_user
    from app.services.email_service import send_email, is_configured

    if not is_configured():
        return jsonify(
            {
                "success": False,
                "message": "Email is not configured. Check the Email tab in Settings.",
            }
        )

    recipient = current_user.email
    if not recipient:
        return jsonify(
            {"success": False, "message": "Your account has no email address set."}
        )

    ok, err = send_email(
        subject="[Beep.AI.Researcher] Admin test email",
        body=(
            f"This is a test email sent from Beep.AI.Researcher admin settings.\n\n"
            f"Recipient: {recipient}"
        ),
        recipients=[recipient],
    )
    if ok:
        return jsonify(
            {"success": True, "message": f"Test email sent to {recipient} ✓"}
        )
    else:
        return jsonify({"success": False, "message": f"Send failed: {err}"})
