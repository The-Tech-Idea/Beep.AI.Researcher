"""Real-time monitoring data models for Phase 4.3."""
from datetime import datetime, timedelta, UTC
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, 
    Boolean, JSON, Index, and_, func
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from enum import Enum
from app.database import db


def _utcnow():
    return datetime.now(UTC).replace(tzinfo=None)

# Enums for monitoring
class MetricType(Enum):
    """Types of metrics that can be tracked."""
    EXECUTION_TIME = "execution_time"  # milliseconds
    MEMORY_USED = "memory_used"        # megabytes
    CPU_USAGE = "cpu_usage"            # percentage
    RESULT_SIZE = "result_size"        # kilobytes
    NETWORK_LATENCY = "network_latency"  # milliseconds
    RECORD_COUNT = "record_count"      # count


class AlertType(Enum):
    """Types of performance alerts."""
    HIGH_CPU = "high_cpu"
    HIGH_MEMORY = "high_memory"
    JOB_TIMEOUT = "job_timeout"
    HIGH_FAILURE_RATE = "high_failure_rate"
    PLUGIN_DEGRADATION = "plugin_degradation"
    RESPONSE_TIME = "response_time"
    ERROR_SPIKE = "error_spike"


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status tracking."""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class HealthStatus(Enum):
    """System health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


class JobMetrics(db.Model):
    """Track metrics for individual batch jobs and plugin executions."""
    
    __tablename__ = 'job_metrics'
    
    id = Column(Integer, primary_key=True)
    batch_job_id = Column(Integer, ForeignKey('batch_job.id', ondelete='CASCADE'), nullable=False, index=True)
    plugin_id = Column(Integer, nullable=True, index=True)
    plugin_name = Column(String(255), nullable=True)
    
    # Metric data
    metric_type = Column(String(50), nullable=False, index=True)  # execution_time, memory, cpu, etc
    metric_value = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)  # ms, MB, %, count, etc
    
    # Context
    record_index = Column(Integer, nullable=True)  # Which record in batch
    operation_type = Column(String(100), nullable=True)  # plugin_execution, data_transfer, etc
    
    # Metadata
    recorded_at = Column(DateTime, default=_utcnow, nullable=False, index=True)
    success = Column(Boolean, default=True)  # Whether the operation succeeded
    error_message = Column(String(500), nullable=True)  # Error if failed
    
    # Relationships
    batch_job = relationship('BatchJob', back_populates='metrics')
    
    def __repr__(self):
        return f"<JobMetrics {self.metric_type}={self.metric_value}{self.unit}>"
    
    def to_dict(self):
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'batch_job_id': self.batch_job_id,
            'plugin_id': self.plugin_id,
            'plugin_name': self.plugin_name,
            'metric_type': self.metric_type,
            'metric_value': self.metric_value,
            'unit': self.unit,
            'record_index': self.record_index,
            'operation_type': self.operation_type,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None,
            'success': self.success,
            'error_message': self.error_message
        }


class PerformanceBenchmark(db.Model):
    """Store performance benchmarks for plugins."""
    
    __tablename__ = 'performance_benchmark'
    __table_args__ = (
        Index('idx_plugin_id', 'plugin_id'),
    )
    
    id = Column(Integer, primary_key=True)
    plugin_id = Column(Integer, nullable=False, unique=True, index=True)
    plugin_name = Column(String(255), nullable=False)
    
    # Metric aggregates
    avg_execution_time = Column(Float, nullable=True)  # ms
    min_execution_time = Column(Float, nullable=True)  # ms
    max_execution_time = Column(Float, nullable=True)  # ms
    std_dev_execution_time = Column(Float, nullable=True)  # Standard deviation
    
    avg_memory_used = Column(Float, nullable=True)  # MB
    max_memory_used = Column(Float, nullable=True)  # MB
    
    success_rate = Column(Float, nullable=True)  # Percentage 0-100
    failure_rate = Column(Float, nullable=True)  # Percentage 0-100
    
    # Statistical data
    total_executions = Column(Integer, default=0)
    recent_execution_count = Column(Integer, default=0)  # Last 100 executions
    
    # Metadata
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    last_updated = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<PerformanceBenchmark plugin_id={self.plugin_id} avg_time={self.avg_execution_time}ms>"
    
    def to_dict(self):
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'plugin_id': self.plugin_id,
            'plugin_name': self.plugin_name,
            'avg_execution_time': self.avg_execution_time,
            'min_execution_time': self.min_execution_time,
            'max_execution_time': self.max_execution_time,
            'std_dev_execution_time': self.std_dev_execution_time,
            'avg_memory_used': self.avg_memory_used,
            'max_memory_used': self.max_memory_used,
            'success_rate': self.success_rate,
            'failure_rate': self.failure_rate,
            'total_executions': self.total_executions,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }


class SystemHealth(db.Model):
    """Track overall system health and resource usage."""
    
    __tablename__ = 'system_health'
    __table_args__ = (
        Index('idx_timestamp', 'recorded_at'),
    )
    
    id = Column(Integer, primary_key=True)
    
    # Memory metrics
    memory_used_mb = Column(Float, nullable=False)  # Current memory usage
    memory_available_mb = Column(Float, nullable=False)  # Available memory
    memory_usage_percent = Column(Float, nullable=False)  # Percentage used
    
    # CPU metrics
    cpu_usage_percent = Column(Float, nullable=False)
    active_thread_count = Column(Integer, nullable=False)
    
    # Job metrics
    active_jobs = Column(Integer, default=0)
    completed_jobs_today = Column(Integer, default=0)
    failed_jobs_today = Column(Integer, default=0)
    total_jobs_processed = Column(Integer, default=0)
    
    # Performance metrics
    error_rate_percent = Column(Float, default=0.0)
    avg_response_time_ms = Column(Float, default=0.0)
    requests_per_minute = Column(Float, default=0.0)
    
    # Status
    overall_status = Column(String(20), default='healthy')  # healthy, degraded, unhealthy, critical
    
    # Metadata
    recorded_at = Column(DateTime, default=_utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<SystemHealth {self.overall_status} @ {self.recorded_at}>"
    
    def to_dict(self):
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'memory_used_mb': self.memory_used_mb,
            'memory_available_mb': self.memory_available_mb,
            'memory_usage_percent': self.memory_usage_percent,
            'cpu_usage_percent': self.cpu_usage_percent,
            'active_thread_count': self.active_thread_count,
            'active_jobs': self.active_jobs,
            'completed_jobs_today': self.completed_jobs_today,
            'failed_jobs_today': self.failed_jobs_today,
            'error_rate_percent': self.error_rate_percent,
            'avg_response_time_ms': self.avg_response_time_ms,
            'requests_per_minute': self.requests_per_minute,
            'overall_status': self.overall_status,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None
        }
    
    def get_health_color(self):
        """Get status color for UI (green, yellow, red, darkred)."""
        status_map = {
            HealthStatus.HEALTHY.value: 'green',
            HealthStatus.DEGRADED.value: 'yellow',
            HealthStatus.UNHEALTHY.value: 'red',
            HealthStatus.CRITICAL.value: 'darkred'
        }
        return status_map.get(self.overall_status, 'green')


class PerformanceAlert(db.Model):
    """Track performance alerts and anomalies."""
    
    __tablename__ = 'performance_alert'
    __table_args__ = (
        Index('idx_status_created', 'status', 'created_at'),
        Index('idx_type_severity', 'alert_type', 'severity'),
    )
    
    id = Column(Integer, primary_key=True)
    
    # Alert info
    alert_type = Column(String(50), nullable=False, index=True)  # high_cpu, memory, timeout, etc
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    status = Column(String(20), default='active', nullable=False, index=True)  # active, acknowledged, resolved
    
    # What triggered the alert
    metric_name = Column(String(100), nullable=False)
    threshold_value = Column(Float, nullable=False)
    current_value = Column(Float, nullable=False)
    
    # Additional context
    plugin_id = Column(Integer, nullable=True, index=True)
    plugin_name = Column(String(255), nullable=True)
    job_id = Column(Integer, ForeignKey('batch_job.id', ondelete='SET NULL'), nullable=True)
    
    # Message
    title = Column(String(255), nullable=False)
    description = Column(String(500), nullable=True)
    
    # Lifecycle
    created_at = Column(DateTime, default=_utcnow, nullable=False, index=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    
    # Metadata
    notification_sent = Column(Boolean, default=False)
    extra_data = Column(JSON, nullable=True)  # Additional context
    
    def __repr__(self):
        return f"<PerformanceAlert {self.alert_type} severity={self.severity} status={self.status}>"
    
    def acknowledge(self):
        """Mark alert as acknowledged."""
        self.status = AlertStatus.ACKNOWLEDGED.value
        self.acknowledged_at = _utcnow()
    
    def resolve(self):
        """Mark alert as resolved."""
        self.status = AlertStatus.RESOLVED.value
        self.resolved_at = _utcnow()
    
    def to_dict(self):
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'alert_type': self.alert_type,
            'severity': self.severity,
            'status': self.status,
            'metric_name': self.metric_name,
            'threshold_value': self.threshold_value,
            'current_value': self.current_value,
            'plugin_id': self.plugin_id,
            'plugin_name': self.plugin_name,
            'job_id': self.job_id,
            'title': self.title,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'notification_sent': self.notification_sent
        }


class AlertConfiguration(db.Model):
    """Configure alert thresholds and rules."""
    
    __tablename__ = 'alert_configuration'
    
    id = Column(Integer, primary_key=True)
    
    # What to alert on
    alert_type = Column(String(50), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False)
    
    # Thresholds
    warning_threshold = Column(Float, nullable=False)  # yellow alert
    critical_threshold = Column(Float, nullable=False)  # red alert
    
    # Behavior
    enabled = Column(Boolean, default=True)
    notify_via_email = Column(Boolean, default=False)
    notify_via_webhook = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    update_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)
    
    def __repr__(self):
        return f"<AlertConfiguration {self.alert_type} warn={self.warning_threshold} crit={self.critical_threshold}>"
    
    def to_dict(self):
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'alert_type': self.alert_type,
            'metric_name': self.metric_name,
            'warning_threshold': self.warning_threshold,
            'critical_threshold': self.critical_threshold,
            'enabled': self.enabled,
            'notify_via_email': self.notify_via_email,
            'notify_via_webhook': self.notify_via_webhook
        }


class AuditMetrics(db.Model):
    """Audit trail of system operations with timing."""
    
    __tablename__ = 'audit_metrics'
    __table_args__ = (
        Index('idx_operation_timestamp', 'operation_type', 'recorded_at'),
        Index('idx_user_timestamp', 'user_id', 'recorded_at'),
    )
    
    id = Column(Integer, primary_key=True)
    
    # Operation info
    operation_type = Column(String(100), nullable=False, index=True)  # plugin_execution, permission_check, batch_job, etc
    status = Column(String(20), nullable=False)  # success, failure
    
    # Performance
    duration_ms = Column(Float, nullable=False)  # How long the operation took
    
    # Statistics
    success_count = Column(Integer, default=1)
    failure_count = Column(Integer, default=0)
    total_count = Column(Integer, default=1)
    
    # User/Context
    user_id = Column(Integer, nullable=True, index=True)
    resource_id = Column(String(100), nullable=True)  # plugin_id, job_id, etc
    resource_type = Column(String(50), nullable=True)  # plugin, batch_job, etc
    
    # Result
    error_message = Column(String(500), nullable=True)
    
    # Metadata
    recorded_at = Column(DateTime, default=_utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<AuditMetrics {self.operation_type} {self.status} {self.duration_ms}ms>"
    
    def to_dict(self):
        """Serialize to dictionary."""
        return {
            'id': self.id,
            'operation_type': self.operation_type,
            'status': self.status,
            'duration_ms': self.duration_ms,
            'user_id': self.user_id,
            'resource_id': self.resource_id,
            'resource_type': self.resource_type,
            'error_message': self.error_message,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None
        }


# Add relationship to BatchJob model if it exists
# This assumes BatchJob model exists in batch_operations.py
try:
    from app.models.researcher.batch_operations import BatchJob
    BatchJob.metrics = relationship('JobMetrics', back_populates='batch_job', cascade='all, delete-orphan')
except ImportError:
    pass
