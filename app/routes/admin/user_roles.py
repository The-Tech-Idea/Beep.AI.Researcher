"""Admin routes for user role assignments."""

from datetime import datetime, timedelta, UTC
from functools import wraps

from flask import Blueprint, jsonify, request

from app.database import db
from app.decorators.permissions import require_permission
from app.models.rbac import RBACRole, UserRole

user_role_admin_bp = Blueprint("user_role_admin", __name__, url_prefix="/admin/users")


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


def require_user_header(f):
    """Require request user identity header for read-only admin endpoints."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not request.headers.get("X-User-ID"):
            return jsonify({"error": "Unauthorized", "message": "X-User-ID header is required"}), 401
        return f(*args, **kwargs)
    return wrapper


def _assignment_payload(assignment: UserRole) -> dict:
    role = db.session.get(RBACRole, assignment.role_id) if assignment.role_id else None
    return {
        "id": assignment.id,
        "user_id": assignment.user_id,
        "role_id": assignment.role_id,
        "role_name": role.name if role else None,
        "scope": assignment.scope,
        "scope_id": assignment.scope_id,
        "expires_at": assignment.expires_at.isoformat() if assignment.expires_at else None,
        "is_expired": assignment.is_expired(),
        "created_at": assignment.created_at.isoformat() if assignment.created_at else None,
        "created_by": assignment.created_by,
    }


@user_role_admin_bp.route("/<user_id>/roles", methods=["GET"])
@require_user_header
def get_user_roles(user_id):
    assignments = UserRole.query.filter_by(user_id=user_id).all()
    payload = [_assignment_payload(a) for a in assignments]
    return jsonify({"success": True, "user_id": user_id, "count": len(payload), "assignments": payload}), 200


@user_role_admin_bp.route("/<user_id>/roles", methods=["POST"])
@require_permission("admin:users")
def assign_role(user_id):
    data = request.get_json() or {}
    role_id = data.get("role_id")
    role = db.session.get(RBACRole, role_id)
    if not role:
        return jsonify({"error": "Not Found", "message": f"Role '{role_id}' not found"}), 404

    scope = (data.get("scope") or "global").strip()
    scope_id = data.get("scope_id")
    existing = UserRole.query.filter_by(user_id=user_id, role_id=role_id, scope=scope, scope_id=scope_id).first()
    if existing and not existing.is_expired():
        return jsonify({"error": "Conflict", "message": f"User '{user_id}' already has role '{role.name}' in scope '{scope}'"}), 409

    expires_at = None
    if data.get("expires_in_days") is not None:
        expires_at = _utcnow() + timedelta(days=int(data["expires_in_days"]))

    assignment = UserRole(
        user_id=user_id,
        role_id=role_id,
        scope=scope,
        scope_id=scope_id,
        expires_at=expires_at,
        created_by=request.headers.get("X-User-ID"),
        created_at=_utcnow(),
    )
    db.session.add(assignment)
    db.session.commit()
    return jsonify({"success": True, "message": f"Assigned '{role.name}' role to user '{user_id}'", "assignment": _assignment_payload(assignment)}), 201


@user_role_admin_bp.route("/<user_id>/roles/<role_id>", methods=["DELETE"])
@require_permission("admin:users")
def revoke_role(user_id, role_id):
    assignment = UserRole.query.filter_by(user_id=user_id, role_id=role_id).first()
    if not assignment:
        return jsonify({"error": "Not Found", "message": f"No role assignment found for user '{user_id}'"}), 404
    db.session.delete(assignment)
    db.session.commit()
    return jsonify({"success": True, "message": f"Revoked role '{role_id}' from user '{user_id}'"}), 200


@user_role_admin_bp.route("/<user_id>/roles/<assignment_id>", methods=["PUT"])
@require_permission("admin:users")
def update_role_assignment(user_id, assignment_id):
    assignment = UserRole.query.filter_by(id=assignment_id, user_id=user_id).first()
    if not assignment:
        return jsonify({"error": "Not Found", "message": f"Role assignment '{assignment_id}' not found"}), 404

    data = request.get_json() or {}
    if "expires_in_days" in data:
        if data["expires_in_days"] is None:
            assignment.expires_at = None
        else:
            assignment.expires_at = _utcnow() + timedelta(days=int(data["expires_in_days"]))
    db.session.commit()
    return jsonify({"success": True, "message": "Updated role assignment", "assignment": _assignment_payload(assignment)}), 200
