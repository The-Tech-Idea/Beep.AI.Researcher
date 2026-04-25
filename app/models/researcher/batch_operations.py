"""Batch operation models for Phase 4.2."""
from datetime import datetime
from app.core.time_utils import utcnow_naive
from enum import Enum
from app.database import db
import json
from sqlalchemy.orm import validates


class BatchJobStatus(Enum):
    """Status of a batch job."""
    pending = 'pending'           # Job created, not started
    running = 'running'           # Currently executing
    paused = 'paused'             # Execution paused
    completed = 'completed'       # Finished successfully
    failed = 'failed'             # Finished with errors
    cancelled = 'cancelled'       # User cancelled


class ExportFormat(Enum):
    """Export format for results."""
    csv = 'csv'
    json = 'json'
    xlsx = 'xlsx'


class BatchJob(db.Model):
    """Batch operation job for parallel plugin execution."""
    __tablename__ = 'batch_job'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Basic info
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    
    # Configuration (stored as JSON)
    plugins_config = db.Column(db.JSON, default=dict)  # [{plugin_id, options}, ...]
    data_filters = db.Column(db.JSON, default=dict)    # Filtering criteria
    source_data_type = db.Column(db.String(50))      # extraction_result, classification_result
    source_data_id = db.Column(db.Integer)           # ID of source data
    
    # Status tracking
    status = db.Column(
        db.Enum(
            BatchJobStatus,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            native_enum=False
        ),
        default=BatchJobStatus.pending,
        nullable=False
    )
    progress = db.Column(db.Float, default=0.0)      # 0-100
    
    # Processing details
    total_records = db.Column(db.Integer, default=0)
    processed_records = db.Column(db.Integer, default=0)
    successful_records = db.Column(db.Integer, default=0)
    failed_records = db.Column(db.Integer, default=0)
    
    # Export configuration
    export_format = db.Column(db.String(10))         # csv, json, xlsx
    export_file_path = db.Column(db.String(500))     # Path to exported file
    export_file_size = db.Column(db.BigInteger)      # Size in bytes
    
    # Error tracking
    error_message = db.Column(db.Text)
    error_details = db.Column(db.JSON)               # Detailed error info
    
    # Timing
    created_at = db.Column(db.DateTime, default=utcnow_naive, index=True)
    started_at = db.Column(db.DateTime)
    paused_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Estimated duration (in seconds)
    estimated_duration = db.Column(db.Integer)
    actual_duration = db.Column(db.Integer)
    
    # Relationships
    user = db.relationship('User', backref='batch_jobs')
    job_results = db.relationship('BatchJobResult', backref='batch_job', cascade='all, delete-orphan')

    @validates('status')
    def _validate_status(self, _, value):
        if isinstance(value, BatchJobStatus):
            return value
        if isinstance(value, str):
            normalized = value.lower()
            for status in BatchJobStatus:
                if status.value == normalized:
                    return status
        return BatchJobStatus.pending
    
    def __repr__(self):
        return f'<BatchJob {self.id} {self.name} status={self.status}>'
    
    def to_dict(self, include_results=False):
        """Convert to dictionary."""
        status = self.status.value if isinstance(self.status, BatchJobStatus) else self.status
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'status': status,
            'progress': self.progress,
            'total_records': self.total_records,
            'processed_records': self.processed_records,
            'successful_records': self.successful_records,
            'failed_records': self.failed_records,
            'export_format': self.export_format,
            'export_file_path': self.export_file_path,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'estimated_duration': self.estimated_duration,
            'actual_duration': self.actual_duration,
        }
        
        if include_results:
            data['results'] = [r.to_dict() for r in self.job_results]
        
        return data
    
    def get_estimated_time_remaining(self) -> int:
        """Get estimated remaining time in seconds."""
        if self.progress <= 0:
            return 0

        # If estimated_duration is not set, derive it from runtime and progress.
        if not self.estimated_duration and self.started_at:
            elapsed = max((utcnow_naive() - self.started_at).total_seconds(), 1)
            completion_ratio = max(self.progress / 100.0, 0.01)
            estimated_total = elapsed / completion_ratio
            return max(int(estimated_total - elapsed), 0)
        if not self.estimated_duration:
            return 0
        
        elapsed_multiplier = max(self.progress / 100.0, 0.01)
        total_estimated = self.estimated_duration / elapsed_multiplier
        remaining = total_estimated - self.estimated_duration
        
        return max(int(remaining), 0)
    
    def mark_started(self):
        """Mark job as started."""
        self.started_at = utcnow_naive()
        self.status = BatchJobStatus.running
        db.session.commit()
    
    def mark_completed(self):
        """Mark job as completed."""
        self.completed_at = utcnow_naive()
        self.progress = 100.0
        self.status = BatchJobStatus.completed
        
        if self.started_at:
            self.actual_duration = int((self.completed_at - self.started_at).total_seconds())
        
        db.session.commit()
    
    def mark_failed(self, error_message: str, details: dict = None):
        """Mark job as failed."""
        self.completed_at = utcnow_naive()
        self.status = BatchJobStatus.failed
        self.error_message = error_message
        self.error_details = details
        
        if self.started_at:
            self.actual_duration = int((self.completed_at - self.started_at).total_seconds())
        
        db.session.commit()
    
    def mark_paused(self):
        """Mark job as paused."""
        self.paused_at = utcnow_naive()
        self.status = BatchJobStatus.paused
        db.session.commit()
    
    def mark_cancelled(self):
        """Mark job as cancelled."""
        self.completed_at = utcnow_naive()
        self.status = BatchJobStatus.cancelled
        
        if self.started_at:
            self.actual_duration = int((self.completed_at - self.started_at).total_seconds())
        
        db.session.commit()
    
    def update_progress(self, processed: int, successful: int, failed: int):
        """Update job progress."""
        self.processed_records = processed
        self.successful_records = successful
        self.failed_records = failed
        
        if self.total_records > 0:
            self.progress = min(100.0, (processed / self.total_records) * 100)
        
        db.session.commit()


class BatchJobResult(db.Model):
    """Individual result from a batch job."""
    __tablename__ = 'batch_job_result'
    
    id = db.Column(db.Integer, primary_key=True)
    batch_job_id = db.Column(db.Integer, db.ForeignKey('batch_job.id'), nullable=False, index=True)
    
    # Record info
    record_index = db.Column(db.Integer)            # Position in source data
    source_record_id = db.Column(db.Integer)        # ID of source record
    
    # Plugin info
    plugin_id = db.Column(db.Integer, db.ForeignKey('plugins.id'), nullable=False)
    plugin_name = db.Column(db.String(255))
    
    # Execution result
    success = db.Column(db.Boolean, default=False)
    result_data = db.Column(db.JSON)                # Plugin result
    error_message = db.Column(db.Text)
    execution_time_ms = db.Column(db.Float)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=utcnow_naive)
    
    # Relationships
    plugin = db.relationship('Plugin', backref='batch_results')
    
    def __repr__(self):
        return f'<BatchJobResult batch={self.batch_job_id} plugin={self.plugin_id}>'
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'batch_job_id': self.batch_job_id,
            'record_index': self.record_index,
            'plugin_id': self.plugin_id,
            'plugin_name': self.plugin_name,
            'success': self.success,
            'result_data': self.result_data,
            'error_message': self.error_message,
            'execution_time_ms': self.execution_time_ms,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class BatchJobLog(db.Model):
    """Detailed log entries for batch job execution."""
    __tablename__ = 'batch_job_log'
    
    id = db.Column(db.Integer, primary_key=True)
    batch_job_id = db.Column(db.Integer, db.ForeignKey('batch_job.id'), nullable=False, index=True)
    
    # Log info
    level = db.Column(db.String(20))                # info, warning, error, debug
    message = db.Column(db.Text)
    
    # Context
    record_index = db.Column(db.Integer)
    plugin_id = db.Column(db.Integer)
    plugin_name = db.Column(db.String(255))
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=utcnow_naive, index=True)
    
    # Relationships
    batch_job = db.relationship('BatchJob', backref='logs')
    
    def __repr__(self):
        return f'<BatchJobLog batch={self.batch_job_id} level={self.level}>'
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'batch_job_id': self.batch_job_id,
            'level': self.level,
            'message': self.message,
            'record_index': self.record_index,
            'plugin_id': self.plugin_id,
            'plugin_name': self.plugin_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
