"""Admin debug routes for plugin execution analysis and performance monitoring (Phase 3.7)."""
import json
import logging
from datetime import timedelta
from app.core.time_utils import utcnow_naive
from flask import Blueprint, request, jsonify
from sqlalchemy import func, desc, and_

from app.database import db
from app.models.researcher.plugins import (
    Plugin, PluginExecutionLog, HookPoint
)
from app.models.researcher.extraction_plugins import (
    ExtractionValidationResult
)
from app.routes.route_entity_lookup import get_entity_or_404

logger = logging.getLogger(__name__)

debug_bp = Blueprint('debug', __name__, url_prefix='/api/admin/debug')


def admin_required(f):
    """Minimal admin gate for debug endpoints."""
    def decorated_function(*args, **kwargs):
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        is_admin = request.headers.get('X-Is-Admin', 'false').lower() == 'true'
        if not is_admin:
            return jsonify({'error': 'Admin access required'}), 403

        kwargs['user_id'] = user_id
        return f(*args, **kwargs)

    decorated_function.__name__ = f.__name__
    return decorated_function


@debug_bp.route('/plugins/trace/latest', methods=['GET'])
@admin_required
def get_latest_executions():
    """Get latest plugin executions across all plugins.
    
    Query Parameters:
    - limit: Number of executions (default: 50, max: 500)
    - plugin_name: Filter by plugin (optional)
    - hook_point: Filter by hook point (optional)
    - status: Filter by status (success|error|timeout) (optional)
    - days: Last N days (default: 7)
    """
    try:
        limit = min(int(request.args.get('limit', 50)), 500)
        plugin_name = request.args.get('plugin_name')
        hook_point = request.args.get('hook_point')
        status = request.args.get('status')
        days = int(request.args.get('days', 7))

        # Build query
        query = PluginExecutionLog.query
        
        # Filter by date
        cutoff_date = utcnow_naive() - timedelta(days=days)
        query = query.filter(PluginExecutionLog.executed_at >= cutoff_date)

        # Filter by plugin
        if plugin_name:
            plugin = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()
            if plugin:
                query = query.filter(PluginExecutionLog.plugin_id == plugin.id)

        # Filter by hook point
        if hook_point:
            query = query.filter(PluginExecutionLog.hook_point == hook_point)

        # Filter by status
        if status:
            query = query.filter(PluginExecutionLog.status == status)

        # Get total count
        total = query.count()

        # Get limited results, sorted by most recent
        executions = query.order_by(desc(PluginExecutionLog.executed_at)).limit(limit).all()

        out = []
        for exe in executions:
            out.append({
                'id': exe.id,
                'plugin_name': exe.plugin.name if exe.plugin else 'unknown',
                'hook_point': exe.hook_point,
                'request_id': exe.request_id,
                'status': exe.status,
                'execution_time_ms': exe.execution_time_ms,
                'error': exe.error_message,
                'executed_at': exe.executed_at.isoformat() if exe.executed_at else None,
                'traceback': exe.traceback if exe.traceback else None,
            })

        return jsonify({
            'executions': out,
            'count': len(out),
            'total_available': total,
            'time_period_days': days,
            'filters': {
                'plugin_name': plugin_name,
                'hook_point': hook_point,
                'status': status,
            }
        })

    except Exception as e:
        logger.error(f"Error retrieving latest executions: {e}")
        return jsonify({'error': str(e)}), 500


@debug_bp.route('/plugins/trace/<int:execution_id>', methods=['GET'])
@admin_required
def get_execution_trace(execution_id):
    """Get detailed trace for single execution."""
    try:
        execution = get_entity_or_404(PluginExecutionLog, execution_id)

        # Parse JSON fields
        request_data = json.loads(execution.request_data) if execution.request_data else {}
        response_data = json.loads(execution.response_data) if execution.response_data else {}

        return jsonify({
            'execution_id': execution.id,
            'plugin_name': execution.plugin.name if execution.plugin else 'unknown',
            'plugin_version': execution.plugin.version if execution.plugin else None,
            'hook_point': execution.hook_point,
            'request_id': execution.request_id,
            'context': {
                'hook_point': execution.hook_point,
                'has_request_data': bool(execution.request_data),
                'has_response_data': bool(execution.response_data),
            },
            'request_data': request_data[:200] if isinstance(request_data, dict) else str(request_data)[:200],
            'response_data': response_data[:200] if isinstance(response_data, dict) else str(response_data)[:200],
            'execution_time_ms': execution.execution_time_ms,
            'status': execution.status,
            'error': execution.error_message,
            'executed_at': execution.executed_at.isoformat() if execution.executed_at else None,
            'traceback': execution.traceback if execution.traceback else None,
        })

    except Exception as e:
        logger.error(f"Error retrieving execution trace: {e}")
        return jsonify({'error': str(e)}), 500


@debug_bp.route('/plugins/<plugin_name>/trace', methods=['GET'])
@admin_required
def get_plugin_trace(plugin_name):
    """Get execution history for specific plugin.
    
    Query Parameters:
    - days: Last N days (default: 7)
    - limit: Results per page (default: 100)
    - offset: Pagination offset (default: 0)
    """
    try:
        plugin = Plugin.query.filter(Plugin.name == plugin_name).first_or_404()
        days = int(request.args.get('days', 7))
        limit = min(int(request.args.get('limit', 100)), 500)
        offset = int(request.args.get('offset', 0))

        # Build query
        cutoff_date = utcnow_naive() - timedelta(days=days)
        query = PluginExecutionLog.query.filter(
            and_(
                PluginExecutionLog.plugin_id == plugin.id,
                PluginExecutionLog.executed_at >= cutoff_date
            )
        )

        total = query.count()
        executions = query.order_by(desc(PluginExecutionLog.executed_at))\
            .limit(limit).offset(offset).all()

        out = []
        for exe in executions:
            out.append({
                'execution_id': exe.id,
                'hook_point': exe.hook_point,
                'status': exe.status,
                'execution_time_ms': exe.execution_time_ms,
                'error': exe.error_message,
                'executed_at': exe.executed_at.isoformat() if exe.executed_at else None,
            })

        return jsonify({
            'plugin_name': plugin_name,
            'executions': out,
            'count': len(out),
            'offset': offset,
            'total': total,
            'time_period': {
                'start': cutoff_date.isoformat(),
                'end': utcnow_naive().isoformat(),
                'days': days,
            }
        })

    except Exception as e:
        logger.error(f"Error retrieving plugin trace: {e}")
        return jsonify({'error': str(e)}), 500


@debug_bp.route('/plugins/analytics/performance', methods=['GET'])
@admin_required
def get_performance_analytics():
    """Get overall performance metrics for all plugins."""
    try:
        days = int(request.args.get('days', 7))
        cutoff_date = utcnow_naive() - timedelta(days=days)

        # Get all executions in period
        executions = PluginExecutionLog.query.filter(
            PluginExecutionLog.executed_at >= cutoff_date
        ).all()

        if not executions:
            return jsonify({
                'summary': {
                    'total_executions': 0,
                    'total_errors': 0,
                    'average_execution_time_ms': 0.0,
                    'p95_execution_time_ms': 0.0,
                    'p99_execution_time_ms': 0.0,
                    'error_rate': 0.0,
                    'timeout_count': 0,
                },
                'by_plugin': [],
                'time_period_days': days,
            })

        # Calculate overall metrics
        total_executions = len(executions)
        total_errors = len([e for e in executions if e.status == 'error'])
        timeout_count = len([e for e in executions if e.status == 'timeout'])
        
        execution_times = [e.execution_time_ms for e in executions if e.execution_time_ms]
        execution_times.sort()
        
        avg_time = sum(execution_times) / len(execution_times) if execution_times else 0.0
        p95_idx = int(len(execution_times) * 0.95)
        p99_idx = int(len(execution_times) * 0.99)
        p95_time = execution_times[p95_idx] if p95_idx < len(execution_times) else 0.0
        p99_time = execution_times[p99_idx] if p99_idx < len(execution_times) else 0.0

        summary = {
            'total_executions': total_executions,
            'total_errors': total_errors,
            'average_execution_time_ms': round(avg_time, 2),
            'p95_execution_time_ms': round(p95_time, 2),
            'p99_execution_time_ms': round(p99_time, 2),
            'error_rate': round(total_errors / total_executions, 4) if total_executions > 0 else 0.0,
            'timeout_count': timeout_count,
        }

        # Group by plugin
        by_plugin = {}
        for exe in executions:
            plugin_name = exe.plugin.name if exe.plugin else 'unknown'
            if plugin_name not in by_plugin:
                by_plugin[plugin_name] = {
                    'execution_count': 0,
                    'error_count': 0,
                    'timeout_count': 0,
                    'times': [],
                }
            
            by_plugin[plugin_name]['execution_count'] += 1
            if exe.status == 'error':
                by_plugin[plugin_name]['error_count'] += 1
            if exe.status == 'timeout':
                by_plugin[plugin_name]['timeout_count'] += 1
            if exe.execution_time_ms:
                by_plugin[plugin_name]['times'].append(exe.execution_time_ms)

        # Calculate per-plugin stats
        plugin_stats = []
        for plugin_name, stats in by_plugin.items():
            times = stats['times']
            times.sort()
            
            avg = sum(times) / len(times) if times else 0.0
            p95 = times[int(len(times) * 0.95)] if len(times) > 0 else 0.0
            
            plugin_stats.append({
                'plugin_name': plugin_name,
                'execution_count': stats['execution_count'],
                'error_count': stats['error_count'],
                'timeout_count': stats['timeout_count'],
                'average_time_ms': round(avg, 2),
                'p95_time_ms': round(p95, 2),
                'error_rate': round(stats['error_count'] / stats['execution_count'], 4) if stats['execution_count'] > 0 else 0.0,
                'success_rate': round(1.0 - (stats['error_count'] / stats['execution_count']), 4) if stats['execution_count'] > 0 else 1.0,
            })

        # Sort by execution count descending
        plugin_stats.sort(key=lambda x: x['execution_count'], reverse=True)

        return jsonify({
            'summary': summary,
            'by_plugin': plugin_stats,
            'time_period_days': days,
        })

    except Exception as e:
        logger.error(f"Error retrieving performance analytics: {e}")
        return jsonify({'error': str(e)}), 500


@debug_bp.route('/plugins/<plugin_name>/analytics', methods=['GET'])
@admin_required
def get_plugin_analytics(plugin_name):
    """Get detailed analytics for single plugin.
    
    Query Parameters:
    - days: Time period (default: 7)
    """
    try:
        plugin = Plugin.query.filter(Plugin.name == plugin_name).first_or_404()
        days = int(request.args.get('days', 7))
        cutoff_date = utcnow_naive() - timedelta(days=days)

        # Get executions for plugin
        executions = PluginExecutionLog.query.filter(
            and_(
                PluginExecutionLog.plugin_id == plugin.id,
                PluginExecutionLog.executed_at >= cutoff_date
            )
        ).all()

        if not executions:
            return jsonify({
                'plugin_name': plugin_name,
                'summary': {
                    'executions': 0,
                    'errors': 0,
                    'average_time_ms': 0.0,
                },
                'by_hook_point': [],
                'timeline': [],
                'errors_by_type': [],
            })

        # Summary stats
        total_execs = len(executions)
        total_errors = len([e for e in executions if e.status == 'error'])
        execution_times = [e.execution_time_ms for e in executions if e.execution_time_ms]
        avg_time = sum(execution_times) / len(execution_times) if execution_times else 0.0

        summary = {
            'executions': total_execs,
            'errors': total_errors,
            'average_time_ms': round(avg_time, 2),
            'p95_time_ms': round(sorted(execution_times)[int(len(execution_times) * 0.95)], 2) if execution_times else 0.0,
            'error_rate': round(total_errors / total_execs, 4) if total_execs > 0 else 0.0,
        }

        # By hook point
        by_hook = {}
        for exe in executions:
            hook = exe.hook_point or 'unknown'
            if hook not in by_hook:
                by_hook[hook] = {'count': 0, 'times': [], 'errors': 0}
            by_hook[hook]['count'] += 1
            if exe.execution_time_ms:
                by_hook[hook]['times'].append(exe.execution_time_ms)
            if exe.status == 'error':
                by_hook[hook]['errors'] += 1

        hook_stats = []
        for hook, stats in by_hook.items():
            avg = sum(stats['times']) / len(stats['times']) if stats['times'] else 0.0
            hook_stats.append({
                'hook_point': hook,
                'count': stats['count'],
                'average_time_ms': round(avg, 2),
                'error_count': stats['errors'],
            })

        # Timeline (by day)
        timeline = {}
        for exe in executions:
            day = exe.executed_at.date() if exe.executed_at else None
            if not day:
                continue
            if day not in timeline:
                timeline[day] = {'executions': 0, 'errors': 0, 'times': []}
            timeline[day]['executions'] += 1
            if exe.status == 'error':
                timeline[day]['errors'] += 1
            if exe.execution_time_ms:
                timeline[day]['times'].append(exe.execution_time_ms)

        timeline_list = []
        for day in sorted(timeline.keys(), reverse=True):
            stats = timeline[day]
            avg = sum(stats['times']) / len(stats['times']) if stats['times'] else 0.0
            timeline_list.append({
                'date': day.isoformat(),
                'executions': stats['executions'],
                'errors': stats['errors'],
                'average_time_ms': round(avg, 2),
            })

        # Error types
        error_types = {}
        for exe in executions:
            if exe.status == 'error':
                error_type = 'ValidationError'  # Default
                if exe.error_message:
                    if 'timeout' in exe.error_message.lower():
                        error_type = 'TimeoutError'
                    elif 'database' in exe.error_message.lower():
                        error_type = 'DatabaseError'
                    elif 'validation' in exe.error_message.lower():
                        error_type = 'ValidationError'
                
                if error_type not in error_types:
                    error_types[error_type] = 0
                error_types[error_type] += 1

        error_list = []
        for error_type, count in error_types.items():
            error_list.append({
                'error_type': error_type,
                'count': count,
                'percentage': round((count / total_errors * 100) if total_errors > 0 else 0, 1),
            })

        return jsonify({
            'plugin_name': plugin_name,
            'time_period': f"{days} days",
            'summary': summary,
            'by_hook_point': hook_stats,
            'timeline': timeline_list,
            'errors_by_type': error_list,
        })

    except Exception as e:
        logger.error(f"Error retrieving plugin analytics: {e}")
        return jsonify({'error': str(e)}), 500


@debug_bp.route('/plugins/analytics/comparison', methods=['GET'])
@admin_required
def compare_plugin_analytics():
    """Compare performance metrics across plugins.
    
    Query Parameters:
    - metric: time|errors|success_rate (default: time)
    - period: 7d|30d|90d (default: 7d)
    """
    try:
        metric = request.args.get('metric', 'time')
        period = request.args.get('period', '7d')
        
        # Parse period
        if period == '7d':
            days = 7
        elif period == '30d':
            days = 30
        elif period == '90d':
            days = 90
        else:
            days = 7

        cutoff_date = utcnow_naive() - timedelta(days=days)

        # Get all executions
        executions = PluginExecutionLog.query.filter(
            PluginExecutionLog.executed_at >= cutoff_date
        ).all()

        # Group by plugin
        by_plugin = {}
        for exe in executions:
            plugin_name = exe.plugin.name if exe.plugin else 'unknown'
            if plugin_name not in by_plugin:
                by_plugin[plugin_name] = {
                    'count': 0,
                    'errors': 0,
                    'times': [],
                }
            by_plugin[plugin_name]['count'] += 1
            if exe.status == 'error':
                by_plugin[plugin_name]['errors'] += 1
            if exe.execution_time_ms:
                by_plugin[plugin_name]['times'].append(exe.execution_time_ms)

        # Calculate metrics
        data = []
        for plugin_name, stats in by_plugin.items():
            times = stats['times']
            times.sort()
            
            avg_time = sum(times) / len(times) if times else 0.0
            error_rate = stats['errors'] / stats['count'] if stats['count'] > 0 else 0.0
            success_rate = 1.0 - error_rate

            # Select metric
            if metric == 'time':
                value = round(avg_time, 2)
                units = 'milliseconds'
            elif metric == 'errors':
                value = stats['errors']
                units = 'count'
            elif metric == 'success_rate':
                value = round(success_rate * 100, 1)
                units = 'percentage'
            else:
                value = round(avg_time, 2)
                units = 'milliseconds'

            data.append({
                'label': plugin_name,
                'value': value,
                'execution_count': stats['count'],
            })

        # Sort and add rank
        data.sort(key=lambda x: x['value'])
        for i, item in enumerate(data, 1):
            item['rank'] = i
            item['trend'] = 'stable'  # Would need historical data for trends

        return jsonify({
            'metric': metric,
            'period': f"{days} days",
            'units': units,
            'data': data,
        })

    except Exception as e:
        logger.error(f"Error comparing plugin analytics: {e}")
        return jsonify({'error': str(e)}), 500


@debug_bp.route('/validation/history', methods=['GET'])
@admin_required
def get_validation_history():
    """Get validation operation history.
    
    Query Parameters:
    - schema_id: Filter by schema (optional)
    - field_name: Filter by field (optional)
    - days: Last N days (default: 7)
    - limit: Results (default: 100)
    - offset: Pagination offset (default: 0)
    """
    try:
        schema_id = request.args.get('schema_id')
        field_name = request.args.get('field_name')
        days = int(request.args.get('days', 7))
        limit = min(int(request.args.get('limit', 100)), 500)
        offset = int(request.args.get('offset', 0))

        cutoff_date = utcnow_naive() - timedelta(days=days)

        # Query validation results
        query = ExtractionValidationResult.query.filter(
            ExtractionValidationResult.executed_at >= cutoff_date
        )

        total = query.count()
        results = query.order_by(desc(ExtractionValidationResult.executed_at))\
            .limit(limit).offset(offset).all()

        validations = []
        for result in results:
            validations.append({
                'validation_id': result.id,
                'field_id': result.field_value.field_id if result.field_value else None,
                'field_name': result.field_value.field.field_name if result.field_value and result.field_value.field else 'unknown',
                'is_valid': result.is_valid,
                'validation_message': result.validation_message,
                'plugin_name': result.plugin.name if result.plugin else 'unknown',
                'execution_time_ms': result.execution_time_ms,
                'executed_at': result.executed_at.isoformat() if result.executed_at else None,
                'suggestions': result.get_suggestions(),
            })

        # Summary stats
        valid_count = sum(1 for r in results if r.is_valid)
        invalid_count = len(results) - valid_count

        return jsonify({
            'validations': validations,
            'count': len(validations),
            'offset': offset,
            'total': total,
            'summary': {
                'total_validations': total,
                'valid_percentage': round((valid_count / total * 100) if total > 0 else 0, 1),
                'invalid_percentage': round((invalid_count / total * 100) if total > 0 else 0, 1),
                'average_duration_ms': round(sum(r.execution_time_ms or 0 for r in results) / len(results), 2) if results else 0.0,
            },
            'time_period_days': days,
        })

    except Exception as e:
        logger.error(f"Error retrieving validation history: {e}")
        return jsonify({'error': str(e)}), 500


@debug_bp.route('/validation/summary', methods=['GET'])
@admin_required
def get_validation_summary():
    """Get validation summary statistics.
    
    Query Parameters:
    - days: Last N days (default: 7)
    """
    try:
        days = int(request.args.get('days', 7))
        cutoff_date = utcnow_naive() - timedelta(days=days)

        # Query validation results
        results = ExtractionValidationResult.query.filter(
            ExtractionValidationResult.executed_at >= cutoff_date
        ).all()

        if not results:
            return jsonify({
                'summary': {
                    'total': 0,
                    'valid': 0,
                    'invalid': 0,
                    'valid_percentage': 0.0,
                    'invalid_percentage': 0.0,
                    'average_duration_ms': 0.0,
                },
                'time_period_days': days,
            })

        total = len(results)
        valid = sum(1 for r in results if r.is_valid)
        invalid = total - valid
        avg_duration = sum(r.execution_time_ms or 0 for r in results) / total if total > 0 else 0.0

        return jsonify({
            'summary': {
                'total': total,
                'valid': valid,
                'invalid': invalid,
                'valid_percentage': round((valid / total * 100) if total > 0 else 0, 1),
                'invalid_percentage': round((invalid / total * 100) if total > 0 else 0, 1),
                'average_duration_ms': round(avg_duration, 2),
            },
            'time_period_days': days,
        })

    except Exception as e:
        logger.error(f"Error retrieving validation summary: {e}")
        return jsonify({'error': str(e)}), 500


@debug_bp.route('/health', methods=['GET'])
@admin_required
def get_debug_health():
    """Get system health status from debug perspective."""
    try:
        # Check plugin executions in last 1 hour
        one_hour_ago = utcnow_naive() - timedelta(hours=1)
        recent_executions = PluginExecutionLog.query.filter(
            PluginExecutionLog.executed_at >= one_hour_ago
        ).all()

        recent_errors = sum(1 for e in recent_executions if e.status == 'error')
        recent_timeouts = sum(1 for e in recent_executions if e.status == 'timeout')

        # Check validation in last 1 hour
        recent_validations = ExtractionValidationResult.query.filter(
            ExtractionValidationResult.executed_at >= one_hour_ago
        ).all()

        validation_errors = sum(1 for v in recent_validations if not v.is_valid)

        # Overall health
        health_status = 'healthy'
        if recent_errors > 5 or recent_timeouts > 2:
            health_status = 'degraded'
        if recent_errors > 20 or recent_timeouts > 10:
            health_status = 'unhealthy'

        return jsonify({
            'status': health_status,
            'last_hour': {
                'plugin_executions': len(recent_executions),
                'plugin_errors': recent_errors,
                'plugin_timeouts': recent_timeouts,
                'validations': len(recent_validations),
                'validation_failures': validation_errors,
            },
            'timestamp': utcnow_naive().isoformat(),
        })

    except Exception as e:
        logger.error(f"Error retrieving debug health: {e}")
        return jsonify({'error': str(e), 'status': 'error'}), 500
