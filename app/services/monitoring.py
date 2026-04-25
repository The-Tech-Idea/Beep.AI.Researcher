"""Real-time monitoring service for Phase 4.3."""
import psutil
import statistics
from datetime import datetime, timedelta, UTC
from sqlalchemy import func, and_, or_, desc
from app.database import db
from app.models.researcher.monitoring import (
    JobMetrics, PerformanceBenchmark, SystemHealth, PerformanceAlert,
    AlertConfiguration, AuditMetrics, MetricType, AlertType, AlertSeverity,
    AlertStatus, HealthStatus
)
from app.models.researcher.batch_operations import BatchJob
from app.services.plugin_permissions import PluginPermissionService


class MonitoringService:
    """Service for real-time monitoring, metrics collection, and performance analysis."""
    
    def __init__(self):
        """Initialize monitoring service."""
        self.psutil_available = True
        try:
            import psutil
            self.psutil = psutil
        except ImportError:
            self.psutil_available = False

    def _utcnow(self):
        return datetime.now(UTC).replace(tzinfo=None)
    
    # ==================== Metric Recording ====================
    
    def record_job_metric(self, batch_job_id, metric_type, metric_value, unit,
                         plugin_id=None, plugin_name=None, record_index=None,
                         operation_type=None, success=True, error_message=None):
        """
        Record a metric for a batch job or plugin execution.
        
        Args:
            batch_job_id: BatchJob ID
            metric_type: Type of metric (execution_time, memory_used, cpu_usage, etc)
            metric_value: The actual value
            unit: Unit of measurement (ms, MB, %, etc)
            plugin_id: Optional plugin ID
            plugin_name: Optional plugin name
            record_index: Optional record index in batch
            operation_type: Optional operation type description
            success: Whether operation succeeded
            error_message: Optional error message
            
        Returns:
            tuple: (success, message, metric_id)
        """
        try:
            metric = JobMetrics(
                batch_job_id=batch_job_id,
                metric_type=metric_type,
                metric_value=metric_value,
                unit=unit,
                plugin_id=plugin_id,
                plugin_name=plugin_name,
                record_index=record_index,
                operation_type=operation_type,
                success=success,
                error_message=error_message
            )
            db.session.add(metric)
            db.session.commit()
            
            return True, "Metric recorded successfully", metric.id
        except Exception as e:
            db.session.rollback()
            return False, f"Failed to record metric: {str(e)}", None
    
    # ==================== Performance Analysis ====================
    
    def calculate_job_performance(self, batch_job_id):
        """
        Calculate aggregate performance statistics for a job.
        
        Args:
            batch_job_id: BatchJob ID
            
        Returns:
            dict: Performance statistics
        """
        try:
            metrics = JobMetrics.query.filter_by(batch_job_id=batch_job_id).all()
            
            if not metrics:
                return {
                    'total_metrics': 0,
                    'execution_times': {},
                    'memory_usage': {},
                    'success_rate': 0,
                    'error_count': 0
                }
            
            # Group metrics by type
            exec_times = [m.metric_value for m in metrics 
                         if m.metric_type == MetricType.EXECUTION_TIME.value]
            memory_values = [m.metric_value for m in metrics 
                            if m.metric_type == MetricType.MEMORY_USED.value]
            cpu_values = [m.metric_value for m in metrics 
                         if m.metric_type == MetricType.CPU_USAGE.value]
            
            # Calculate stats
            def calc_stats(values):
                if not values:
                    return None
                return {
                    'min': min(values),
                    'max': max(values),
                    'avg': sum(values) / len(values),
                    'median': statistics.median(values),
                    'stdev': statistics.stdev(values) if len(values) > 1 else 0,
                    'count': len(values)
                }
            
            success_count = sum(1 for m in metrics if m.success)
            error_count = len(metrics) - success_count
            
            return {
                'total_metrics': len(metrics),
                'execution_times': calc_stats(exec_times) or {},
                'memory_usage': calc_stats(memory_values) or {},
                'cpu_usage': calc_stats(cpu_values) or {},
                'success_rate': (success_count / len(metrics) * 100) if metrics else 0,
                'error_count': error_count,
                'recorded_at': self._utcnow().isoformat()
            }
        except Exception as e:
            return {'error': str(e)}
    
    def analyze_trends(self, plugin_id, metric_type, days=7):
        """
        Analyze performance trends for a plugin over time.
        
        Args:
            plugin_id: Plugin ID
            metric_type: Type of metric to analyze
            days: Number of days to analyze
            
        Returns:
            dict: Trend data with slope, direction, etc
        """
        try:
            since_date = self._utcnow() - timedelta(days=days)
            
            metrics = JobMetrics.query.filter(
                and_(
                    JobMetrics.plugin_id == plugin_id,
                    JobMetrics.metric_type == metric_type,
                    JobMetrics.recorded_at >= since_date
                )
            ).all()
            
            if not metrics:
                return {'message': 'No data available', 'data_points': 0}
            
            values = [m.metric_value for m in metrics]
            
            # Calculate trend: simple linear regression
            n = len(values)
            if n < 2:
                return {
                    'trend': 'stable',
                    'direction': 'flat',
                    'first_value': values[0],
                    'last_value': values[0],
                    'change_percent': 0,
                    'data_points': n
                }
            
            # Calculate slope
            x = list(range(n))
            x_mean = sum(x) / n
            y_mean = sum(values) / n
            
            numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
            denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
            
            slope = numerator / denominator if denominator != 0 else 0
            
            # Determine trend
            change_percent = ((values[-1] - values[0]) / values[0] * 100) if values[0] != 0 else 0
            
            trend = 'improving' if slope < 0 else 'degrading' if slope > 0 else 'stable'
            direction = 'down' if slope < 0 else 'up' if slope > 0 else 'flat'
            
            return {
                'metric_type': metric_type,
                'days_analyzed': days,
                'data_points': n,
                'first_value': values[0],
                'last_value': values[-1],
                'min_value': min(values),
                'max_value': max(values),
                'avg_value': sum(values) / n,
                'slope': slope,
                'trend': trend,
                'direction': direction,
                'change_percent': change_percent,
                'calculated_at': self._utcnow().isoformat()
            }
        except Exception as e:
            return {'error': str(e)}
    
    def create_performance_benchmark(self, plugin_id, plugin_name):
        """
        Create or update performance benchmark for a plugin.
        
        Args:
            plugin_id: Plugin ID
            plugin_name: Plugin name
            
        Returns:
            tuple: (success, message, benchmark_id)
        """
        try:
            # Get recent metrics for this plugin
            recent_date = self._utcnow() - timedelta(days=30)
            metrics = JobMetrics.query.filter(
                and_(
                    JobMetrics.plugin_id == plugin_id,
                    JobMetrics.recorded_at >= recent_date
                )
            ).all()
            
            if not metrics:
                return False, "No metrics available for plugin", None
            
            # Calculate statistics
            exec_times = [m.metric_value for m in metrics 
                         if m.metric_type == MetricType.EXECUTION_TIME.value]
            memory_values = [m.metric_value for m in metrics 
                            if m.metric_type == MetricType.MEMORY_USED.value]
            
            def safe_calc(values):
                if not values:
                    return 0, float('inf'), float('-inf')
                return sum(values) / len(values), min(values), max(values)
            
            exec_avg, exec_min, exec_max = safe_calc(exec_times)
            mem_avg, _, mem_max = safe_calc(memory_values)
            
            success_count = sum(1 for m in metrics if m.success)
            success_rate = (success_count / len(metrics) * 100) if metrics else 0
            
            # Create or update benchmark
            benchmark = PerformanceBenchmark.query.filter_by(plugin_id=plugin_id).first()
            
            if benchmark:
                benchmark.plugin_name = plugin_name
                benchmark.avg_execution_time = exec_avg
                benchmark.min_execution_time = exec_min if exec_min != float('inf') else None
                benchmark.max_execution_time = exec_max if exec_max != float('-inf') else None
                benchmark.avg_memory_used = mem_avg
                benchmark.max_memory_used = mem_max if mem_max != float('-inf') else None
                benchmark.success_rate = success_rate
                benchmark.failure_rate = 100 - success_rate
                benchmark.total_executions += len(metrics)
                benchmark.recent_execution_count = len(metrics)
            else:
                benchmark = PerformanceBenchmark(
                    plugin_id=plugin_id,
                    plugin_name=plugin_name,
                    avg_execution_time=exec_avg,
                    min_execution_time=exec_min if exec_min != float('inf') else None,
                    max_execution_time=exec_max if exec_max != float('-inf') else None,
                    avg_memory_used=mem_avg,
                    max_memory_used=mem_max if mem_max != float('-inf') else None,
                    success_rate=success_rate,
                    failure_rate=100 - success_rate,
                    total_executions=len(metrics),
                    recent_execution_count=len(metrics)
                )
                db.session.add(benchmark)
            
            db.session.commit()
            return True, "Benchmark created/updated successfully", benchmark.id
        except Exception as e:
            db.session.rollback()
            return False, f"Failed to create benchmark: {str(e)}", None
    
    # ==================== Health Tracking ====================
    
    def update_system_health(self):
        """
        Sample and record current system health metrics.
        
        Returns:
            tuple: (success, message, health_id)
        """
        try:
            if not self.psutil_available:
                return False, "psutil not available", None
            
            # Gather system metrics
            memory = self.psutil.virtual_memory()
            cpu_percent = self.psutil.cpu_percent(interval=0.1)
            thread_count = self.psutil.active_children().__len__() if hasattr(self.psutil, 'active_children') else 0
            
            # Get job statistics
            today = self._utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            completed_today = BatchJob.query.filter(
                and_(
                    BatchJob.created_at >= today,
                    BatchJob.status == self._status_enum_value('completed')
                )
            ).count()
            
            failed_today = BatchJob.query.filter(
                and_(
                    BatchJob.created_at >= today,
                    BatchJob.status == self._status_enum_value('failed')
                )
            ).count()
            
            active_jobs = BatchJob.query.filter(
                BatchJob.status == self._status_enum_value('running')
            ).count()
            
            total_jobs = BatchJob.query.count()
            
            # Calculate error rate
            all_metrics = JobMetrics.query.filter(
                JobMetrics.recorded_at >= (self._utcnow() - timedelta(hours=1))
            ).all()
            
            error_rate = 0
            if all_metrics:
                errors = sum(1 for m in all_metrics if not m.success)
                error_rate = (errors / len(all_metrics) * 100) if all_metrics else 0
            
            # Determine overall status
            status = HealthStatus.HEALTHY.value
            if memory.percent > 80 or cpu_percent > 80:
                status = HealthStatus.CRITICAL.value
            elif memory.percent > 70 or cpu_percent > 70:
                status = HealthStatus.UNHEALTHY.value
            elif memory.percent > 60 or cpu_percent > 60:
                status = HealthStatus.DEGRADED.value
            
            # Create health record
            health = SystemHealth(
                memory_used_mb=memory.used / (1024 ** 2),
                memory_available_mb=memory.available / (1024 ** 2),
                memory_usage_percent=memory.percent,
                cpu_usage_percent=cpu_percent,
                active_thread_count=thread_count,
                active_jobs=active_jobs,
                completed_jobs_today=completed_today,
                failed_jobs_today=failed_today,
                total_jobs_processed=total_jobs,
                error_rate_percent=error_rate,
                overall_status=status
            )
            
            db.session.add(health)
            db.session.commit()
            
            # Check if health indicates alerts needed
            self._check_system_alerts(health)
            
            return True, "System health recorded", health.id
        except Exception as e:
            db.session.rollback()
            return False, f"Failed to record system health: {str(e)}", None
    
    def get_system_health(self, hours=1):
        """
        Get system health snapshot from the last N hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            dict: Latest system health data
        """
        try:
            since = self._utcnow() - timedelta(hours=hours)
            
            latest = SystemHealth.query.filter(
                SystemHealth.recorded_at >= since
            ).order_by(desc(SystemHealth.recorded_at)).first()
            
            if not latest:
                return {'message': 'No health data available'}
            
            return latest.to_dict()
        except Exception as e:
            return {'error': str(e)}
    
    def get_system_health_history(self, hours=24, limit=100):
        """
        Get system health history.
        
        Args:
            hours: Hours to look back
            limit: Max records to return
            
        Returns:
            list: Health data points
        """
        try:
            since = self._utcnow() - timedelta(hours=hours)
            
            records = SystemHealth.query.filter(
                SystemHealth.recorded_at >= since
            ).order_by(desc(SystemHealth.recorded_at)).limit(limit).all()
            
            return [r.to_dict() for r in records]
        except Exception as e:
            return {'error': str(e)}
    
    # ==================== Alerting ====================
    
    def check_performance_alerts(self):
        """
        Check for performance threshold violations and create alerts.
        
        Returns:
            tuple: (success, message, alerts_created_count)
        """
        try:
            alerts_created = 0
            configs = AlertConfiguration.query.filter_by(enabled=True).all()
            
            for config in configs:
                # Get recent metrics for this check
                since = self._utcnow() - timedelta(hours=1)
                metrics = JobMetrics.query.filter(
                    and_(
                        JobMetrics.metric_type == config.metric_name,
                        JobMetrics.recorded_at >= since
                    )
                ).all()
                
                for metric in metrics:
                    alert = None
                    severity = AlertSeverity.LOW.value
                    
                    # Check thresholds
                    if metric.metric_value >= config.critical_threshold:
                        severity = AlertSeverity.CRITICAL.value
                        alert = PerformanceAlert(
                            alert_type=config.alert_type,
                            severity=severity,
                            status=AlertStatus.ACTIVE.value,
                            metric_name=config.metric_name,
                            threshold_value=config.critical_threshold,
                            current_value=metric.metric_value,
                            plugin_id=metric.plugin_id,
                            plugin_name=metric.plugin_name,
                            job_id=metric.batch_job_id,
                            title=f"Critical Alert: {config.alert_type}",
                            description=f"{config.metric_name} = {metric.metric_value} exceeds critical threshold {config.critical_threshold}"
                        )
                    elif metric.metric_value >= config.warning_threshold:
                        severity = AlertSeverity.HIGH.value
                        alert = PerformanceAlert(
                            alert_type=config.alert_type,
                            severity=severity,
                            status=AlertStatus.ACTIVE.value,
                            metric_name=config.metric_name,
                            threshold_value=config.warning_threshold,
                            current_value=metric.metric_value,
                            plugin_id=metric.plugin_id,
                            plugin_name=metric.plugin_name,
                            job_id=metric.batch_job_id,
                            title=f"Warning Alert: {config.alert_type}",
                            description=f"{config.metric_name} = {metric.metric_value} exceeds warning threshold {config.warning_threshold}"
                        )
                    
                    if alert:
                        db.session.add(alert)
                        alerts_created += 1
            
            db.session.commit()
            return True, f"Alert check completed, {alerts_created} alerts created", alerts_created
        except Exception as e:
            db.session.rollback()
            return False, f"Failed to check alerts: {str(e)}", 0
    
    def _check_system_alerts(self, health):
        """
        Internal method to check system health and create alerts.
        
        Args:
            health: SystemHealth record
        """
        try:
            # Check CPU alert
            if health.cpu_usage_percent > 80:
                alert = PerformanceAlert(
                    alert_type=AlertType.HIGH_CPU.value,
                    severity=AlertSeverity.CRITICAL.value,
                    status=AlertStatus.ACTIVE.value,
                    metric_name='cpu_usage',
                    threshold_value=80,
                    current_value=health.cpu_usage_percent,
                    title="Critical: High CPU Usage",
                    description=f"CPU usage at {health.cpu_usage_percent}%"
                )
                db.session.add(alert)
            
            # Check memory alert
            if health.memory_usage_percent > 85:
                alert = PerformanceAlert(
                    alert_type=AlertType.HIGH_MEMORY.value,
                    severity=AlertSeverity.CRITICAL.value,
                    status=AlertStatus.ACTIVE.value,
                    metric_name='memory_usage',
                    threshold_value=85,
                    current_value=health.memory_usage_percent,
                    title="Critical: High Memory Usage",
                    description=f"Memory usage at {health.memory_usage_percent}%"
                )
                db.session.add(alert)
            
            # Check error rate alert
            if health.error_rate_percent > 10:
                alert = PerformanceAlert(
                    alert_type=AlertType.HIGH_FAILURE_RATE.value,
                    severity=AlertSeverity.HIGH.value,
                    status=AlertStatus.ACTIVE.value,
                    metric_name='error_rate',
                    threshold_value=10,
                    current_value=health.error_rate_percent,
                    title="Warning: High Error Rate",
                    description=f"Error rate at {health.error_rate_percent}%"
                )
                db.session.add(alert)
            
            db.session.commit()
        except Exception:
            db.session.rollback()
    
    def get_performance_alerts(self, status=None, alert_type=None, severity=None, limit=100):
        """
        Query performance alerts with filtering.
        
        Args:
            status: Filter by status (active, acknowledged, resolved)
            alert_type: Filter by alert type
            severity: Filter by severity
            limit: Maximum records to return
            
        Returns:
            list: Alert records
        """
        try:
            query = PerformanceAlert.query
            
            if status:
                query = query.filter_by(status=status)
            if alert_type:
                query = query.filter_by(alert_type=alert_type)
            if severity:
                query = query.filter_by(severity=severity)
            
            alerts = query.order_by(desc(PerformanceAlert.created_at)).limit(limit).all()
            return [a.to_dict() for a in alerts]
        except Exception as e:
            return {'error': str(e)}
    
    def acknowledge_alert(self, alert_id):
        """
        Acknowledge a performance alert.
        
        Args:
            alert_id: Alert ID
            
        Returns:
            tuple: (success, message)
        """
        try:
            alert = db.session.get(PerformanceAlert, alert_id)
            if not alert:
                return False, "Alert not found"
            
            alert.acknowledge()
            db.session.commit()
            return True, "Alert acknowledged"
        except Exception as e:
            db.session.rollback()
            return False, f"Failed to acknowledge alert: {str(e)}"
    
    def resolve_alert(self, alert_id):
        """
        Resolve a performance alert.
        
        Args:
            alert_id: Alert ID
            
        Returns:
            tuple: (success, message)
        """
        try:
            alert = db.session.get(PerformanceAlert, alert_id)
            if not alert:
                return False, "Alert not found"
            
            alert.resolve()
            db.session.commit()
            return True, "Alert resolved"
        except Exception as e:
            db.session.rollback()
            return False, f"Failed to resolve alert: {str(e)}"
    
    # ==================== Dashboard & Reporting ====================
    
    def get_dashboard_metrics(self, timeframe='1h'):
        """
        Get aggregated metrics for dashboard display.
        
        Args:
            timeframe: '1h', '24h', '7d', '30d'
            
        Returns:
            dict: Dashboard metrics
        """
        try:
            # Calculate time delta
            delta_map = {
                '1h': timedelta(hours=1),
                '24h': timedelta(days=1),
                '7d': timedelta(days=7),
                '30d': timedelta(days=30)
            }
            delta = delta_map.get(timeframe, timedelta(hours=1))
            since = self._utcnow() - delta
            
            # Job statistics
            total_executed = BatchJob.query.filter(
                BatchJob.created_at >= since
            ).count()
            
            completed = BatchJob.query.filter(
                and_(
                    BatchJob.created_at >= since,
                    BatchJob.status == self._status_enum_value('completed')
                )
            ).count()
            
            failed = BatchJob.query.filter(
                and_(
                    BatchJob.created_at >= since,
                    BatchJob.status == self._status_enum_value('failed')
                )
            ).count()
            
            # Recent alerts
            recent_alerts = PerformanceAlert.query.filter(
                and_(
                    PerformanceAlert.created_at >= since,
                    PerformanceAlert.status == AlertStatus.ACTIVE.value
                )
            ).count()
            
            # System health
            latest_health = SystemHealth.query.order_by(
                desc(SystemHealth.recorded_at)
            ).first()
            
            return {
                'timeframe': timeframe,
                'stats': {
                    'total_jobs': total_executed,
                    'completed_jobs': completed,
                    'failed_jobs': failed,
                    'success_rate': (completed / total_executed * 100) if total_executed > 0 else 0,
                    'active_alerts': recent_alerts
                },
                'system_health': latest_health.to_dict() if latest_health else None,
                'calculated_at': self._utcnow().isoformat()
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_plugin_performance_report(self, plugin_id, days=30):
        """
        Generate comprehensive performance report for a plugin.
        
        Args:
            plugin_id: Plugin ID
            days: Days to analyze
            
        Returns:
            dict: Performance report
        """
        try:
            since = self._utcnow() - timedelta(days=days)
            
            # Get benchmark
            benchmark = PerformanceBenchmark.query.filter_by(plugin_id=plugin_id).first()
            
            # Get recent metrics
            metrics = JobMetrics.query.filter(
                and_(
                    JobMetrics.plugin_id == plugin_id,
                    JobMetrics.recorded_at >= since
                )
            ).all()
            
            if not metrics:
                return {'message': 'No data available for plugin'}
            
            # Analyze trends
            trends = self.analyze_trends(plugin_id, MetricType.EXECUTION_TIME.value, days)
            
            return {
                'plugin_id': plugin_id,
                'days_analyzed': days,
                'total_executions': len(metrics),
                'benchmark': benchmark.to_dict() if benchmark else None,
                'recent_trends': trends,
                'metric_count': len(metrics),
                'report_date': self._utcnow().isoformat()
            }
        except Exception as e:
            return {'error': str(e)}

    @staticmethod
    def _status_enum_value(name: str):
        from app.models.researcher.batch_operations import BatchJobStatus
        return getattr(BatchJobStatus, name.lower()).value


# Singleton instance
monitoring_service = MonitoringService()

