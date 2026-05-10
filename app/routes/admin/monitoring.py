"""REST and WebSocket routes for real-time monitoring (Phase 4.3)."""

from flask import Blueprint, request, jsonify
from datetime import datetime
from functools import wraps
from app.services.monitoring import monitoring_service
from app.services.plugin_permissions import PluginPermissionService
from app.models.researcher.monitoring import (
    AlertConfiguration,
    PerformanceAlert,
    AlertStatus,
)
from app.models.researcher.batch_operations import BatchJob
from app.database import db
import json

# Create blueprint
monitoring_bp = Blueprint("monitoring", __name__, url_prefix="/api/monitoring")

# ==================== Utility Functions ====================


def admin_required(f):
    """Decorator to check admin permissions."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.headers.get("X-User-ID")
        if not user_id:
            return jsonify({"error": "Unauthorized"}), 401

        # Check admin status (you may need to adjust based on your user model)
        # For now, we check if user is admin
        is_admin = request.headers.get("X-Is-Admin", "false").lower() == "true"
        if not is_admin:
            return jsonify({"error": "Admin access required"}), 403

        kwargs["user_id"] = user_id
        return f(*args, **kwargs)

    return decorated_function


def handle_errors(f):
    """Decorator for consistent error handling."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return decorated_function


# ==================== REST Endpoints ====================


@monitoring_bp.route("/health", methods=["GET"])
@admin_required
@handle_errors
def get_system_health(user_id=None):
    """
    Get current system health status.

    Returns:
        dict: Latest system health metrics
    """
    result = monitoring_service.get_system_health(hours=1)

    if "error" in result:
        return jsonify(result), 400

    return jsonify({"success": True, "data": result}), 200


@monitoring_bp.route("/health/history", methods=["GET"])
@admin_required
@handle_errors
def get_health_history(user_id=None):
    """
    Get system health history.

    Query Parameters:
        hours: Hours to look back (default: 24)
        limit: Max records (default: 100, max: 1000)

    Returns:
        list: Health data points
    """
    hours = min(int(request.args.get("hours", 24)), 720)  # Max 30 days
    limit = min(int(request.args.get("limit", 100)), 1000)

    result = monitoring_service.get_system_health_history(hours=hours, limit=limit)

    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 400

    return jsonify({"success": True, "data": result, "count": len(result)}), 200


@monitoring_bp.route("/metrics/job/<int:job_id>", methods=["GET"])
@admin_required
@handle_errors
def get_job_metrics(job_id, user_id=None):
    """
    Get performance metrics for a batch job.

    Returns:
        dict: Job performance statistics
    """
    job = db.session.get(BatchJob, job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    result = monitoring_service.calculate_job_performance(job_id)

    if "error" in result:
        return jsonify(result), 400

    return jsonify({"success": True, "job_id": job_id, "data": result}), 200


@monitoring_bp.route("/metrics/plugin/<int:plugin_id>/trends", methods=["GET"])
@admin_required
@handle_errors
def get_plugin_trends(plugin_id, user_id=None):
    """
    Analyze performance trends for a plugin.

    Query Parameters:
        days: Days to analyze (default: 7, max: 90)
        metric_type: Type of metric (default: execution_time)

    Returns:
        dict: Trend analysis
    """
    days = min(int(request.args.get("days", 7)), 90)
    metric_type = request.args.get("metric_type", "execution_time")

    result = monitoring_service.analyze_trends(plugin_id, metric_type, days=days)

    if "error" in result:
        return jsonify(result), 400

    return jsonify({"success": True, "plugin_id": plugin_id, "data": result}), 200


@monitoring_bp.route("/benchmarks/<int:plugin_id>", methods=["GET"])
@admin_required
@handle_errors
def get_plugin_benchmark(plugin_id, user_id=None):
    """
    Get performance benchmark for a plugin.

    Returns:
        dict: Plugin benchmark data
    """
    result = monitoring_service.get_plugin_performance_report(plugin_id)

    if "error" in result:
        return jsonify(result), 400

    return jsonify({"success": True, "plugin_id": plugin_id, "data": result}), 200


@monitoring_bp.route("/benchmarks/<int:plugin_id>", methods=["POST"])
@admin_required
@handle_errors
def create_plugin_benchmark(plugin_id, user_id=None):
    """
    Create or update performance benchmark for a plugin.

    Request Body:
        {
            "plugin_name": "string"
        }

    Returns:
        dict: Created benchmark
    """
    data = request.get_json() or {}
    plugin_name = data.get("plugin_name", f"plugin_{plugin_id}")

    success, message, benchmark_id = monitoring_service.create_performance_benchmark(
        plugin_id, plugin_name
    )

    if not success:
        return jsonify({"error": message}), 400

    return jsonify(
        {"success": True, "message": message, "benchmark_id": benchmark_id}
    ), 201


# ==================== Alert Endpoints ====================


@monitoring_bp.route("/alerts", methods=["GET"])
@admin_required
@handle_errors
def get_alerts(user_id=None):
    """
    Get performance alerts with optional filtering.

    Query Parameters:
        status: Filter by status (active, acknowledged, resolved)
        alert_type: Filter by alert type
        severity: Filter by severity (low, medium, high, critical)
        limit: Max records (default: 100, max: 500)

    Returns:
        list: Alert records
    """
    status = request.args.get("status")
    alert_type = request.args.get("alert_type")
    severity = request.args.get("severity")
    limit = min(int(request.args.get("limit", 100)), 500)

    result = monitoring_service.get_performance_alerts(
        status=status, alert_type=alert_type, severity=severity, limit=limit
    )

    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 400

    return jsonify({"success": True, "data": result, "count": len(result)}), 200


@monitoring_bp.route("/alerts/<int:alert_id>/acknowledge", methods=["POST"])
@admin_required
@handle_errors
def acknowledge_alert(alert_id, user_id=None):
    """
    Acknowledge a performance alert.

    Returns:
        dict: Success message
    """
    success, message = monitoring_service.acknowledge_alert(alert_id)

    if not success:
        return jsonify({"error": message}), 400

    return jsonify({"success": True, "message": message, "alert_id": alert_id}), 200


@monitoring_bp.route("/alerts/<int:alert_id>/resolve", methods=["POST"])
@admin_required
@handle_errors
def resolve_alert(alert_id, user_id=None):
    """
    Resolve a performance alert.

    Returns:
        dict: Success message
    """
    success, message = monitoring_service.resolve_alert(alert_id)

    if not success:
        return jsonify({"error": message}), 400

    return jsonify({"success": True, "message": message, "alert_id": alert_id}), 200


@monitoring_bp.route("/alerts/check", methods=["POST"])
@admin_required
@handle_errors
def check_alerts(user_id=None):
    """
    Manually trigger alert checking.

    Returns:
        dict: Number of alerts created
    """
    success, message, count = monitoring_service.check_performance_alerts()

    if not success:
        return jsonify({"error": message}), 400

    return jsonify({"success": True, "message": message, "alerts_created": count}), 200


# ==================== Alert Configuration ====================


@monitoring_bp.route("/alerts/config", methods=["GET"])
@admin_required
@handle_errors
def get_alert_configurations(user_id=None):
    """
    Get all alert configurations.

    Returns:
        list: Alert configurations
    """
    try:
        configs = AlertConfiguration.query.all()
        return jsonify(
            {
                "success": True,
                "data": [c.to_dict() for c in configs],
                "count": len(configs),
            }
        ), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@monitoring_bp.route("/alerts/config", methods=["POST"])
@admin_required
@handle_errors
def create_alert_configuration(user_id=None):
    """
    Create a new alert configuration.

    Request Body:
        {
            "alert_type": "string",
            "metric_name": "string",
            "warning_threshold": number,
            "critical_threshold": number,
            "enabled": boolean,
            "notify_via_email": boolean,
            "notify_via_webhook": boolean
        }

    Returns:
        dict: Created configuration
    """
    data = request.get_json() or {}

    try:
        config = AlertConfiguration(
            alert_type=data.get("alert_type"),
            metric_name=data.get("metric_name"),
            warning_threshold=float(data.get("warning_threshold", 0)),
            critical_threshold=float(data.get("critical_threshold", 0)),
            enabled=data.get("enabled", True),
            notify_via_email=data.get("notify_via_email", False),
            notify_via_webhook=data.get("notify_via_webhook", False),
        )

        db.session.add(config)
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "Alert configuration created",
                "data": config.to_dict(),
            }
        ), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@monitoring_bp.route("/alerts/config/<int:config_id>", methods=["PUT"])
@admin_required
@handle_errors
def update_alert_configuration(config_id, user_id=None):
    """
    Update an alert configuration.

    Request Body:
        {
            "warning_threshold": number,
            "critical_threshold": number,
            "enabled": boolean
        }

    Returns:
        dict: Updated configuration
    """
    config = db.session.get(AlertConfiguration, config_id)
    if not config:
        return jsonify({"error": "Configuration not found"}), 404

    data = request.get_json() or {}

    try:
        if "warning_threshold" in data:
            config.warning_threshold = float(data["warning_threshold"])
        if "critical_threshold" in data:
            config.critical_threshold = float(data["critical_threshold"])
        if "enabled" in data:
            config.enabled = data["enabled"]
        if "notify_via_email" in data:
            config.notify_via_email = data["notify_via_email"]
        if "notify_via_webhook" in data:
            config.notify_via_webhook = data["notify_via_webhook"]

        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "Configuration updated",
                "data": config.to_dict(),
            }
        ), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@monitoring_bp.route("/alerts/config/<int:config_id>", methods=["DELETE"])
@admin_required
@handle_errors
def delete_alert_configuration(config_id, user_id=None):
    """
    Delete an alert configuration.

    Returns:
        dict: Success message
    """
    config = db.session.get(AlertConfiguration, config_id)
    if not config:
        return jsonify({"error": "Configuration not found"}), 404

    try:
        db.session.delete(config)
        db.session.commit()

        return jsonify({"success": True, "message": "Configuration deleted"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


# ==================== Dashboard & Reports ====================


@monitoring_bp.route("/dashboard", methods=["GET"])
@admin_required
@handle_errors
def get_dashboard(user_id=None):
    """
    Get dashboard metrics.

    Query Parameters:
        timeframe: '1h', '24h', '7d', '30d' (default: '1h')

    Returns:
        dict: Dashboard data
    """
    timeframe = request.args.get("timeframe", "1h")

    result = monitoring_service.get_dashboard_metrics(timeframe=timeframe)

    if "error" in result:
        return jsonify(result), 400

    return jsonify({"success": True, "data": result}), 200


@monitoring_bp.route("/reports/plugin/<int:plugin_id>", methods=["GET"])
@admin_required
@handle_errors
def get_plugin_report(plugin_id, user_id=None):
    """
    Get comprehensive plugin performance report.

    Query Parameters:
        days: Days to analyze (default: 30, max: 365)

    Returns:
        dict: Performance report
    """
    days = min(int(request.args.get("days", 30)), 365)

    result = monitoring_service.get_plugin_performance_report(plugin_id, days=days)

    if "error" in result:
        return jsonify(result), 400

    return jsonify({"success": True, "data": result}), 200


# ==================== WebSocket Support (Blueprint registration) ====================
# Note: WebSocket support requires flask-sock or similar extension
# The actual WebSocket handlers should be registered separately with the app


def register_websocket_handlers(app, sock):
    """
    Register WebSocket handlers for real-time monitoring.

    Args:
        app: Flask app instance
        sock: Flask-Sock instance
    """

    # Store active connections
    active_connections = {
        "job_monitors": {},  # {job_id: [connections]}
        "system_monitor": [],
        "alert_monitor": [],
    }

    @sock.route("/ws/monitoring/jobs/<int:job_id>")
    def monitor_job(ws, job_id):
        """
        WebSocket handler for job-specific monitoring.

        Sends real-time metrics for a specific batch job.
        """
        if job_id not in active_connections["job_monitors"]:
            active_connections["job_monitors"][job_id] = []

        active_connections["job_monitors"][job_id].append(ws)

        try:
            while not ws.closed:
                data = ws.receive()
                if data:
                    # Handle incoming messages (e.g., commands)
                    message = json.loads(data) if isinstance(data, str) else data

                    if message.get("type") == "get_metrics":
                        # Get current metrics and send back
                        job = db.session.get(BatchJob, job_id)
                        if job:
                            result = monitoring_service.calculate_job_performance(
                                job_id
                            )
                            ws.send(
                                json.dumps(
                                    {
                                        "type": "metrics_update",
                                        "job_id": job_id,
                                        "status": job.status,
                                        "progress": job.progress,
                                        "metrics": result,
                                    }
                                )
                            )
        finally:
            active_connections["job_monitors"][job_id].remove(ws)

    @sock.route("/ws/monitoring/system")
    def monitor_system(ws):
        """
        WebSocket handler for system-wide monitoring.

        Broadcasts system health metrics to all connected clients.
        """
        active_connections["system_monitor"].append(ws)

        try:
            while not ws.closed:
                data = ws.receive()
                if data:
                    message = json.loads(data) if isinstance(data, str) else data

                    if message.get("type") == "get_health":
                        # Get current health and send back
                        result = monitoring_service.get_system_health(hours=1)
                        ws.send(
                            json.dumps(
                                {
                                    "type": "health_update",
                                    "data": result
                                    if isinstance(result, dict) and "id" in result
                                    else None,
                                }
                            )
                        )
        finally:
            active_connections["system_monitor"].remove(ws)

    @sock.route("/ws/monitoring/alerts")
    def monitor_alerts(ws):
        """
        WebSocket handler for alert monitoring.

        Sends real-time alerts to subscribed clients.
        """
        active_connections["alert_monitor"].append(ws)

        try:
            while not ws.closed:
                data = ws.receive()
                if data:
                    message = json.loads(data) if isinstance(data, str) else data

                    if message.get("type") == "get_active_alerts":
                        # Get active alerts
                        result = monitoring_service.get_performance_alerts(
                            status=AlertStatus.ACTIVE.value, limit=50
                        )
                        ws.send(
                            json.dumps(
                                {
                                    "type": "alerts_update",
                                    "data": result if isinstance(result, list) else [],
                                    "count": len(result)
                                    if isinstance(result, list)
                                    else 0,
                                }
                            )
                        )
        finally:
            active_connections["alert_monitor"].remove(ws)

    return active_connections
