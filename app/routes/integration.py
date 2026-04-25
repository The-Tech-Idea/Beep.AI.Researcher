"""
Route Integration Helpers - Unifies EventBus, Hooks, and JobQueue for API routes.

Provides convenience functions to:
1. Publish events to EventBus
2. Execute hooks at key points
3. Queue async jobs via JobQueue
4. Track operation context and metadata
"""

import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps

from app.core import (
    get_event_bus, get_hook_registry, get_job_queue, get_job_registry,
    Event, EventType, EventPriority, JobType, JobPriority, HookContext
)

logger = logging.getLogger(__name__)


class RouteIntegrationContext:
    """
    Context object for tracking route operations.
    
    Holds metadata about current operation for event/hook/job usage.
    """
    
    def __init__(self, operation_name: str, user_id: Optional[str] = None,
                 project_id: Optional[int] = None, **metadata):
        self.operation_name = operation_name
        self.user_id = user_id
        self.project_id = project_id
        self.metadata = metadata
        self.event_data = {}
        self.hook_results = {}


def publish_event(event_type: str, data: Dict[str, Any], source: str = "route",
                  priority: Optional[EventPriority] = None) -> bool:
    """
    Publish event to EventBus.
    
    Args:
        event_type: Type of event (from EventType enum)
        data: Event data/payload
        source: Source of event (default: "route")
        priority: Event priority (optional, defaults to NORMAL)
    
    Returns:
        True if published successfully
    
    Example:
        publish_event(
            EventType.DOCUMENT_UPLOADED.value,
            {"document_id": "doc123", "filename": "report.pdf"},
            source="document_route",
            priority=EventPriority.HIGH
        )
    """
    try:
        bus = get_event_bus()
        event = Event(
            event_type=event_type,
            data=data,
            source=source,
            priority=priority or EventPriority.NORMAL
        )
        bus.publish(event)
        logger.info(f"Published event {event_type} from {source}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish event {event_type}: {e}")
        return False


def execute_hooks(event_type: str, operation_name: str, context_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute all hooks registered for an event.
    
    Args:
        event_type: Type of event (from EventType enum)
        operation_name: Name of operation for logging
        context_data: Data to pass to hooks
    
    Returns:
        Results from hook execution
    
    Example:
        results = execute_hooks(
            EventType.DOCUMENT_UPLOADED.value,
            "upload_document",
            {"document_id": "doc123", "user_id": "user456"}
        )
    """
    try:
        registry = get_hook_registry()
        
        # Create event for hooks
        bus = get_event_bus()
        event = Event(
            event_type=event_type,
            data=context_data,
            source="route"
        )
        
        # Execute hooks
        results = registry.execute_hooks(event, operation_name, context_data)
        logger.info(f"Executed hooks for {event_type}: {results}")
        return results
    except Exception as e:
        logger.error(f"Error executing hooks for {event_type}: {e}")
        return {"success": False, "error": str(e)}


def queue_job(job_type: str, input_data: Dict[str, Any],
              priority: JobPriority = JobPriority.NORMAL,
              max_retries: int = 3, metadata: Dict[str, Any] = None) -> Optional[str]:
    """
    Queue async job for background processing.
    
    Args:
        job_type: Type of job (from JobType enum)
        input_data: Job input parameters
        priority: Job priority (default: NORMAL)
        max_retries: Max retry attempts (default: 3)
        metadata: Custom metadata for tracking
    
    Returns:
        Job ID if queued successfully, None otherwise
    
    Example:
        job_id = queue_job(
            JobType.EXTRACT_DOCUMENT.value,
            {"document_id": "doc123", "schema_id": "schema456"},
            priority=JobPriority.HIGH,
            metadata={"user_id": "user789"}
        )
    """
    try:
        queue = get_job_queue()
        job = queue.create_job(
            job_type=job_type,
            input_data=input_data,
            priority=priority,
            max_retries=max_retries,
            metadata=metadata or {}
        )
        logger.info(f"Queued job {job.job_id} of type {job_type}")
        return job.job_id
    except Exception as e:
        logger.error(f"Failed to queue job {job_type}: {e}")
        return None


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Get status of queued job.
    
    Args:
        job_id: Job ID to check
    
    Returns:
        Job status dict or None if not found
    
    Example:
        status = get_job_status("job123")
        print(f"Job status: {status['status']}, Progress: {status['retry_count']}/{status['max_retries']}")
    """
    try:
        queue = get_job_queue()
        job = queue.get_job(job_id)
        if not job:
            return None
        
        return {
            "job_id": job.job_id,
            "job_type": job.job_type,
            "status": job.status,
            "priority": job.priority,
            "input_data": job.input_data,
            "output_data": job.output_data,
            "error_message": job.error_message,
            "retry_count": job.retry_count,
            "max_retries": job.max_retries,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "next_retry_at": job.next_retry_at,
            "logs": job.logs[-10:],  # Last 10 log entries
        }
    except Exception as e:
        logger.error(f"Failed to get job status {job_id}: {e}")
        return None


def register_job_handler(job_type: str, handler: Callable[..., Dict[str, Any]]) -> bool:
    """
    Register handler for custom job type.
    
    Args:
        job_type: Job type to handle
        handler: Callable that processes job input_data and returns result dict
    
    Returns:
        True if registered successfully
    
    Example:
        def extract_handler(input_data):
            doc_id = input_data["document_id"]
            schema_id = input_data["schema_id"]
            # Perform extraction
            return {
                "document_id": doc_id,
                "schema_id": schema_id,
                "extracted_data": {...},
                "success": True
            }
        
        register_job_handler(JobType.EXTRACT_DOCUMENT.value, extract_handler)
    """
    try:
        registry = get_job_registry()
        registry.register(job_type, handler)
        logger.info(f"Registered handler for job type {job_type}")
        return True
    except Exception as e:
        logger.error(f"Failed to register handler for {job_type}: {e}")
        return False


def integrated_operation(operation_name: str, event_type: Optional[str] = None,
                        hooks_before: bool = False, hooks_after: bool = False,
                        async_job: Optional[str] = None):
    """
    Decorator to integrate EventBus, Hooks, and JobQueue into route operations.
    
    Wraps a route handler to:
    1. Execute before hooks
    2. Run the main operation
    3. Execute after hooks
    4. Queue async job if specified
    5. Publish completion event
    
    Args:
        operation_name: Name of operation for logging
        event_type: Event type to publish on completion
        hooks_before: Execute hooks before operation
        hooks_after: Execute hooks after operation
        async_job: Job type to queue for async processing
    
    Example:
        @app.route('/projects/<int:project_id>/documents/upload', methods=['POST'])
        @integrated_operation(
            operation_name="upload_document",
            event_type=EventType.DOCUMENT_UPLOADED.value,
            hooks_after=True
        )
        def upload_document(project_id):
            # Normal route implementation
            return {"success": True, "document_id": "doc123"}
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            context = RouteIntegrationContext(operation_name, **kwargs)
            
            try:
                # Execute before hooks
                if hooks_before and event_type:
                    execute_hooks(event_type, f"{operation_name}_before", {})
                
                # Run main operation
                result = func(*args, **kwargs)
                
                # Execute after hooks
                if hooks_after and event_type and isinstance(result, dict):
                    execute_hooks(event_type, f"{operation_name}_after", result)
                
                # Queue async job if specified
                if async_job and isinstance(result, dict):
                    job_id = queue_job(async_job, result)
                    if job_id:
                        result["async_job_id"] = job_id
                
                # Publish completion event
                if event_type and isinstance(result, dict):
                    publish_event(event_type, result, source=f"{operation_name}_route")
                
                return result
                
            except Exception as e:
                logger.error(f"Error in {operation_name}: {e}")
                raise
        
        return wrapper
    return decorator


class EventBusPublisher:
    """Helper class for publishing related events."""
    
    @staticmethod
    def document_uploaded(document_id: str, project_id: int, filename: str,
                         file_size: int, user_id: Optional[str] = None) -> bool:
        """Publish document uploaded event."""
        return publish_event(
            EventType.DOCUMENT_UPLOADED.value,
            {
                "document_id": document_id,
                "project_id": project_id,
                "filename": filename,
                "file_size": file_size,
                "user_id": user_id,
            },
            source="documents_route"
        )
    
    @staticmethod
    def document_deleted(document_id: str, project_id: int) -> bool:
        """Publish document deleted event."""
        return publish_event(
            EventType.DOCUMENT_DELETED.value,
            {
                "document_id": document_id,
                "project_id": project_id,
            },
            source="documents_route"
        )
    
    @staticmethod
    def extraction_started(document_id: str, schema_id: int, project_id: int) -> bool:
        """Publish extraction started event."""
        return publish_event(
            EventType.EXTRACTION_STARTED.value,
            {
                "document_id": document_id,
                "schema_id": schema_id,
                "project_id": project_id,
            },
            source="extraction_route"
        )
    
    @staticmethod
    def extraction_completed(document_id: str, schema_id: int, result_id: int,
                            project_id: int) -> bool:
        """Publish extraction completed event."""
        return publish_event(
            EventType.EXTRACTION_COMPLETED.value,
            {
                "document_id": document_id,
                "schema_id": schema_id,
                "result_id": result_id,
                "project_id": project_id,
            },
            source="extraction_route"
        )
    
    @staticmethod
    def chat_message_sent(session_id: int, message_id: int, project_id: int,
                         user_id: Optional[str] = None) -> bool:
        """Publish chat message sent event."""
        return publish_event(
            EventType.CHAT_MESSAGE_SENT.value,
            {
                "session_id": session_id,
                "message_id": message_id,
                "project_id": project_id,
                "user_id": user_id,
            },
            source="chat_route"
        )
    
    @staticmethod
    def code_created(code_id: int, project_id: int, user_id: Optional[str] = None) -> bool:
        """Publish code created event."""
        return publish_event(
            EventType.CODE_CREATED.value,
            {
                "code_id": code_id,
                "project_id": project_id,
                "user_id": user_id,
            },
            source="codes_route"
        )
    
    @staticmethod
    def code_updated(code_id: int, project_id: int) -> bool:
        """Publish code updated event."""
        return publish_event(
            EventType.CODE_UPDATED.value,
            {
                "code_id": code_id,
                "project_id": project_id,
            },
            source="codes_route"
        )


class JobQueueManager:
    """Helper class for job queue operations."""
    
    @staticmethod
    def queue_extraction(document_id: str, schema_id: int, project_id: int,
                        user_id: Optional[str] = None) -> Optional[str]:
        """Queue extraction job."""
        return queue_job(
            JobType.EXTRACT_DOCUMENT.value,
            {
                "document_id": document_id,
                "schema_id": schema_id,
                "project_id": project_id,
            },
            priority=JobPriority.NORMAL,
            metadata={"user_id": user_id, "project_id": project_id}
        )
    
    @staticmethod
    def queue_report_generation(project_id: int, report_type: str,
                               user_id: Optional[str] = None) -> Optional[str]:
        """Queue report generation job."""
        return queue_job(
            JobType.GENERATE_REPORT.value,
            {
                "project_id": project_id,
                "report_type": report_type,
            },
            priority=JobPriority.HIGH,
            metadata={"user_id": user_id, "project_id": project_id}
        )
    
    @staticmethod
    def queue_index_update(project_id: int) -> Optional[str]:
        """Queue search index update job."""
        return queue_job(
            JobType.INDEX_UPDATE.value,
            {
                "project_id": project_id,
            },
            priority=JobPriority.LOW,
            max_retries=2
        )


# Initialize default handlers on module import
def initialize_default_handlers():
    """Register default handlers for built-in job types."""
    try:
        # Register PDF download handler
        from app.core.job_queue import JobType
        from app.jobs.pdf_download_handler import handle_pdf_download
        register_job_handler(JobType.PDF_DOWNLOAD.value, handle_pdf_download)
    except Exception:
        # Non-fatal: continue even if registration fails
        logger.exception("Failed to register default job handlers")
