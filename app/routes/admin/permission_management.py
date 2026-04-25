"""Plugin permission management routes (Phase 4.1)."""
from flask import Blueprint, request, jsonify, g
from datetime import timedelta
from app.core.time_utils import utcnow_naive
from app.decorators.auth import admin_required
from app.decorators.plugin_permissions import log_plugin_action
from app.services.plugin_permissions import PluginPermissionService
from app.models.researcher.plugin_permissions import AccessLevel

permission_bp = Blueprint('permission_management', __name__, url_prefix='/api/admin/permissions')


@permission_bp.route('/grant', methods=['POST'])
@admin_required
@log_plugin_action('grant_permission')
def grant_permission():
    """Grant role-based permissions for a plugin.
    
    Request body:
    {
        "plugin_id": 1,
        "role_id": 2,
        "can_execute": true,
        "can_configure": false,
        "can_view_logs": true,
        "can_test": true
    }
    """
    try:
        data = request.get_json() or {}
        
        plugin_id = data.get('plugin_id')
        role_id = data.get('role_id')
        
        if not plugin_id or not role_id:
            return jsonify({'error': 'Missing required fields: plugin_id, role_id'}), 400
        
        success, message, permission = PluginPermissionService.grant_permission(
            plugin_id=plugin_id,
            role_id=role_id,
            can_execute=data.get('can_execute', False),
            can_configure=data.get('can_configure', False),
            can_view_logs=data.get('can_view_logs', False),
            can_test=data.get('can_test', False),
            created_by=g.user_id
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'permission': permission.to_dict() if permission else None
            }), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error granting permission: {str(e)}'}), 500


@permission_bp.route('/revoke', methods=['POST'])
@admin_required
@log_plugin_action('revoke_permission')
def revoke_permission():
    """Revoke role-based permissions for a plugin.
    
    Request body:
    {
        "plugin_id": 1,
        "role_id": 2
    }
    """
    try:
        data = request.get_json() or {}
        
        plugin_id = data.get('plugin_id')
        role_id = data.get('role_id')
        
        if not plugin_id or not role_id:
            return jsonify({'error': 'Missing required fields: plugin_id, role_id'}), 400
        
        success, message = PluginPermissionService.revoke_permission(plugin_id, role_id)
        
        if success:
            return jsonify({'success': True, 'message': message}), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error revoking permission: {str(e)}'}), 500


@permission_bp.route('/assign-user', methods=['POST'])
@admin_required
@log_plugin_action('assign_user_access')
def assign_user_access():
    """Assign direct plugin access to a user (overrides role-based permissions).
    
    Request body:
    {
        "user_id": 5,
        "plugin_id": 1,
        "access_level": "EXECUTE",  # NONE, READ, EXECUTE, CONFIGURE, ADMIN
        "reason": "Clinical trial researcher",
        "days_until_expiry": 30
    }
    """
    try:
        data = request.get_json() or {}
        
        user_id = data.get('user_id')
        plugin_id = data.get('plugin_id')
        access_level_str = data.get('access_level', 'EXECUTE')
        reason = data.get('reason')
        days = data.get('days_until_expiry')
        
        if not user_id or not plugin_id:
            return jsonify({'error': 'Missing required fields: user_id, plugin_id'}), 400
        
        # Convert access level string to enum
        try:
            access_level = AccessLevel[access_level_str]
        except KeyError:
            return jsonify({'error': f'Invalid access level: {access_level_str}'}), 400
        
        # Calculate expiry date if provided
        expiry_date = None
        if days:
            expiry_date = utcnow_naive() + timedelta(days=days)
        
        success, message, assignment = PluginPermissionService.assign_user_access(
            user_id=user_id,
            plugin_id=plugin_id,
            access_level=access_level,
            reason=reason,
            expiry_date=expiry_date,
            assigned_by=g.user_id
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'assignment': assignment.to_dict() if assignment else None
            }), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error assigning access: {str(e)}'}), 500


@permission_bp.route('/revoke-user', methods=['POST'])
@admin_required
@log_plugin_action('revoke_user_access')
def revoke_user_access():
    """Revoke direct plugin access from a user.
    
    Request body:
    {
        "user_id": 5,
        "plugin_id": 1
    }
    """
    try:
        data = request.get_json() or {}
        
        user_id = data.get('user_id')
        plugin_id = data.get('plugin_id')
        
        if not user_id or not plugin_id:
            return jsonify({'error': 'Missing required fields: user_id, plugin_id'}), 400
        
        success, message = PluginPermissionService.revoke_user_access(user_id, plugin_id)
        
        if success:
            return jsonify({'success': True, 'message': message}), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error revoking access: {str(e)}'}), 500


@permission_bp.route('/check/<int:user_id>/<int:plugin_id>', methods=['GET'])
@admin_required
def check_user_access(user_id: int, plugin_id: int):
    """Check user access for a plugin.
    
    Query parameters:
    - action: execute, configure, test, view_logs (default: execute)
    """
    try:
        action = request.args.get('action', 'execute')
        
        has_access, message, access_level = PluginPermissionService.check_user_access(
            user_id, plugin_id, action
        )
        
        return jsonify({
            'has_access': has_access,
            'message': message,
            'access_level': access_level.name,
            'required_action': action
        }), 200
    
    except Exception as e:
        return jsonify({'error': f'Error checking access: {str(e)}'}), 500


@permission_bp.route('/user-plugins/<int:user_id>', methods=['GET'])
@admin_required
def get_user_plugins(user_id: int):
    """Get all plugins accessible to a user, grouped by access level."""
    try:
        plugins = PluginPermissionService.get_user_plugins(user_id)
        
        if 'error' in plugins:
            return jsonify(plugins), 400
        
        return jsonify({
            'success': True,
            'user_id': user_id,
            'plugins': plugins
        }), 200
    
    except Exception as e:
        return jsonify({'error': f'Error fetching plugins: {str(e)}'}), 500


@permission_bp.route('/plugin-users/<int:plugin_id>', methods=['GET'])
@admin_required
def get_plugin_users(plugin_id: int):
    """Get all users with access to a plugin."""
    try:
        success, message, users_data = PluginPermissionService.get_plugin_users(plugin_id)
        
        if success:
            return jsonify({
                'success': True,
                'plugin_id': plugin_id,
                'users': users_data
            }), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error fetching users: {str(e)}'}), 500


@permission_bp.route('/audit-logs', methods=['GET'])
@admin_required
def get_audit_logs():
    """Get plugin audit logs with optional filtering.
    
    Query parameters:
    - plugin_id: Filter by plugin
    - user_id: Filter by user
    - action: Filter by action type
    - days: Include logs from last N days (default: 30)
    - limit: Maximum results (default: 100)
    - offset: Pagination offset (default: 0)
    """
    try:
        plugin_id = request.args.get('plugin_id', type=int)
        user_id = request.args.get('user_id', type=int)
        action = request.args.get('action')
        days = request.args.get('days', 30, type=int)
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        # Validate limits
        limit = min(limit, 500)  # Max 500 results
        offset = max(offset, 0)
        
        success, message, logs = PluginPermissionService.get_audit_logs(
            plugin_id=plugin_id,
            user_id=user_id,
            action=action,
            days=days,
            limit=limit,
            offset=offset
        )
        
        if success:
            return jsonify({
                'success': True,
                'logs': logs,
                'count': len(logs),
                'limit': limit,
                'offset': offset
            }), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error fetching audit logs: {str(e)}'}), 500


@permission_bp.route('/cleanup-expired', methods=['POST'])
@admin_required
@log_plugin_action('cleanup_expired_assignments')
def cleanup_expired_assignments():
    """Clean up expired user access assignments."""
    try:
        success, message, deleted_count = PluginPermissionService.cleanup_expired_assignments()
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'deleted_count': deleted_count
            }), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error cleaning up assignments: {str(e)}'}), 500


@permission_bp.route('/summary/<int:plugin_id>', methods=['GET'])
@admin_required
def get_permission_summary(plugin_id: int):
    """Get a summary of all permissions for a plugin."""
    try:
        success, message, summary = PluginPermissionService.get_permission_summary(plugin_id)
        
        if success:
            return jsonify({
                'success': True,
                'summary': summary
            }), 200
        else:
            return jsonify({'error': message}), 400
    
    except Exception as e:
        return jsonify({'error': f'Error getting permission summary: {str(e)}'}), 500
