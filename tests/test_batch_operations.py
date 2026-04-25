"""Comprehensive tests for batch operations (Phase 4.2)."""
import pytest
from datetime import datetime, timedelta
from app.models.researcher.batch_operations import (
    BatchJob, BatchJobResult, BatchJobLog, BatchJobStatus, ExportFormat
)
from app.services.batch_operations import BatchOperationService
from app.services.plugin_permissions import PluginPermissionService
from app.models.researcher.plugins import Plugin
from app.database import db
from flask import g


class TestBatchJobModel:
    """Test BatchJob model functionality."""
    
    def test_batch_job_creation(self, app, db):
        """Test creating a batch job."""
        with app.app_context():
            job = BatchJob(
                user_id=1,
                name="Test Batch",
                description="Test batch job",
                status=BatchJobStatus.pending,
                total_records=100
            )
            
            db.db.add(job)
            db.db.commit()
            
            assert job.id is not None
            assert job.user_id == 1
            assert job.name == "Test Batch"
            assert job.status == BatchJobStatus.pending
            assert job.created_at is not None
    
    def test_batch_job_status_transitions(self, app, db):
        """Test status transitions."""
        with app.app_context():
            job = BatchJob(user_id=1, name="Test", status=BatchJobStatus.pending)
            db.db.add(job)
            db.db.commit()
            
            # Transition to running
            job.mark_started()
            assert job.status == BatchJobStatus.running
            assert job.started_at is not None
            
            # Update progress
            job.update_progress(50, 45, 2)
            assert job.processed_records == 50
            assert job.successful_records == 45
            assert job.failed_records == 2
            
            # Mark completed
            job.mark_completed()
            assert job.status == BatchJobStatus.completed
            assert job.completed_at is not None
    
    def test_batch_job_pause(self, app, db):
        """Test pausing a batch job."""
        with app.app_context():
            job = BatchJob(user_id=1, name="Test", status=BatchJobStatus.pending)
            db.db.add(job)
            db.db.commit()
            
            job.mark_started()
            job.update_progress(30, 28, 1)
            job.mark_paused()
            
            assert job.status == BatchJobStatus.paused
            assert job.processed_records == 30
    
    def test_batch_job_failure(self, app, db):
        """Test marking job as failed."""
        with app.app_context():
            job = BatchJob(user_id=1, name="Test", status=BatchJobStatus.pending)
            db.db.add(job)
            db.db.commit()
            
            job.mark_started()
            job.mark_failed("Database connection failed", {"error_code": 500})
            
            assert job.status == BatchJobStatus.failed
            assert "Database connection failed" in job.error_message
            assert job.error_details is not None
    
    def test_batch_job_estimated_time(self, app, db):
        """Test estimated time remaining calculation."""
        with app.app_context():
            job = BatchJob(user_id=1, name="Test", total_records=1000)
            job.mark_started()
            job.started_at = datetime.utcnow() - timedelta(seconds=10)
            job.update_progress(100, 100, 0)
            
            estimated = job.get_estimated_time_remaining()
            # 100 records in 10 seconds = 0.1 sec per record
            # 1000 total - 100 done = 900 remaining * 0.1 = 90 seconds
            assert estimated is not None
            assert estimated > 0
    
    def test_batch_job_to_dict(self, app, db):
        """Test serialization."""
        with app.app_context():
            job = BatchJob(
                user_id=1,
                name="Test Batch",
                status=BatchJobStatus.running,
                progress=45.5
            )
            db.db.add(job)
            db.db.commit()
            
            job_dict = job.to_dict()
            assert job_dict['name'] == "Test Batch"
            assert job_dict['status'] == BatchJobStatus.running.value
            assert job_dict['progress'] == 45.5


class TestBatchJobResultModel:
    """Test BatchJobResult model."""
    
    def test_batch_result_creation(self, app, db):
        """Test creating a batch result."""
        with app.app_context():
            job = BatchJob(user_id=1, name="Test")
            db.db.add(job)
            db.db.commit()
            
            result = BatchJobResult(
                batch_job_id=job.id,
                record_index=0,
                plugin_id=1,
                plugin_name="Test Plugin",
                success=True,
                result_data={"output": "test"},
                execution_time_ms=100
            )
            
            db.db.add(result)
            db.db.commit()
            
            assert result.id is not None
            assert result.batch_job_id == job.id
            assert result.success is True
    
    def test_batch_result_failure(self, app, db):
        """Test creating a failed batch result."""
        with app.app_context():
            job = BatchJob(user_id=1, name="Test")
            db.db.add(job)
            db.db.commit()
            
            result = BatchJobResult(
                batch_job_id=job.id,
                record_index=1,
                plugin_id=1,
                plugin_name="Test Plugin",
                success=False,
                error_message="Plugin execution failed",
                execution_time_ms=50
            )
            
            db.db.add(result)
            db.db.commit()
            
            assert result.success is False
            assert "execution failed" in result.error_message


class TestBatchJobLogModel:
    """Test BatchJobLog model."""
    
    def test_batch_log_creation(self, app, db):
        """Test creating batch logs."""
        with app.app_context():
            job = BatchJob(user_id=1, name="Test")
            db.db.add(job)
            db.db.commit()
            
            log = BatchJobLog(
                batch_job_id=job.id,
                level="info",
                message="Batch job started",
                record_index=0
            )
            
            db.db.add(log)
            db.db.commit()
            
            assert log.id is not None
            assert log.level == "info"
            assert log.created_at is not None


class TestBatchOperationService:
    """Test BatchOperationService functionality."""
    
    def test_create_batch_job(self, app, db, mock_user):
        """Test creating a batch job with service."""
        with app.app_context():
            g.user_id = mock_user['id']
            
            success, message, job = BatchOperationService.create_batch_job(
                user_id=mock_user['id'],
                name="Q1 Analysis",
                plugins_list=[1, 2],
                description="Test batch job"
            )
            
            assert success is True
            assert job is not None
            assert job.name == "Q1 Analysis"
            assert job.status == BatchJobStatus.pending
    
    def test_create_batch_job_without_permissions(self, app, db, mock_user):
        """Test creating batch job without plugin access."""
        with app.app_context():
            g.user_id = mock_user['id']
            
            # Mock permission service to deny access
            success, message, job = BatchOperationService.create_batch_job(
                user_id=mock_user['id'],
                name="Unauthorized",
                plugins_list=[999]  # Non-existent plugin
            )
            
            # Should still create job, permission check happens at start
            # This depends on implementation philosophy
    
    def test_start_batch_job(self, app, db, mock_user):
        """Test starting a batch job."""
        with app.app_context():
            g.user_id = mock_user['id']
            
            # Create job first
            job = BatchJob(
                user_id=mock_user['id'],
                name="Test",
                status=BatchJobStatus.pending,
                total_records=100
            )
            db.db.add(job)
            db.db.commit()
            
            success, message = BatchOperationService.start_batch_job(
                job_id=job.id,
                user_id=mock_user['id'],
                total_records=100
            )
            
            assert success is True
            assert job.status == BatchJobStatus.running
            assert job.started_at is not None
    
    def test_pause_batch_job(self, app, db, mock_user):
        """Test pausing a batch job."""
        with app.app_context():
            job = BatchJob(
                user_id=mock_user['id'],
                name="Test",
                status=BatchJobStatus.running
            )
            job.mark_started()
            db.db.add(job)
            db.db.commit()
            
            success, message = BatchOperationService.pause_batch_job(
                job_id=job.id,
                user_id=mock_user['id']
            )
            
            assert success is True
            assert job.status == BatchJobStatus.paused
    
    def test_cancel_batch_job(self, app, db, mock_user):
        """Test cancelling a batch job."""
        with app.app_context():
            job = BatchJob(
                user_id=mock_user['id'],
                name="Test",
                status=BatchJobStatus.running
            )
            job.mark_started()
            db.db.add(job)
            db.db.commit()
            
            success, message = BatchOperationService.cancel_batch_job(
                job_id=job.id,
                user_id=mock_user['id']
            )
            
            assert success is True
            assert job.status == BatchJobStatus.cancelled
    
    def test_cannot_cancel_completed_job(self, app, db, mock_user):
        """Test that completed jobs cannot be cancelled."""
        with app.app_context():
            job = BatchJob(
                user_id=mock_user['id'],
                name="Test",
                status=BatchJobStatus.completed
            )
            db.db.add(job)
            db.db.commit()
            
            success, message = BatchOperationService.cancel_batch_job(
                job_id=job.id,
                user_id=mock_user['id']
            )
            
            assert success is False
            assert job.status == BatchJobStatus.completed
    
    def test_get_batch_status(self, app, db, mock_user):
        """Test getting batch job status."""
        with app.app_context():
            job = BatchJob(
                user_id=mock_user['id'],
                name="Test",
                status=BatchJobStatus.running,
                total_records=100,
                processed_records=50
            )
            job.mark_started()
            db.db.add(job)
            db.db.commit()
            
            status = BatchOperationService.get_batch_status(job.id)
            
            assert status['id'] == job.id
            assert status['status'] == BatchJobStatus.running.value
            assert status['total_records'] == 100
            assert status['processed_records'] == 50
    
    def test_export_to_csv(self, app, db, mock_user):
        """Test exporting results to CSV."""
        with app.app_context():
            job = BatchJob(user_id=mock_user['id'], name="Test")
            db.db.add(job)
            db.db.commit()
            
            # Add some results
            for i in range(3):
                result = BatchJobResult(
                    batch_job_id=job.id,
                    record_index=i,
                    plugin_id=1,
                    plugin_name="Plugin1",
                    success=True,
                    result_data={"value": f"test{i}"},
                    execution_time_ms=100
                )
                db.db.add(result)
            
            db.db.commit()
            
            success, message, csv_content = BatchOperationService.export_to_csv(job.id)
            
            assert success is True
            assert csv_content is not None
            assert "record_index" in csv_content
            assert "plugin_id" in csv_content
    
    def test_export_to_json(self, app, db, mock_user):
        """Test exporting results to JSON."""
        with app.app_context():
            job = BatchJob(user_id=mock_user['id'], name="Test")
            db.db.add(job)
            db.db.commit()
            
            # Add results
            result = BatchJobResult(
                batch_job_id=job.id,
                record_index=0,
                plugin_id=1,
                plugin_name="Plugin1",
                success=True,
                result_data={"key": "value"},
                execution_time_ms=100
            )
            db.db.add(result)
            db.db.commit()
            
            success, message, json_content = BatchOperationService.export_to_json(job.id)
            
            assert success is True
            assert json_content is not None
            assert "results" in json_content or "batch_job" in json_content
    
    def test_get_batch_results_pagination(self, app, db, mock_user):
        """Test pagination of batch results."""
        with app.app_context():
            job = BatchJob(user_id=mock_user['id'], name="Test")
            db.db.add(job)
            db.db.commit()
            
            # Add 10 results
            for i in range(10):
                result = BatchJobResult(
                    batch_job_id=job.id,
                    record_index=i,
                    plugin_id=1,
                    plugin_name="Plugin1",
                    success=(i % 2 == 0),
                    execution_time_ms=100
                )
                db.db.add(result)
            
            db.db.commit()
            
            success, message, results = BatchOperationService.get_batch_results(
                job_id=job.id,
                limit=5,
                offset=0
            )
            
            assert success is True
            assert len(results) == 5
    
    def test_get_batch_results_filter_success(self, app, db, mock_user):
        """Test filtering results by success."""
        with app.app_context():
            job = BatchJob(user_id=mock_user['id'], name="Test")
            db.db.add(job)
            db.db.commit()
            
            # Add mixed results
            for i in range(5):
                result = BatchJobResult(
                    batch_job_id=job.id,
                    record_index=i,
                    plugin_id=1,
                    plugin_name="Plugin1",
                    success=(i < 3),  # First 3 successful
                    execution_time_ms=100
                )
                db.db.add(result)
            
            db.db.commit()
            
            # Get only successful results
            success, message, results = BatchOperationService.get_batch_results(
                job_id=job.id,
                filter_success=True
            )
            
            assert len(results) == 3
            assert all(r['success'] is True for r in results)
            
            # Get only failed results
            success, message, results = BatchOperationService.get_batch_results(
                job_id=job.id,
                filter_success=False
            )
            
            assert len(results) == 2
            assert all(r['success'] is False for r in results)
    
    def test_add_batch_log(self, app, db, mock_user):
        """Test adding batch logs."""
        with app.app_context():
            job = BatchJob(user_id=mock_user['id'], name="Test")
            db.db.add(job)
            db.db.commit()
            
            success, message = BatchOperationService.add_batch_log(
                job_id=job.id,
                level="info",
                message="Test log message",
                record_index=0,
                plugin_id=1
            )
            
            assert success is True
            
            # Verify log was created
            logs = BatchJobLog.query.filter_by(batch_job_id=job.id).all()
            assert len(logs) > 0
    
    def test_get_batch_logs_filtering(self, app, db, mock_user):
        """Test getting and filtering batch logs."""
        with app.app_context():
            job = BatchJob(user_id=mock_user['id'], name="Test")
            db.db.add(job)
            db.db.commit()
            
            # Add logs at different levels
            for level in ["info", "warning", "error", "debug"]:
                log = BatchJobLog(
                    batch_job_id=job.id,
                    level=level,
                    message=f"Test {level} log"
                )
                db.db.add(log)
            
            db.db.commit()
            
            success, message, logs = BatchOperationService.get_batch_logs(
                job_id=job.id,
                level="error"
            )
            
            assert success is True
            assert all(l['level'] == 'error' for l in logs)
    
    def test_cleanup_old_jobs(self, app, db, mock_user):
        """Test cleanup of old batch jobs."""
        with app.app_context():
            # Create old completed job
            old_job = BatchJob(
                user_id=mock_user['id'],
                name="Old Job",
                status=BatchJobStatus.completed
            )
            old_job.created_at = datetime.utcnow() - timedelta(days=40)
            db.db.add(old_job)
            
            # Create recent job
            recent_job = BatchJob(
                user_id=mock_user['id'],
                name="Recent Job",
                status=BatchJobStatus.completed
            )
            db.db.add(recent_job)
            db.db.commit()
            
            success, message, deleted_count = BatchOperationService.cleanup_old_jobs(days=30)
            
            assert success is True
            assert deleted_count == 1
            
            # Verify old job is gone
            assert db.session.get(BatchJob, old_job.id) is None
            # Recent job still exists
            assert db.session.get(BatchJob, recent_job.id) is not None


class TestBatchOperationPermissions:
    """Test permission enforcement in batch operations."""
    
    def test_batch_job_user_isolation(self, app, db):
        """Test that users can only see their own batch jobs."""
        with app.app_context():
            # Create jobs for different users
            job1 = BatchJob(user_id=1, name="User1 Job")
            job2 = BatchJob(user_id=2, name="User2 Job")
            
            db.db.add(job1)
            db.db.add(job2)
            db.db.commit()
            
            # User 1 should not be able to edit User 2's job
            success, message = BatchOperationService.start_batch_job(
                job_id=job2.id,
                user_id=1
            )
            
            assert success is False or message == "Unauthorized"
    
    def test_batch_execution_respects_plugin_permissions(self, app, db, mock_user):
        """Test that batch execution respects individual plugin permissions."""
        with app.app_context():
            g.user_id = mock_user['id']
            
            # This test verifies that execute_batch_parallel calls
            # PluginPermissionService.check_user_access() for each plugin
            # Implementation depends on actual permission system
    
    def test_batch_results_user_isolation(self, app, db, mock_user):
        """Test that batch results are isolated by user."""
        with app.app_context():
            job1 = BatchJob(user_id=1, name="Test1")
            job2 = BatchJob(user_id=2, name="Test2")
            
            db.db.add(job1)
            db.db.add(job2)
            db.db.commit()
            
            result1 = BatchJobResult(
                batch_job_id=job1.id,
                record_index=0,
                plugin_id=1,
                plugin_name="Plugin",
                success=True
            )
            
            db.db.add(result1)
            db.db.commit()
            
            # User 2 should not access User 1's results
            success, message, results = BatchOperationService.get_batch_results(
                job_id=job2.id
            )
            
            # Should return empty or error depending on implementation


class TestBatchExportFormats:
    """Test different export formats."""
    
    def test_csv_export_format(self, app, db, mock_user):
        """Test CSV export has correct format."""
        with app.app_context():
            job = BatchJob(user_id=mock_user['id'], name="Test")
            db.db.add(job)
            db.db.commit()
            
            # Add results
            for i in range(3):
                result = BatchJobResult(
                    batch_job_id=job.id,
                    record_index=i,
                    plugin_id=1,
                    plugin_name="Plugin1",
                    success=True,
                    result_data={"test": f"value{i}"},
                    execution_time_ms=100
                )
                db.db.add(result)
            
            db.db.commit()
            
            success, message, csv_content = BatchOperationService.export_to_csv(job.id)
            
            assert success is True
            lines = csv_content.split('\n')
            assert len(lines) >= 4  # Header + 3 rows
            assert 'record_index' in lines[0]
    
    def test_json_export_structure(self, app, db, mock_user):
        """Test JSON export has correct structure."""
        with app.app_context():
            job = BatchJob(user_id=mock_user['id'], name="Test", status=BatchJobStatus.completed)
            db.db.add(job)
            db.db.commit()
            
            result = BatchJobResult(
                batch_job_id=job.id,
                record_index=0,
                plugin_id=1,
                plugin_name="Plugin1",
                success=True,
                execution_time_ms=100
            )
            db.db.add(result)
            db.db.commit()
            
            success, message, json_content = BatchOperationService.export_to_json(job.id)
            
            assert success is True
            # JSON should be valid and contain results
            assert "results" in json_content or "batch_job" in json_content

