"""Permission Decorators for RBAC - Phase 1.8.

Provides decorators to protect routes with permission checks.
"""

from functools import wraps
from flask import request, jsonify, current_app
from flask_login import current_user
from app.services.permission_service import PermissionService


def _is_admin_request() -> bool:
    """Detect admin endpoints where RBAC must remain enforced."""
    path = (request.path or "").lower()
    endpoint = (request.endpoint or "").lower()
    blueprint = (request.blueprint or "").lower()

    if path.startswith("/admin/") or path.startswith("/api/admin/"):
        return True

    if endpoint.startswith("admin") or endpoint.startswith("role_admin.") or endpoint.startswith("user_role_admin."):
        return True

    if blueprint.startswith("admin") or blueprint in {"role_admin", "user_role_admin"}:
        return True

    return False


def require_permission(permission: str, scope: str = 'global'):
    """Decorator to require specific permission before executing route.
    
    Usage:
        @app.route('/admin/roles')
        @require_permission('admin:roles')
        def manage_roles():
            ...
        
        @app.route('/projects/<int:project_id>/documents')
        @require_permission('project:write', scope='project')
        def upload_document(project_id):
            ...
    
    Args:
        permission: Permission string (e.g., 'document:write', 'project:write')
        scope: 'global' or 'project' - if 'project', will extract project_id from kwargs
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Authenticated users get full access on non-admin routes.
            # Admin routes continue to use RBAC permission checks.
            if current_user.is_authenticated and not _is_admin_request():
                return f(*args, **kwargs)

            user_id = request.headers.get('X-User-ID')
            admin_path = _is_admin_request()
            if not user_id and not admin_path and current_user.is_authenticated:
                user_id = str(current_user.id)
            
            if not user_id:
                return jsonify({
                    'error': 'Unauthorized',
                    'message': 'X-User-ID header required'
                }), 401
            
            scope_id = None
            if scope == 'project':
                # Extract project_id from route kwargs
                scope_id = kwargs.get('project_id')

            if not PermissionService.user_has_permission(user_id, permission, scope, scope_id):
                return jsonify({
                    'error': 'Forbidden',
                    'message': f'Missing permission: {permission}'
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def require_document_access(access_type: str = 'read'):
    """Decorator to require document access before executing route.
    
    Checks if user has read or write access to document.
    
    Usage:
        @app.route('/documents/<doc_id>')
        @require_document_access('read')
        def get_document(doc_id):
            ...
    
    Args:
        access_type: 'read' or 'write'
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.is_authenticated and not _is_admin_request():
                return f(*args, **kwargs)

            user_id = request.headers.get('X-User-ID')
            if not user_id and current_user.is_authenticated:
                user_id = str(current_user.id)
            
            if not user_id:
                return jsonify({
                    'error': 'Unauthorized',
                    'message': 'X-User-ID header required'
                }), 401
            
            # Get document_id from kwargs (could be doc_id, document_id, or id)
            document_id = (
                kwargs.get('doc_id') or
                kwargs.get('document_id') or
                kwargs.get('id') or
                request.args.get('document_id')
            )
            
            if not document_id:
                return jsonify({
                    'error': 'Bad Request',
                    'message': 'Document ID required'
                }), 400
            
            # Check access
            if access_type == 'read':
                can_access = PermissionService.can_access_document(user_id, document_id)
            elif access_type == 'write':
                can_access = PermissionService.can_write_document(user_id, document_id)
            else:
                can_access = False
            
            if not can_access:
                return jsonify({
                    'error': 'Forbidden',
                    'message': f'No {access_type} access to document'
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def require_owner(resource_field: str = 'owner_id', user_field: str = 'X-User-ID'):
    """Decorator to require user to be owner of resource.
    
    Usage:
        @app.route('/documents/<doc_id>', methods=['DELETE'])
        @require_owner('owner_id')
        def delete_document(doc_id):
            ...
    
    Args:
        resource_field: Field name in request JSON containing owner_id
        user_field: Header field containing user_id
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = request.headers.get(user_field)
            
            if not user_id:
                return jsonify({
                    'error': 'Unauthorized',
                    'message': f'{user_field} header required'
                }), 401
            
            data = request.get_json() or {}
            owner_id = data.get(resource_field)
            
            if not owner_id:
                return jsonify({
                    'error': 'Bad Request',
                    'message': f'{resource_field} required in request body'
                }), 400
            
            if owner_id != user_id:
                return jsonify({
                    'error': 'Forbidden',
                    'message': 'Only owner can perform this action'
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator
