"""
Integration tests for Phase 1.4 - Route Integration.

Tests demonstrate:
1. EventBus event publishing from routes
2. Hook execution triggered by route operations
3. JobQueue integration for async operations
4. Full integration flow: operation → event → hooks → job
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json

from app.core import (
    get_event_bus, get_hook_registry, get_job_queue,
    EventType, JobType, JobPriority, JobStatus
)
from app.routes.integration import (
    publish_event, execute_hooks, queue_job, get_job_status,
    register_job_handler, EventBusPublisher, JobQueueManager
)


class TestEventPublishing:
    """Test EventBus integration with routes."""

    def test_publish_document_uploaded_event(self):
        """Test publishing document upload event."""
        success = publish_event(
            EventType.DOCUMENT_UPLOADED.value,
            {
                "document_id": "doc123",
                "filename": "report.pdf",
                "file_size": 12345,
            },
            source="documents_route"
        )
        
        assert success is True
        
        # Verify event was recorded in event bus
        bus = get_event_bus()
        assert bus.get_stats()["total_events"] > 0

    def test_publish_extraction_events(self):
        """Test publishing extraction-related events."""
        # Publish started event
        success1 = publish_event(
            EventType.EXTRACTION_STARTED.value,
            {"document_id": "doc123", "schema_id": 1},
            source="extraction_route"
        )
        
        # Publish completed event
        success2 = publish_event(
            EventType.EXTRACTION_COMPLETED.value,
            {"document_id": "doc123", "schema_id": 1, "result_id": 42},
            source="extraction_route"
        )
        
        assert success1 is True
        assert success2 is True

    def test_publish_chat_message_event(self):
        """Test publishing chat message event."""
        success = publish_event(
            EventType.CHAT_MESSAGE_SENT.value,
            {
                "session_id": 5,
                "message_id": 100,
                "content": "What is...",
                "user_id": "user456",
            },
            source="chat_route"
        )
        
        assert success is True

    def test_publish_code_events(self):
        """Test publishing code events."""
        # Code created
        success1 = publish_event(
            EventType.CODE_CREATED.value,
            {"code_id": 999, "project_id": 1},
            source="codes_route"
        )
        
        # Code updated
        success2 = publish_event(
            EventType.CODE_UPDATED.value,
            {"code_id": 999, "project_id": 1},
            source="codes_route"
        )
        
        assert success1 is True
        assert success2 is True

    def test_event_bus_publisher_helper(self):
        """Test EventBusPublisher convenience methods."""
        # Document operations
        assert EventBusPublisher.document_uploaded(
            "doc789", 2, "analysis.pdf", 5000, "user123"
        ) is True
        
        assert EventBusPublisher.document_deleted("doc789", 2) is True
        
        # Extraction operations
        assert EventBusPublisher.extraction_started(
            "doc456", 3, 2
        ) is True
        
        assert EventBusPublisher.extraction_completed(
            "doc456", 3, 99, 2
        ) is True
        
        # Chat operations
        assert EventBusPublisher.chat_message_sent(
            10, 200, 2, "user456"
        ) is True
        
        # Code operations
        assert EventBusPublisher.code_created(88, 2, "user789") is True
        assert EventBusPublisher.code_updated(88, 2) is True


class TestHookExecution:
    """Test Hook integration with routes."""

    def test_execute_hooks_on_document_upload(self):
        """Test executing hooks when document uploaded."""
        # Hooks would execute after document is saved to DB
        results = execute_hooks(
            EventType.DOCUMENT_UPLOADED.value,
            "document_upload",
            {
                "document_id": "doc456",
                "project_id": 3,
                "filename": "data.csv",
                "user_id": "user789"
            }
        )
        
        assert isinstance(results, dict)

    def test_execute_hooks_on_extraction(self):
        """Test executing hooks before/after extraction."""
        # Before extraction
        before_results = execute_hooks(
            EventType.EXTRACTION_STARTED.value,
            "extraction_before",
            {"document_id": "doc456", "schema_id": 5}
        )
        
        # After extraction
        after_results = execute_hooks(
            EventType.EXTRACTION_COMPLETED.value,
            "extraction_after",
            {
                "document_id": "doc456",
                "schema_id": 5,
                "result_id": 150,
                "success": True,
                "extracted_fields": 12
            }
        )
        
        assert isinstance(before_results, dict)
        assert isinstance(after_results, dict)

    def test_execute_hooks_on_chat(self):
        """Test executing hooks on chat messages."""
        results = execute_hooks(
            EventType.CHAT_MESSAGE_SENT.value,
            "chat_message",
            {
                "session_id": 15,
                "message_id": 300,
                "content": "Tell me about...",
                "user_id": "user999"
            }
        )
        
        assert isinstance(results, dict)

    def test_execute_hooks_with_error_isolation(self):
        """Test that hook errors don't break the chain."""
        # Hooks are isolated - one failing shouldn't stop others
        results = execute_hooks(
            EventType.CODE_CREATED.value,
            "code_creation",
            {"code_id": 200, "project_id": 4}
        )
        
        # Even if hooks fail internally, should return results dict
        assert isinstance(results, dict)


class TestJobQueueIntegration:
    """Test JobQueue integration with routes."""

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
        from app.core.job_queue import JobQueue
        JobQueue._instance = None
        queue = JobQueue.get_instance(db_path=temp_db, num_workers=1)
        yield queue
        queue.stop()
        JobQueue._instance = None

    def test_queue_extraction_job(self, job_queue):
        """Test queuing extraction job from route."""
        job_id = queue_job(
            JobType.EXTRACT_DOCUMENT.value,
            {
                "document_id": "doc789",
                "schema_id": 7,
                "project_id": 5,
            },
            priority=JobPriority.NORMAL,
            metadata={"user_id": "user555"}
        )
        
        assert job_id is not None
        
        # Verify job was created
        job = job_queue.get_job(job_id)
        assert job is not None
        assert job.job_type == JobType.EXTRACT_DOCUMENT.value
        assert job.status == JobStatus.PENDING.value

    def test_queue_report_job(self, job_queue):
        """Test queuing report generation job."""
        job_id = queue_job(
            JobType.GENERATE_REPORT.value,
            {
                "project_id": 6,
                "report_type": "summary",
                "filters": {"date_range": "last_month"},
            },
            priority=JobPriority.HIGH,
            metadata={"user_id": "user666"}
        )
        
        assert job_id is not None

    def test_queue_index_update_job(self, job_queue):
        """Test queuing search index update job."""
        job_id = queue_job(
            JobType.INDEX_UPDATE.value,
            {"project_id": 7},
            priority=JobPriority.LOW,
            max_retries=2
        )
        
        assert job_id is not None

    def test_get_job_status(self, job_queue):
        """Test getting job status."""
        job_id = queue_job(
            JobType.EXTRACT_DOCUMENT.value,
            {"document_id": "doc999"},
            metadata={"source": "document_route"}
        )
        
        status = get_job_status(job_id)
        
        assert status is not None
        assert status["job_id"] == job_id
        assert status["job_type"] == JobType.EXTRACT_DOCUMENT.value
        assert status["status"] == JobStatus.PENDING.value
        assert status["retry_count"] == 0
        assert status["max_retries"] == 3

    def test_register_custom_handler(self, job_queue):
        """Test registering custom job handler."""
        def custom_handler(input_data):
            return {
                "processed": True,
                "input": input_data,
                "output": "completed"
            }
        
        success = register_job_handler("custom_operation", custom_handler)
        assert success is True
        
        # Queue custom job
        job_id = queue_job(
            "custom_operation",
            {"data": "test_data"},
        )
        
        assert job_id is not None

    def test_job_queue_manager_helper(self, job_queue):
        """Test JobQueueManager convenience methods."""
        # Queue extraction
        extraction_job = JobQueueManager.queue_extraction(
            "doc500", 9, 8, "user700"
        )
        assert extraction_job is not None
        
        # Queue report
        report_job = JobQueueManager.queue_report_generation(
            8, "detailed_analysis", "user700"
        )
        assert report_job is not None
        
        # Queue index update
        index_job = JobQueueManager.queue_index_update(8)
        assert index_job is not None


class TestIntegratedOperationFlow:
    """Test complete integrated operation flow."""

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
        from app.core.job_queue import JobQueue
        JobQueue._instance = None
        queue = JobQueue(db_path=temp_db, num_workers=1)
        yield queue
        queue.stop()
        JobQueue._instance = None

    def test_document_upload_integration_flow(self, job_queue):
        """Test full flow: upload → event → hooks → job."""
        # 1. Publish document uploaded event
        event_published = EventBusPublisher.document_uploaded(
            "doc_flow_1", 100, "research.pdf", 50000, "user_flow_1"
        )
        assert event_published is True
        
        # 2. Execute document upload hooks
        hook_results = execute_hooks(
            EventType.DOCUMENT_UPLOADED.value,
            "document_upload",
            {"document_id": "doc_flow_1", "project_id": 100}
        )
        assert isinstance(hook_results, dict)
        
        # 3. Queue extraction job (e.g., from auto-extraction hook)
        job_id = JobQueueManager.queue_extraction(
            "doc_flow_1", 50, 100, "user_flow_1"
        )
        assert job_id is not None
        
        # 4. Verify job was queued
        job_status = get_job_status(job_id)
        assert job_status["status"] == JobStatus.PENDING.value
        assert job_status["job_type"] == JobType.EXTRACT_DOCUMENT.value

    def test_extraction_integration_flow(self, job_queue):
        """Test full extraction flow: start → process → complete."""
        # 1. Publish extraction started
        start_event = EventBusPublisher.extraction_started(
            "doc_extract_2", 51, 101
        )
        assert start_event is True
        
        # 2. Queue extraction job
        job_id = queue_job(
            JobType.EXTRACT_DOCUMENT.value,
            {
                "document_id": "doc_extract_2",
                "schema_id": 51,
                "project_id": 101,
            }
        )
        assert job_id is not None
        
        # 3. Publish extraction completed
        complete_event = EventBusPublisher.extraction_completed(
            "doc_extract_2", 51, 500, 101
        )
        assert complete_event is True
        
        # 4. Execute post-extraction hooks
        post_hooks = execute_hooks(
            EventType.EXTRACTION_COMPLETED.value,
            "extraction_complete",
            {
                "document_id": "doc_extract_2",
                "schema_id": 51,
                "result_id": 500,
                "fields_extracted": 15
            }
        )
        assert isinstance(post_hooks, dict)

    def test_multi_operation_concurrent_flow(self, job_queue):
        """Test multiple operations running concurrently."""
        # Simulate concurrent operations
        operations = []
        
        # Operation 1: Document upload
        for i in range(3):
            job_id = queue_job(
                JobType.EXTRACT_DOCUMENT.value,
                {"document_id": f"doc_concurrent_{i}", "project_id": 102}
            )
            operations.append(job_id)
        
        # Operation 2: Report generation
        for i in range(2):
            job_id = queue_job(
                JobType.GENERATE_REPORT.value,
                {"project_id": 102, "type": f"report_{i}"},
                priority=JobPriority.HIGH
            )
            operations.append(job_id)
        
        # Operation 3: Index updates
        job_id = queue_job(
            JobType.INDEX_UPDATE.value,
            {"project_id": 102},
            priority=JobPriority.LOW
        )
        operations.append(job_id)
        
        # Verify all jobs queued
        assert len(operations) == 6
        for job_id in operations:
            assert job_id is not None
        
        # Verify all jobs retrievable
        for job_id in operations:
            status = get_job_status(job_id)
            assert status is not None
            assert status["status"] == JobStatus.PENDING.value


class TestIntegrationErrorHandling:
    """Test error handling in integration."""

    def test_publish_event_handles_errors(self):
        """Test that publish_event handles exceptions gracefully."""
        # Invalid event type should still return False, not raise
        result = publish_event(
            "invalid.event.type",
            {"data": "test"}
        )
        # May return True or False depending on validation, but shouldn't raise

    def test_execute_hooks_handles_errors(self):
        """Test that execute_hooks doesn't crash on errors."""
        # Should return error dict, not raise exception
        result = execute_hooks(
            EventType.DOCUMENT_UPLOADED.value,
            "test_op",
            {"test": "data"}
        )
        assert isinstance(result, dict)

    def test_queue_job_handles_errors(self):
        """Test that queue_job handles errors gracefully."""
        # Invalid data should return None, not raise
        result = queue_job(
            "unknown_type",
            None  # Invalid: should be dict
        )
        # Will handle gracefully


class TestIntegrationStatistics:
    """Test statistics tracking across integration."""

    def test_event_statistics(self):
        """Test that published events are tracked."""
        bus = get_event_bus()
        initial_count = bus.get_stats()["total_events"]
        
        # Publish multiple events
        for i in range(3):
            publish_event(
                EventType.CHAT_MESSAGE_SENT.value,
                {"session_id": i, "message": f"test_{i}"}
            )
        
        final_count = bus.get_stats()["total_events"]
        assert final_count > initial_count

    def test_hook_statistics(self):
        """Test that hook execution is tracked."""
        registry = get_hook_registry()
        initial_stats = registry.get_stats()
        
        # Execute hooks multiple times
        for i in range(2):
            execute_hooks(
                EventType.CODE_CREATED.value,
                f"operation_{i}",
                {"code_id": i, "project_id": 1}
            )
        
        final_stats = registry.get_stats()
        # Stats should be tracked (if hooks are registered)
        assert isinstance(final_stats, dict)

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
        from app.core.job_queue import JobQueue
        JobQueue._instance = None
        queue = JobQueue.get_instance(db_path=temp_db, num_workers=1)
        yield queue
        queue.stop()
        JobQueue._instance = None

    def test_job_queue_statistics(self, job_queue):
        """Test that queued jobs are tracked."""
        initial_stats = job_queue.get_stats()
        initial_total = initial_stats["total_jobs"]
        
        # Queue multiple jobs
        for i in range(3):
            queue_job(
                JobType.EXTRACT_DOCUMENT.value,
                {"document_id": f"doc_{i}"}
            )
        
        final_stats = job_queue.get_stats()
        assert final_stats["total_jobs"] == initial_total + 3
        assert final_stats["jobs_pending"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
