"""Permission decorators for plugin access control (Phase 4.1)."""
from functools import wraps
from flask import request, jsonify, g
from datetime import datetime
from app.core.time_utils import utcnow_naive
from app.models.researcher.plugin_permissions import (
    AccessLevel, PluginAudit, get_user_plugin_access_level
)
from app.models.researcher.plugins import Plugin
from app.database import db


def plugin_access_required(action: str = 'execute', access_level: AccessLevel = AccessLevel.EXECUTE):
    """Decorator to enforce plugin access control.
    
    Args:
        action: The action being performed (execute, configure, test, view_logs)
        access_level: Minimum required access level
    
    Usage:
        @plugin_access_required('execute', AccessLevel.EXECUTE)
        def execute_plugin(plugin_id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get user from g (set by auth middleware)
            user_id = getattr(g, 'user_id', None)
            if not user_id:
                return jsonify({'error': 'Unauthorized'}), 401
            
            # Get plugin_id from kwargs or request
            plugin_id = kwargs.get('plugin_id')
            if not plugin_id:
                # Try to get from JSON body
                data = request.get_json() or {}
                plugin_id = data.get('plugin_id')
            
            if not plugin_id:
                return jsonify({'error': 'No plugin_id provided'}), 400
            
            # Check if plugin exists
            plugin = Plugin.query.get(plugin_id)
            if not plugin:
                return jsonify({'error': f'Plugin {plugin_id} not found'}), 404
            
            # Check access level
            user_access = get_user_plugin_access_level(user_id, plugin_id)
            
            if user_access < access_level:
                _log_audit(
                    plugin_id=plugin_id,
                    user_id=user_id,
                    action=action,
                    success=False,
                    error_message=f'Insufficient permissions. Required: {access_level.name}, Got: {user_access.name}'
                )
                return jsonify({
                    'error': 'Access denied',
                    'message': f'Insufficient permissions for action: {action}',
                    'required_access': access_level.name,
                    'current_access': user_access.name
                }), 403
            
            # Store plugin and user info in g for potential use in the view
            g.plugin_id = plugin_id
            g.plugin = plugin
            g.user_plugin_access = user_access
            
            # Execute the view function
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def log_plugin_action(action: str):
    """Decorator to log plugin actions in audit trail.
    
    Usage:
        @log_plugin_action('execute')
        def execute_plugin(plugin_id):
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = getattr(g, 'user_id', None)
            plugin_id = getattr(g, 'plugin_id', None) or kwargs.get('plugin_id')
            
            start_time = utcnow_naive()
            
            try:
                result = f(*args, **kwargs)
                
                execution_time_ms = (utcnow_naive() - start_time).total_seconds() * 1000
                
                # Determine success from response
                success = True
                error_message = None
                if isinstance(result, tuple) and len(result) > 1:
                    status_code = result[1]
                    success = status_code < 400
                    if not success and isinstance(result[0], dict):
                        error_message = result[0].get('error')
                
                _log_audit(
                    plugin_id=plugin_id,
                    user_id=user_id,
                    action=action,
                    success=success,
                    error_message=error_message,
                    execution_time_ms=execution_time_ms,
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent', '')[:500]
                )
                
                return result
            except Exception as e:
                execution_time_ms = (utcnow_naive() - start_time).total_seconds() * 1000
                _log_audit(
                    plugin_id=plugin_id,
                    user_id=user_id,
                    action=action,
                    success=False,
                    error_message=str(e)[:500],
                    execution_time_ms=execution_time_ms,
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent', '')[:500]
                )
                raise
        
        return decorated_function
    return decorator


def admin_check_permission(f):
    """Decorator to verify user is admin and has permission management rights."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = getattr(g, 'user_id', None)
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        
        # Check if user is admin (assuming admin_required sets g.is_admin)
        is_admin = getattr(g, 'is_admin', False)
        if not is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        
        return f(*args, **kwargs)
    
    return decorated_function


def _log_audit(plugin_id: int, user_id: int, action: str, success: bool,
               error_message: str = None, execution_time_ms: float = None,
               ip_address: str = None, user_agent: str = None):
    """Internal function to log plugin actions to audit trail."""
    try:
        audit_log = PluginAudit(
            plugin_id=plugin_id,
            user_id=user_id,
            action=action,
            success=success,
            error_message=error_message,
            execution_time_ms=execution_time_ms,
            ip_address=ip_address or request.remote_addr,
            user_agent=user_agent or request.headers.get('User-Agent', '')[:500]
        )
        db.session.add(audit_log)
        db.session.commit()
    except Exception as e:
        # Log failures silently to not break the request
        print(f"Failed to log plugin audit: {e}")
        db.session.rollback()
