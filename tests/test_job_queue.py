"""
Comprehensive tests for Job Queue System (Phase 1.3).

Tests cover:
- Job creation, execution, and status tracking
- Priority queue ordering
- Retry logic with exponential backoff
- Error handling and isolation
- Job statistics
- Job registry and handlers
- Background worker functionality
"""

import pytest
import time
import tempfile
import sqlite3
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from app.core import (
    JobQueue, Job, JobStatus, JobType, JobPriority, JobResult,
    JobRegistry, get_job_queue, get_job_registry,
)


class TestJobDataStructure:
    """Test Job dataclass and basic properties."""

    def test_job_creation_with_defaults(self):
        """Test creating job with default values."""
        job = Job(job_type=JobType.EXTRACT_DOCUMENT.value)
        
        assert job.job_id is not None
        assert job.job_type == JobType.EXTRACT_DOCUMENT.value
        assert job.status == JobStatus.PENDING.value
        assert job.priority == JobPriority.NORMAL.value
        assert job.retry_count == 0
        assert job.max_retries == 3
        assert job.created_at is not None
        assert job.started_at is None
        assert job.completed_at is None

    def test_job_creation_with_custom_values(self):
        """Test creating job with custom values."""
        input_data = {"doc_id": "doc123"}
        metadata = {"user_id": "user456"}
        
        job = Job(
            job_type=JobType.WEB_SEARCH.value,
            priority=JobPriority.CRITICAL.value,
            input_data=input_data,
            max_retries=5,
            metadata=metadata
        )
        
        assert job.job_type == JobType.WEB_SEARCH.value
        assert job.priority == JobPriority.CRITICAL.value
        assert job.input_data == input_data
        assert job.max_retries == 5
        assert job.metadata == metadata

    def test_job_to_dict(self):
        """Test job conversion to dictionary."""
        job = Job(job_type=JobType.EXTRACT_DOCUMENT.value)
        job_dict = job.to_dict()
        
        assert isinstance(job_dict, dict)
        assert job_dict["job_type"] == JobType.EXTRACT_DOCUMENT.value
        assert "job_id" in job_dict
        assert "status" in job_dict

    def test_job_to_json(self):
        """Test job conversion to JSON."""
        job = Job(job_type=JobType.EXTRACT_DOCUMENT.value)
        job_json = job.to_json()
        
        assert isinstance(job_json, str)
        assert "job_type" in job_json
        assert "extract_document" in job_json

    def test_job_from_dict(self):
        """Test creating job from dictionary."""
        data = {
            "job_id": "job123",
            "job_type": JobType.WEB_SEARCH.value,
            "status": JobStatus.RUNNING.value,
            "priority": JobPriority.HIGH.value,
            "input_data": {"query": "test"},
            "output_data": {},
            "error_message": None,
            "retry_count": 0,
            "max_retries": 3,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "started_at": None,
            "completed_at": None,
            "next_retry_at": None,
            "metadata": {},
            "logs": []
        }
        
        job = Job.from_dict(data)
        
        assert job.job_id == "job123"
        assert job.job_type == JobType.WEB_SEARCH.value
        assert job.priority == JobPriority.HIGH.value

    def test_job_add_log(self):
        """Test adding logs to job."""
        job = Job(job_type=JobType.EXTRACT_DOCUMENT.value)
        
        job.add_log("Starting job")
        job.add_log("Processing document")
        
        assert len(job.logs) == 2
        assert "Starting job" in job.logs[0]
        assert "Processing document" in job.logs[1]

    def test_job_is_retriable(self):
        """Test job retry eligibility."""
        job = Job(job_type=JobType.EXTRACT_DOCUMENT.value, max_retries=3)
        
        # Not retriable if not failed
        assert not job.is_retriable()
        
        # Not retriable if max retries exceeded
        job.status = JobStatus.FAILED.value
        job.retry_count = 3
        assert not job.is_retriable()
        
        # Retriable if failed and retries remaining
        job.retry_count = 2
        assert job.is_retriable()

    def test_job_mark_for_retry(self):
        """Test marking job for retry."""
        job = Job(job_type=JobType.EXTRACT_DOCUMENT.value, max_retries=3)
        job.status = JobStatus.FAILED.value
        job.retry_count = 0
        
        job.mark_for_retry()
        
        assert job.retry_count == 1
        assert job.status == JobStatus.RETRY.value
        assert job.next_retry_at is not None
        # Exponential backoff: 2^1 = 2 seconds
        retry_time = datetime.fromisoformat(job.next_retry_at)
        assert retry_time > datetime.now(timezone.utc)


class TestJobPriority:
    """Test JobPriority enum."""

    def test_priority_ordering(self):
        """Test priority comparison."""
        assert JobPriority.CRITICAL < JobPriority.HIGH
        assert JobPriority.HIGH < JobPriority.NORMAL
        assert JobPriority.NORMAL < JobPriority.LOW

    def test_priority_value(self):
        """Test priority numeric values."""
        assert JobPriority.CRITICAL.value == 0
        assert JobPriority.HIGH.value == 1
        assert JobPriority.NORMAL.value == 2
        assert JobPriority.LOW.value == 3


class TestJobResult:
    """Test JobResult dataclass."""

    def test_result_success(self):
        """Test successful result."""
        result = JobResult(success=True, output={"data": "test"}, execution_time_ms=42.5)
        
        assert result.success is True
        assert result.output == {"data": "test"}
        assert result.error is None
        assert result.execution_time_ms == 42.5

    def test_result_failure(self):
        """Test failed result."""
        result = JobResult(success=False, error="Test error")
        
        assert result.success is False
        assert result.error == "Test error"
        assert result.output is None


class TestJobRegistry:
    """Test Job Registry for handler management."""

    def test_registry_singleton(self):
        """Test registry singleton pattern."""
        registry1 = get_job_registry()
        registry2 = get_job_registry()
        
        assert registry1 is registry2

    def test_register_handler(self):
        """Test registering job handler."""
        registry = get_job_registry()
        
        def test_handler(data):
            return {"result": "ok"}
        
        registry.register("test_job", test_handler)
        
        assert registry.has_handler("test_job")
        assert registry.get_handler("test_job") is test_handler

    def test_register_handler_invalid(self):
        """Test registering invalid handler."""
        registry = get_job_registry()
        
        with pytest.raises(ValueError):
            registry.register("invalid", "not_callable")

    def test_unregister_handler(self):
        """Test unregistering handler."""
        registry = get_job_registry()
        
        def test_handler(data):
            return {}
        
        registry.register("test_handler", test_handler)
        assert registry.has_handler("test_handler")
        
        registry.unregister("test_handler")
        assert not registry.has_handler("test_handler")

    def test_get_all_handlers(self):
        """Test getting all registered handlers."""
        registry = get_job_registry()
        
        def handler1(data):
            return {}
        
        def handler2(data):
            return {}
        
        registry.register("job1", handler1)
        registry.register("job2", handler2)
        
        handlers = registry.get_all_handlers()
        assert "job1" in handlers
        assert "job2" in handlers


class TestJobQueue:
    """Test Job Queue operations."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def job_queue(self, temp_db):
        """Create job queue with temp database."""
        # Reset singleton for testing
        JobQueue._instance = None
        queue = JobQueue(db_path=temp_db, num_workers=2)
        yield queue
        queue.stop()
        JobQueue._instance = None

    def test_queue_singleton(self):
        """Test job queue singleton."""
        JobQueue._instance = None
        queue1 = get_job_queue()
        queue2 = get_job_queue()
        
        assert queue1 is queue2
        queue1.stop()
        JobQueue._instance = None

    def test_create_job(self, job_queue):
        """Test creating job."""
        input_data = {"doc_id": "doc123"}
        job = job_queue.create_job(
            job_type=JobType.EXTRACT_DOCUMENT.value,
            input_data=input_data,
            priority=JobPriority.HIGH
        )
        
        assert job.job_id is not None
        assert job.job_type == JobType.EXTRACT_DOCUMENT.value
        assert job.status == JobStatus.PENDING.value
        assert job.input_data == input_data
        assert job_queue._statistics["total_jobs"] == 1

    def test_get_job(self, job_queue):
        """Test retrieving job by ID."""
        created_job = job_queue.create_job(
            job_type=JobType.WEB_SEARCH.value,
            input_data={"query": "test"}
        )
        
        retrieved_job = job_queue.get_job(created_job.job_id)
        
        assert retrieved_job is not None
        assert retrieved_job.job_id == created_job.job_id
        assert retrieved_job.job_type == JobType.WEB_SEARCH.value

    def test_get_nonexistent_job(self, job_queue):
        """Test getting non-existent job."""
        job = job_queue.get_job("non_existent_id")
        
        assert job is None

    def test_get_pending_jobs(self, job_queue):
        """Test getting pending jobs."""
        job_queue.create_job(JobType.EXTRACT_DOCUMENT.value, {}, JobPriority.LOW)
        job_queue.create_job(JobType.WEB_SEARCH.value, {}, JobPriority.CRITICAL)
        job_queue.create_job(JobType.PROCESS_DATASET.value, {}, JobPriority.NORMAL)
        
        pending = job_queue.get_pending_jobs()
        
        assert len(pending) == 3
        # Should be sorted by priority
        assert pending[0].priority == JobPriority.CRITICAL.value
        assert pending[1].priority == JobPriority.NORMAL.value
        assert pending[2].priority == JobPriority.LOW.value

    def test_get_jobs_by_status(self, job_queue):
        """Test filtering jobs by status."""
        job1 = job_queue.create_job(JobType.EXTRACT_DOCUMENT.value, {})
        job2 = job_queue.create_job(JobType.WEB_SEARCH.value, {})
        job1.status = JobStatus.COMPLETED.value
        job_queue._save_job_to_db(job1)
        
        pending = job_queue.get_jobs_by_status(JobStatus.PENDING)
        completed = job_queue.get_jobs_by_status(JobStatus.COMPLETED)
        
        assert len(pending) == 1
        assert pending[0].job_id == job2.job_id
        assert len(completed) == 1
        assert completed[0].job_id == job1.job_id

    def test_cancel_job(self, job_queue):
        """Test cancelling a job."""
        job = job_queue.create_job(JobType.EXTRACT_DOCUMENT.value, {})
        
        success = job_queue.cancel_job(job.job_id)
        
        assert success is True
        job = job_queue.get_job(job.job_id)
        assert job.status == JobStatus.CANCELLED.value
        assert job_queue._statistics["cancelled"] == 1

    def test_cancel_completed_job(self, job_queue):
        """Test that cannot cancel completed job."""
        job = job_queue.create_job(JobType.EXTRACT_DOCUMENT.value, {})
        job.status = JobStatus.COMPLETED.value
        job_queue._save_job_to_db(job)
        
        success = job_queue.cancel_job(job.job_id)
        
        assert success is False

    def test_retry_job(self, job_queue):
        """Test retrying failed job."""
        job = job_queue.create_job(JobType.EXTRACT_DOCUMENT.value, {}, max_retries=3)
        job.status = JobStatus.FAILED.value
        job_queue._save_job_to_db(job)
        
        success = job_queue.retry_job(job.job_id)
        
        assert success is True
        job = job_queue.get_job(job.job_id)
        assert job.status == JobStatus.RETRY.value
        assert job.retry_count == 1
        assert job_queue._statistics["retried"] == 1

    def test_job_history(self, job_queue):
        """Test getting job history."""
        for i in range(5):
            job_queue.create_job(JobType.EXTRACT_DOCUMENT.value, {})
        
        history = job_queue.get_job_history(limit=3)
        
        assert len(history) == 3

    def test_job_history_filter_by_status(self, job_queue):
        """Test filtering job history by status."""
        job1 = job_queue.create_job(JobType.EXTRACT_DOCUMENT.value, {})
        job2 = job_queue.create_job(JobType.WEB_SEARCH.value, {})
        job1.status = JobStatus.COMPLETED.value
        job_queue._save_job_to_db(job1)
        
        history = job_queue.get_job_history(status=JobStatus.COMPLETED)
        
        assert len(history) == 1
        assert history[0].job_id == job1.job_id


class TestJobExecution:
    """Test job execution with handlers."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def job_queue(self, temp_db):
        """Create job queue with temp database."""
        JobQueue._instance = None
        queue = JobQueue(db_path=temp_db, num_workers=1)
        yield queue
        queue.stop()
        JobQueue._instance = None

    def test_execute_job_success(self, job_queue):
        """Test successful job execution."""
        registry = get_job_registry()
        
        def success_handler(data):
            return {"result": "success", "input": data}
        
        registry.register(JobType.EXTRACT_DOCUMENT.value, success_handler)
        
        job = job_queue.create_job(
            job_type=JobType.EXTRACT_DOCUMENT.value,
            input_data={"doc_id": "test"}
        )
        
        result = job_queue._execute_job(job)
        
        assert result.success is True
        assert job.status == JobStatus.COMPLETED.value
        assert job.output_data["result"] == "success"
        assert job_queue._statistics["completed"] == 1

    def test_execute_job_no_handler(self, job_queue):
        """Test execution with no registered handler."""
        job = job_queue.create_job(
            job_type="unknown_type",
            input_data={}
        )
        
        result = job_queue._execute_job(job)
        
        assert result.success is False
        assert job.status == JobStatus.FAILED.value
        assert "No handler" in result.error

    def test_execute_job_handler_error(self, job_queue):
        """Test execution with handler that raises error."""
        registry = get_job_registry()
        
        def error_handler(data):
            raise ValueError("Test error")
        
        registry.register("error_job", error_handler)
        
        job = job_queue.create_job(job_type="error_job", input_data={}, max_retries=1)
        
        result = job_queue._execute_job(job)
        
        assert result.success is False
        assert job.error_message is not None
        assert "ValueError" in job.error_message

    def test_execute_job_retry_on_failure(self, job_queue):
        """Test that failed jobs marked for retry."""
        registry = get_job_registry()
        
        def failing_handler(data):
            raise RuntimeError("Failure")
        
        registry.register("fail_job", failing_handler)
        
        job = job_queue.create_job(job_type="fail_job", input_data={}, max_retries=3)
        
        result = job_queue._execute_job(job)
        
        assert job.status == JobStatus.RETRY.value
        assert job.retry_count == 1
        assert job_queue._statistics["retried"] == 1

    def test_execute_job_permanent_failure(self, job_queue):
        """Test permanent failure after max retries."""
        registry = get_job_registry()
        
        def failing_handler(data):
            raise RuntimeError("Failure")
        
        registry.register("fail_job", failing_handler)
        
        job = job_queue.create_job(job_type="fail_job", input_data={}, max_retries=2)
        job.retry_count = 2  # Already at max
        
        result = job_queue._execute_job(job)
        
        assert job.status == JobStatus.FAILED.value
        assert job_queue._statistics["failed"] == 1


class TestJobStatistics:
    """Test job queue statistics."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def job_queue(self, temp_db):
        """Create job queue with temp database."""
        JobQueue._instance = None
        queue = JobQueue(db_path=temp_db, num_workers=1)
        yield queue
        queue.stop()
        JobQueue._instance = None

    def test_statistics_initialization(self, job_queue):
        """Test initial statistics."""
        stats = job_queue.get_stats()
        
        assert stats["total_jobs"] == 0
        assert stats["completed"] == 0
        assert stats["failed"] == 0
        assert stats["retried"] == 0
        assert stats["cancelled"] == 0

    def test_statistics_after_operations(self, job_queue):
        """Test statistics after various operations."""
        job1 = job_queue.create_job(JobType.EXTRACT_DOCUMENT.value, {})
        job2 = job_queue.create_job(JobType.WEB_SEARCH.value, {})
        
        job_queue.cancel_job(job1.job_id)
        
        stats = job_queue.get_stats()
        
        assert stats["total_jobs"] == 2
        assert stats["cancelled"] == 1
        assert stats["jobs_pending"] == 1

    def test_reset_statistics(self, job_queue):
        """Test resetting statistics."""
        job_queue.create_job(JobType.EXTRACT_DOCUMENT.value, {})
        
        stats_before = job_queue.get_stats()
        assert stats_before["total_jobs"] == 1
        
        job_queue.reset_stats()
        
        stats_after = job_queue.get_stats()
        assert stats_after["completed"] == 0
        assert stats_after["failed"] == 0


class TestJobQueuePersistence:
    """Test SQLite persistence."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    def test_jobs_persisted_to_db(self, temp_db):
        """Test jobs are persisted to SQLite."""
        JobQueue._instance = None
        queue = JobQueue(db_path=temp_db, num_workers=1)
        
        job = queue.create_job(JobType.EXTRACT_DOCUMENT.value, {"data": "test"})
        job_id = job.job_id
        queue.stop()
        
        # Reload queue
        JobQueue._instance = None
        queue2 = JobQueue(db_path=temp_db, num_workers=1)
        
        loaded_job = queue2.get_job(job_id)
        assert loaded_job is not None
        assert loaded_job.input_data["data"] == "test"
        
        queue2.stop()
        JobQueue._instance = None

    def test_database_integrity(self, temp_db):
        """Test database schema and integrity."""
        JobQueue._instance = None
        queue = JobQueue(db_path=temp_db, num_workers=1)
        
        # Verify table exists
        with queue._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
            assert cursor.fetchone() is not None
        
        queue.stop()
        JobQueue._instance = None


class TestJobQueueEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        yield db_path
        Path(db_path).unlink(missing_ok=True)

    @pytest.fixture
    def job_queue(self, temp_db):
        """Create job queue with temp database."""
        JobQueue._instance = None
        queue = JobQueue(db_path=temp_db, num_workers=1)
        yield queue
        queue.stop()
        JobQueue._instance = None

    def test_large_input_data(self, job_queue):
        """Test job with large input data."""
        large_data = {"content": "x" * 100_000}
        
        job = job_queue.create_job(JobType.PROCESS_DATASET.value, large_data)
        
        retrieved = job_queue.get_job(job.job_id)
        assert len(retrieved.input_data["content"]) == 100_000

    def test_special_characters_in_data(self, job_queue):
        """Test job with special characters."""
        special_data = {"text": "Hello\n世界\t!@#$%"}
        
        job = job_queue.create_job(JobType.EXTRACT_DOCUMENT.value, special_data)
        
        retrieved = job_queue.get_job(job.job_id)
        assert retrieved.input_data["text"] == "Hello\n世界\t!@#$%"

    def test_concurrent_job_creation(self, job_queue):
        """Test creating jobs concurrently."""
        import threading
        
        def create_jobs():
            for _ in range(10):
                job_queue.create_job(JobType.EXTRACT_DOCUMENT.value, {})
        
        threads = [threading.Thread(target=create_jobs) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All jobs should be created
        all_jobs = job_queue.get_job_history(limit=1000)
        assert len(all_jobs) >= 30


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
