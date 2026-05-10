"""Shared auth decorators for API routes."""

from functools import wraps

from flask import g, jsonify
from flask_login import current_user, login_required


def admin_required(f):
    """Require an authenticated admin user; return JSON 401/403 on failure."""

    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required."}), 401
        if not getattr(current_user, "is_admin", False):
            return jsonify({"error": "Admin access required."}), 403
        g.user_id = current_user.id
        return f(*args, **kwargs)

    return decorated_function
