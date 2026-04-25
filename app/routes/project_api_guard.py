from __future__ import annotations

from functools import wraps

from flask import g, jsonify, request
from flask_login import current_user

from app.models.rbac import Permission
from app.models.researcher import ProjectMember, ResearchProject
from app.routes.route_entity_lookup import get_entity, get_entity_or_404
from app.services.permission_service import PermissionService


_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_ADMIN_PERMISSIONS = (
    Permission.ALL,
    Permission.ADMIN_SETTINGS,
    Permission.ADMIN_AUDIT,
)


def _json_error(error: str, message: str, status_code: int):
    return jsonify({"error": error, "message": message}), status_code


def _required_project_permission(*, write: bool) -> str:
    return Permission.PROJECT_WRITE if write else Permission.PROJECT_READ


def _has_global_permission(user_id: int | str, permission: str) -> bool:
    return PermissionService.user_has_global_permission(str(user_id), permission)


def _has_project_permission(user_id: int | str, project_id: int, permission: str) -> bool:
    return PermissionService.user_has_permission(str(user_id), permission, "project", project_id)


def current_user_is_session_admin() -> bool:
    if not current_user.is_authenticated:
        return False

    if getattr(current_user, "is_admin", False):
        return True

    return any(_has_global_permission(current_user.id, permission) for permission in _ADMIN_PERMISSIONS)


def current_user_can_access_project(project: ResearchProject, *, write: bool = False) -> bool:
    if not current_user.is_authenticated:
        return False

    if current_user_is_session_admin():
        return True

    user_id = int(current_user.id)
    permission = _required_project_permission(write=write)

    if project.owner_id == user_id:
        return True

    if _has_global_permission(user_id, Permission.ALL):
        return True

    if _has_global_permission(user_id, permission) or _has_project_permission(user_id, project.id, permission):
        return True

    membership = ProjectMember.query.filter_by(project_id=project.id, user_id=user_id).first()
    if membership is None:
        return False

    if not write:
        return True

    return (membership.role or "viewer").lower() in {"contributor", "admin"}


def ensure_project_session_access(project_id: int):
    if not current_user.is_authenticated:
        return _json_error("Unauthorized", "Authentication required", 401)

    project = get_entity(ResearchProject, project_id)
    if project is None:
        return _json_error("Not Found", "Project not found", 404)

    write = request.method not in _SAFE_METHODS
    if not current_user_can_access_project(project, write=write):
        return _json_error("Forbidden", "Project access denied", 403)

    g.current_project = project
    g.current_project_write_access = write
    return None


def get_guarded_project_or_404(project_id: int) -> ResearchProject:
    project = getattr(g, "current_project", None)
    if project is not None and int(project.id) == int(project_id):
        return project
    return get_entity_or_404(ResearchProject, project_id)


def ensure_admin_session():
    if not current_user.is_authenticated:
        return _json_error("Unauthorized", "Authentication required", 401)

    if not current_user_is_session_admin():
        return _json_error("Forbidden", "Administrator access required", 403)

    return None


def session_admin_required_json(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        response = ensure_admin_session()
        if response is not None:
            return response
        return func(*args, **kwargs)

    return wrapped


def guard_project_blueprint(blueprint, *, admin_endpoints: set[str] | None = None) -> None:
    protected_admin_endpoints = set(admin_endpoints or set())

    @blueprint.before_request
    def _enforce_guard():
        endpoint_name = (request.endpoint or "").rsplit(".", 1)[-1]
        if endpoint_name in protected_admin_endpoints:
            return ensure_admin_session()

        project_id = (request.view_args or {}).get("project_id")
        if project_id is None:
            return None

        return ensure_project_session_access(project_id)
