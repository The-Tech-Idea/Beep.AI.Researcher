"""Admin routes for RBAC role management."""

from datetime import datetime, UTC
from functools import wraps

from flask import Blueprint, jsonify, request

from app.database import db
from app.decorators.permissions import require_permission
from app.models.rbac import RBACRole, UserRole

role_admin_bp = Blueprint("role_admin", __name__, url_prefix="/admin/roles")


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


def _role_payload(role: RBACRole) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "permissions": role.permissions or [],
        "is_builtin": bool(role.is_builtin),
        "created_at": role.created_at.isoformat() if role.created_at else None,
        "updated_at": role.updated_at.isoformat() if role.updated_at else None,
    }


@role_admin_bp.route("", methods=["GET"])
@require_user_header
def list_roles():
    roles = RBACRole.query.order_by(RBACRole.name).all()
    return jsonify({"success": True, "count": len(roles), "roles": [_role_payload(r) for r in roles]}), 200


@role_admin_bp.route("", methods=["POST"])
@require_permission("admin:roles")
def create_role():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Validation Failed", "message": "Role name is required"}), 400

    if RBACRole.query.filter_by(name=name).first():
        return jsonify({"error": "Conflict", "message": f"Role '{name}' already exists"}), 409

    permissions = data.get("permissions", [])
    if not isinstance(permissions, list):
        return jsonify({"error": "Validation Failed", "message": "permissions must be an array"}), 400

    role = RBACRole(
        name=name,
        description=data.get("description") or "",
        permissions=permissions,
        is_builtin=False,
        created_by=request.headers.get("X-User-ID"),
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    db.session.add(role)
    db.session.commit()
    return jsonify({"success": True, "message": f"Created role '{role.name}'", "role": _role_payload(role)}), 201


@role_admin_bp.route("/<role_id>", methods=["GET"])
@require_user_header
def get_role(role_id):
    role = db.session.get(RBACRole, role_id)
    if not role:
        return jsonify({"error": "Not Found", "message": f"Role '{role_id}' not found"}), 404
    return jsonify({"success": True, "role": _role_payload(role)}), 200


@role_admin_bp.route("/<role_id>", methods=["PUT"])
@require_permission("admin:roles")
def update_role(role_id):
    role = db.session.get(RBACRole, role_id)
    if not role:
        return jsonify({"error": "Not Found", "message": f"Role '{role_id}' not found"}), 404
    if role.is_builtin:
        return jsonify({"error": "Forbidden", "message": "Cannot modify built-in roles"}), 403

    data = request.get_json() or {}
    if "permissions" in data:
        if not isinstance(data["permissions"], list):
            return jsonify({"error": "Validation Failed", "message": "permissions must be an array"}), 400
        role.permissions = data["permissions"]
    if "description" in data:
        role.description = data["description"]
    role.updated_at = _utcnow()
    db.session.commit()
    return jsonify({"success": True, "message": f"Updated role '{role.name}'", "role": _role_payload(role)}), 200


@role_admin_bp.route("/<role_id>", methods=["DELETE"])
@require_permission("admin:roles")
def delete_role(role_id):
    role = db.session.get(RBACRole, role_id)
    if not role:
        return jsonify({"error": "Not Found", "message": f"Role '{role_id}' not found"}), 404
    if role.is_builtin:
        return jsonify({"error": "Forbidden", "message": "Cannot delete built-in roles"}), 403

    user_count = UserRole.query.filter_by(role_id=role_id).count()
    if user_count > 0:
        return jsonify({"error": "Conflict", "message": f"{user_count} users have this role. Revoke assignments first."}), 409

    db.session.delete(role)
    db.session.commit()
    return jsonify({"success": True, "message": f"Deleted role '{role.name}'"}), 200
