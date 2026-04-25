"""Plugin management admin routes (Phase 3.5)."""
import logging
import json
from flask import Blueprint, request, jsonify
from functools import wraps
from flask_login import login_required, current_user

from app.database import db
from app.models.researcher.plugins import (
    Plugin, PluginConfiguration, PluginExecutionLog, PluginStatus
)
from app.services.plugin_manager import get_plugin_manager
from app.services.plugin_registry import get_plugin_registry

logger = logging.getLogger(__name__)

plugin_admin = Blueprint('plugin_admin', __name__, url_prefix='/api/admin/plugins')


def admin_required(f):
    """Decorator to require authenticated admin role."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required.'}), 401
        if not getattr(current_user, 'is_admin', False):
            return jsonify({'error': 'Admin access required.'}), 403
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# Plugin Discovery and Management
# ============================================================================

@plugin_admin.route('', methods=['GET'])
@admin_required
def list_plugins():
    """List all registered plugins.
    
    Query Parameters:
        plugin_type: Filter by plugin type (builtin | custom | external)
        status: Filter by status (installed | enabled | disabled | error)
        
    Returns:
        JSON list of plugin info
    """
    try:
        plugin_type = request.args.get('plugin_type')
        status = request.args.get('status')

        query = db.session.query(Plugin)

        if plugin_type:
            query = query.filter(Plugin.plugin_type == plugin_type)

        if status:
            query = query.filter(Plugin.status == status)

        plugins = query.all()

        return jsonify({
            'success': True,
            'count': len(plugins),
            'plugins': [p.to_dict() for p in plugins],
        }), 200

    except Exception as e:
        logger.error(f"Error listing plugins: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@plugin_admin.route('/<plugin_name>', methods=['GET'])
@admin_required
def get_plugin_info(plugin_name):
    """Get detailed information about a plugin.
    
    Args:
        plugin_name: Plugin name
        
    Returns:
        JSON plugin info with metadata and statistics
    """
    try:
        plugin = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()

        if not plugin:
            return jsonify({
                'success': False,
                'error': f"Plugin {plugin_name} not found",
            }), 404

        return jsonify({
            'success': True,
            'plugin': plugin.to_dict(include_config=True),
            'hooks_registered': len(plugin.hook_registrations),
            'execution_count': plugin.execution_count,
            'error_count': plugin.error_count,
            'configurations': [c.to_dict() for c in plugin.configurations],
        }), 200

    except Exception as e:
        logger.error(f"Error getting plugin info: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================================
# Plugin Lifecycle Control
# ============================================================================

@plugin_admin.route('/<plugin_name>/enable', methods=['POST'])
@admin_required
def enable_plugin(plugin_name):
    """Enable a plugin.
    
    Args:
        plugin_name: Plugin name
        
    Returns:
        JSON with operation result
    """
    try:
        plugin = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()

        if not plugin:
            return jsonify({
                'success': False,
                'error': f"Plugin {plugin_name} not found",
            }), 404

        # Try to load the plugin
        plugin_manager = get_plugin_manager()
        try:
            import asyncio
            # Run async load in sync context
            loop = asyncio.new_event_loop()
            plugin_instance = loop.run_until_complete(plugin_manager.load_plugin(plugin))
            loop.close()

            return jsonify({
                'success': True,
                'message': f"Plugin {plugin_name} enabled successfully",
                'plugin': plugin.to_dict(),
            }), 200

        except Exception as load_error:
            plugin.status = PluginStatus.ERROR.value
            plugin.error_message = str(load_error)
            db.session.add(plugin)
            db.session.commit()

            return jsonify({
                'success': False,
                'error': f"Failed to load plugin: {load_error}",
            }), 500

    except Exception as e:
        logger.error(f"Error enabling plugin: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@plugin_admin.route('/<plugin_name>/disable', methods=['POST'])
@admin_required
def disable_plugin(plugin_name):
    """Disable a plugin.
    
    Args:
        plugin_name: Plugin name
        
    Returns:
        JSON with operation result
    """
    try:
        plugin = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()

        if not plugin:
            return jsonify({
                'success': False,
                'error': f"Plugin {plugin_name} not found",
            }), 404

        # Unload from manager
        plugin_manager = get_plugin_manager()
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(plugin_manager.unload_plugin(plugin_name))
        loop.close()

        plugin.status = PluginStatus.DISABLED.value
        db.session.add(plugin)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': f"Plugin {plugin_name} disabled",
            'plugin': plugin.to_dict(),
        }), 200

    except Exception as e:
        logger.error(f"Error disabling plugin: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================================
# Plugin Configuration
# ============================================================================

@plugin_admin.route('/<plugin_name>/config', methods=['GET'])
@admin_required
def get_plugin_config(plugin_name):
    """Get plugin configuration schema and current config.
    
    Args:
        plugin_name: Plugin name
        
    Returns:
        JSON with config schema and current configuration
    """
    try:
        plugin = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()

        if not plugin:
            return jsonify({
                'success': False,
                'error': f"Plugin {plugin_name} not found",
            }), 404

        config_schema = json.loads(plugin.config_schema_json) if plugin.config_schema_json else {}
        default_config = json.loads(plugin.default_config_json) if plugin.default_config_json else {}

        return jsonify({
            'success': True,
            'plugin_name': plugin_name,
            'config_schema': config_schema,
            'default_config': default_config,
            'current_config': default_config,  # TODO: Get per-project config if provided
        }), 200

    except Exception as e:
        logger.error(f"Error getting plugin config: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@plugin_admin.route('/<plugin_name>/config', methods=['POST'])
@admin_required
def update_plugin_config(plugin_name):
    """Update plugin configuration for a project or tenant.
    
    Args:
        plugin_name: Plugin name
        
    JSON Body:
        project_id: Optional project context
        tenant_id: Optional tenant context
        is_enabled: Whether plugin is enabled for this context
        config: Configuration dictionary
        
    Returns:
        JSON with operation result
    """
    try:
        plugin = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()

        if not plugin:
            return jsonify({
                'success': False,
                'error': f"Plugin {plugin_name} not found",
            }), 404

        data = request.get_json()
        project_id = data.get('project_id')
        tenant_id = data.get('tenant_id')
        is_enabled = data.get('is_enabled', True)
        config_data = data.get('config', {})

        # Find or create configuration
        config = db.session.query(PluginConfiguration).filter(
            PluginConfiguration.plugin_id == plugin.id,
            PluginConfiguration.project_id == project_id,
            PluginConfiguration.tenant_id == tenant_id,
        ).first()

        if config:
            config.is_enabled = is_enabled
            config.config_json = json.dumps(config_data)
        else:
            config = PluginConfiguration(
                plugin_id=plugin.id,
                project_id=project_id,
                tenant_id=tenant_id,
                is_enabled=is_enabled,
                config_json=json.dumps(config_data),
            )
            db.session.add(config)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': "Plugin configuration updated",
            'configuration': config.to_dict(),
        }), 200

    except Exception as e:
        logger.error(f"Error updating plugin config: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================================
# Plugin Execution Logs
# ============================================================================

@plugin_admin.route('/<plugin_name>/logs', methods=['GET'])
@admin_required
def get_plugin_logs(plugin_name):
    """Get execution logs for a plugin.
    
    Query Parameters:
        limit: Number of logs to return (default: 100)
        offset: Offset for pagination (default: 0)
        status: Filter by execution status (success | error | timeout | skipped)
        project_id: Filter by project
        
    Returns:
        JSON list of execution logs
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        status = request.args.get('status')
        project_id = request.args.get('project_id', type=int)

        plugin = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()

        if not plugin:
            return jsonify({
                'success': False,
                'error': f"Plugin {plugin_name} not found",
            }), 404

        query = db.session.query(PluginExecutionLog).filter(
            PluginExecutionLog.plugin_id == plugin.id
        )

        if status:
            query = query.filter(PluginExecutionLog.status == status)

        if project_id:
            query = query.filter(PluginExecutionLog.project_id == project_id)

        total_count = query.count()
        logs = query.order_by(
            PluginExecutionLog.created_at.desc()
        ).limit(limit).offset(offset).all()

        return jsonify({
            'success': True,
            'total_count': total_count,
            'limit': limit,
            'offset': offset,
            'logs': [log.to_dict() for log in logs],
        }), 200

    except Exception as e:
        logger.error(f"Error getting plugin logs: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================================
# Plugin Testing
# ============================================================================

@plugin_admin.route('/<plugin_name>/test', methods=['POST'])
@admin_required
def test_plugin(plugin_name):
    """Test a plugin with sample data.
    
    JSON Body:
        hook_point: Hook point to test (e.g., 'on_extraction')
        test_data: Test data to pass to plugin
        
    Returns:
        JSON with test result
    """
    try:
        plugin_manager = get_plugin_manager()
        plugin = plugin_manager.get_plugin(plugin_name)

        if not plugin:
            return jsonify({
                'success': False,
                'error': f"Plugin {plugin_name} not loaded",
            }), 404

        data = request.get_json()
        hook_point = data.get('hook_point', 'on_extraction')
        test_data = data.get('test_data', {})

        # Create test context
        from app.services.plugin_base import HookContext
        context = HookContext(
            hook_point=hook_point,
            data=test_data,
        )

        # Execute hook
        import asyncio
        loop = asyncio.new_event_loop()
        hook_method_name = hook_point.replace('-', '_')
        
        if not hasattr(plugin, hook_method_name):
            return jsonify({
                'success': False,
                'error': f"Plugin does not implement {hook_point}",
            }), 400

        hook_handler = getattr(plugin, hook_method_name)
        result = loop.run_until_complete(hook_handler(context))
        loop.close()

        return jsonify({
            'success': True,
            'plugin_name': plugin_name,
            'hook_point': hook_point,
            'result': result.to_dict(),
        }), 200

    except Exception as e:
        logger.error(f"Error testing plugin: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================================
# Plugin Statistics
# ============================================================================

@plugin_admin.route('/stats/summary', methods=['GET'])
@admin_required
def get_plugins_summary():
    """Get summary statistics for all plugins.
    
    Returns:
        JSON with aggregated plugin statistics
    """
    try:
        total_plugins = db.session.query(Plugin).count()
        enabled_count = db.session.query(Plugin).filter(
            Plugin.status == PluginStatus.ENABLED.value
        ).count()
        disabled_count = db.session.query(Plugin).filter(
            Plugin.status == PluginStatus.DISABLED.value
        ).count()
        error_count = db.session.query(Plugin).filter(
            Plugin.status == PluginStatus.ERROR.value
        ).count()

        # Get execution stats
        total_executions = db.session.query(
            db.func.sum(Plugin.execution_count)
        ).scalar() or 0

        total_errors = db.session.query(
            db.func.sum(Plugin.error_count)
        ).scalar() or 0

        return jsonify({
            'success': True,
            'summary': {
                'total_plugins': total_plugins,
                'enabled_count': enabled_count,
                'disabled_count': disabled_count,
                'error_count': error_count,
                'total_executions': total_executions,
                'total_errors': total_errors,
                'success_rate': (1 - min(total_errors / max(total_executions, 1), 1)) * 100,
            },
        }), 200

    except Exception as e:
        logger.error(f"Error getting plugin stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


@plugin_admin.route('/<plugin_name>/stats', methods=['GET'])
@admin_required
def get_plugin_stats(plugin_name):
    """Get detailed statistics for a specific plugin.
    
    Args:
        plugin_name: Plugin name
        
    Returns:
        JSON with plugin execution statistics
    """
    try:
        plugin = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()

        if not plugin:
            return jsonify({
                'success': False,
                'error': f"Plugin {plugin_name} not found",
            }), 404

        # Get recent logs
        recent_logs = db.session.query(PluginExecutionLog).filter(
            PluginExecutionLog.plugin_id == plugin.id
        ).order_by(PluginExecutionLog.created_at.desc()).limit(100).all()

        # Calculate averages
        success_count = sum(1 for log in recent_logs if log.status == "success")
        error_count = sum(1 for log in recent_logs if log.status == "error")
        avg_execution_time = (
            sum(log.execution_time_ms for log in recent_logs) / len(recent_logs)
            if recent_logs else 0
        )

        return jsonify({
            'success': True,
            'plugin_name': plugin_name,
            'stats': {
                'total_executions': plugin.execution_count,
                'total_errors': plugin.error_count,
                'recent_logs': len(recent_logs),
                'recent_success_count': success_count,
                'recent_error_count': error_count,
                'average_execution_time_ms': avg_execution_time,
                'last_execution_time': plugin.last_execution_time.isoformat() if plugin.last_execution_time else None,
            },
        }), 200

    except Exception as e:
        logger.error(f"Error getting plugin stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500


# ============================================================================
# Registry Management
# ============================================================================

@plugin_admin.route('/registry/sync', methods=['POST'])
@admin_required
def sync_registry():
    """Sync with plugin registries.
    
    Returns:
        JSON with sync result
    """
    try:
        registry = get_plugin_registry()
        import asyncio
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(registry.discover_plugins())
        loop.close()

        return jsonify({
            'success': True,
            'message': "Registry synced",
            'plugins_discovered': len(result),
        }), 200

    except Exception as e:
        logger.error(f"Error syncing registry: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
        }), 500
