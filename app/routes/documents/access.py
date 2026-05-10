"""Document Access Control Routes - Phase 1.8.

Provides endpoints for:
- Getting document access settings
- Updating access levels (private, shared, group, public)
- Sharing documents with users and groups
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, UTC
import uuid

from app.database import db
from app.models.rbac import DocumentAccess, AccessLevel
from app.decorators.permissions import require_document_access, require_permission

doc_access_bp = Blueprint(
    "document_access", __name__, url_prefix="/documents/<doc_id>/access"
)


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


@doc_access_bp.route("", methods=["GET"])
@require_document_access("read")
def get_document_access(doc_id):
    """Get document access settings.

    Args:
        doc_id: Document ID

    Returns:
        Access control settings for document
    """
    access = DocumentAccess.query.filter_by(document_id=doc_id).first()

    if not access:
        return jsonify(
            {
                "error": "Not Found",
                "message": f"Access settings not found for document '{doc_id}'",
            }
        ), 404

    return jsonify(
        {
            "success": True,
            "access": {
                "document_id": access.document_id,
                "owner_id": access.owner_id,
                "access_level": access.access_level,
                "shared_with": access.shared_with,
                "default_permissions": access.default_permissions,
                "created_at": access.created_at.isoformat()
                if access.created_at
                else None,
                "updated_at": access.updated_at.isoformat()
                if access.updated_at
                else None,
            },
        }
    ), 200


@doc_access_bp.route("", methods=["PUT"])
@require_document_access("write")
def update_document_access(doc_id):
    """Update document access settings.

    Args:
        doc_id: Document ID

    Request body:
        - access_level (str, optional): private, group, shared, public
        - shared_with (dict, optional): {groups: [], users: []}
        - default_permissions (list, optional): ['read'] or ['read', 'write']

    Returns:
        Updated access settings
    """
    access = DocumentAccess.query.filter_by(document_id=doc_id).first()

    if not access:
        return jsonify(
            {
                "error": "Not Found",
                "message": f"Access settings not found for document '{doc_id}'",
            }
        ), 404

    user_id = request.headers.get("X-User-ID")
    if access.owner_id != user_id:
        return jsonify(
            {
                "error": "Forbidden",
                "message": "Only document owner can change access settings",
            }
        ), 403

    data = request.get_json() or {}

    # Update access level
    if "access_level" in data:
        valid_levels = [e.value for e in AccessLevel]
        if data["access_level"] not in valid_levels:
            return jsonify(
                {
                    "error": "Validation Failed",
                    "message": f"Invalid access_level. Must be one of: {', '.join(valid_levels)}",
                }
            ), 400
        access.access_level = data["access_level"]

    # Update shared_with
    if "shared_with" in data:
        access.shared_with = data["shared_with"]

    # Update default permissions
    if "default_permissions" in data:
        access.default_permissions = data["default_permissions"]

    access.updated_at = _utcnow()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to update document access"}), 500

    return jsonify(
        {
            "success": True,
            "message": "Document access updated",
            "access": {
                "access_level": access.access_level,
                "shared_with": access.shared_with,
                "default_permissions": access.default_permissions,
            },
        }
    ), 200


@doc_access_bp.route("/share-user", methods=["POST"])
@require_document_access("write")
def share_document_with_user(doc_id):
    """Share document with specific user.

    Args:
        doc_id: Document ID

    Request body:
        - user_id (str): User to share with
        - permissions (list, optional): ['read'] or ['read', 'write']

    Returns:
        Updated access settings
    """
    access = DocumentAccess.query.filter_by(document_id=doc_id).first()

    if not access:
        return jsonify(
            {
                "error": "Not Found",
                "message": f"Access settings not found for document '{doc_id}'",
            }
        ), 404

    user_id = request.headers.get("X-User-ID")
    if access.owner_id != user_id:
        return jsonify(
            {"error": "Forbidden", "message": "Only document owner can share"}
        ), 403

    data = request.get_json() or {}
    target_user = data.get("user_id")

    if not target_user:
        return jsonify(
            {"error": "Validation Failed", "message": "user_id is required"}
        ), 400

    permissions = data.get("permissions", ["read"])

    # Add user to shared_with
    access.share_with_user(target_user, permissions)
    access.updated_at = _utcnow()

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to share document with user"}), 500

    return jsonify(
        {
            "success": True,
            "message": f"Shared with user '{target_user}'",
            "access": {
                "access_level": access.access_level,
                "shared_with": access.shared_with,
            },
        }
    ), 200


@doc_access_bp.route("/share-group", methods=["POST"])
@require_document_access("write")
def share_document_with_group(doc_id):
    """Share document with group.

    Args:
        doc_id: Document ID

    Request body:
        - group_id (str): Group to share with
        - permissions (list, optional): ['read'] or ['read', 'write']

    Returns:
        Updated access settings
    """
    access = DocumentAccess.query.filter_by(document_id=doc_id).first()

    if not access:
        return jsonify(
            {
                "error": "Not Found",
                "message": f"Access settings not found for document '{doc_id}'",
            }
        ), 404

    user_id = request.headers.get("X-User-ID")
    if access.owner_id != user_id:
        return jsonify(
            {"error": "Forbidden", "message": "Only document owner can share"}
        ), 403

    data = request.get_json() or {}
    group_id = data.get("group_id")

    if not group_id:
        return jsonify(
            {"error": "Validation Failed", "message": "group_id is required"}
        ), 400

    permissions = data.get("permissions", ["read"])

    # Add group to shared_with
    access.share_with_group(group_id, permissions)
    access.updated_at = _utcnow()

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to share document with group"}), 500

    return jsonify(
        {
            "success": True,
            "message": f"Shared with group '{group_id}'",
            "access": {
                "access_level": access.access_level,
                "shared_with": access.shared_with,
            },
        }
    ), 200


@doc_access_bp.route("/unshare-user", methods=["POST"])
@require_document_access("write")
def unshare_document_with_user(doc_id):
    """Remove document sharing with specific user.

    Args:
        doc_id: Document ID

    Request body:
        - user_id (str): User to remove sharing from

    Returns:
        Updated access settings
    """
    access = DocumentAccess.query.filter_by(document_id=doc_id).first()

    if not access:
        return jsonify(
            {
                "error": "Not Found",
                "message": f"Access settings not found for document '{doc_id}'",
            }
        ), 404

    user_id = request.headers.get("X-User-ID")
    if access.owner_id != user_id:
        return jsonify(
            {"error": "Forbidden", "message": "Only document owner can change sharing"}
        ), 403

    data = request.get_json() or {}
    target_user = data.get("user_id")

    if not target_user:
        return jsonify(
            {"error": "Validation Failed", "message": "user_id is required"}
        ), 400

    access.unshare_with_user(target_user)
    access.updated_at = _utcnow()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to remove document sharing"}), 500

    return jsonify(
        {"success": True, "message": f"Removed sharing with user '{target_user}'"}
    ), 200


@doc_access_bp.route("/make-private", methods=["POST"])
@require_document_access("write")
def make_document_private(doc_id):
    """Make document private (owner only).

    Args:
        doc_id: Document ID

    Returns:
        Updated access (now private)
    """
    access = DocumentAccess.query.filter_by(document_id=doc_id).first()

    if not access:
        return jsonify(
            {
                "error": "Not Found",
                "message": f"Access settings not found for document '{doc_id}'",
            }
        ), 404

    user_id = request.headers.get("X-User-ID")
    if access.owner_id != user_id:
        return jsonify(
            {"error": "Forbidden", "message": "Only document owner can change access"}
        ), 403

    access.make_private()
    access.updated_at = _utcnow()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to make document private"}), 500

    return jsonify(
        {
            "success": True,
            "message": "Document is now private (owner only)",
            "access": {
                "access_level": access.access_level,
                "shared_with": access.shared_with,
            },
        }
    ), 200


@doc_access_bp.route("/make-public", methods=["POST"])
@require_document_access("write")
def make_document_public(doc_id):
    """Make document public (everyone in tenant).

    Args:
        doc_id: Document ID

    Returns:
        Updated access (now public)
    """
    access = DocumentAccess.query.filter_by(document_id=doc_id).first()

    if not access:
        return jsonify(
            {
                "error": "Not Found",
                "message": f"Access settings not found for document '{doc_id}'",
            }
        ), 404

    user_id = request.headers.get("X-User-ID")
    if access.owner_id != user_id:
        return jsonify(
            {"error": "Forbidden", "message": "Only document owner can change access"}
        ), 403

    access.make_public()
    access.updated_at = _utcnow()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to make document public"}), 500

    return jsonify(
        {
            "success": True,
            "message": "Document is now public",
            "access": {
                "access_level": access.access_level,
                "default_permissions": access.default_permissions,
            },
        }
    ), 200
