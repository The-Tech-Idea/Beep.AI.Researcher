# Phase 1.4: Route Integration Guide

**Status**: ✅ Complete

**Overview**: Unified integration helpers for EventBus, Hook System, and Job Queue into API routes.

**Key Statistics**:
- Lines of Code: 449 (integration.py only)
- Test Coverage: 24 comprehensive integration tests
- Pass Rate: 100% (24/24 tests)
- Execution Time: ~11 seconds

---

## 1. Overview

The Route Integration layer provides convenience functions and helper classes to simplify integration of the EventBus, Hook System, and Job Queue within API route handlers.

**Core Components**:
- `publish_event()` - Publish events with error handling
- `execute_hooks()` - Execute hooks for specific events
- `queue_job()` - Queue async jobs for background processing
- `EventBusPublisher` - Static convenience methods for common events
- `JobQueueManager` - Static convenience methods for job queuing
- `@integrated_operation()` - Decorator for unified operation flow

---

## 2. Publishing Events from Routes

### Basic Event Publishing

```python
from app.routes.integration import publish_event
from app.core import EventType

# Publish a simple event
success = publish_event(
    EventType.DOCUMENT_UPLOADED.value,
    {
        "document_id": "doc123",
        "filename": "report.pdf",
        "file_size": 12345,
    },
    source="documents_route"
)

if success:
    print("Event published successfully")
else:
    print("Failed to publish event")
```

### Using EventBusPublisher Convenience Class

```python
from app.routes.integration import EventBusPublisher

# Document events
EventBusPublisher.document_uploaded(
    document_id="doc123",
    project_id=1,
    filename="report.pdf",
    file_size=12345,
    user_id="user456"
)

EventBusPublisher.document_deleted(
    document_id="doc123",
    project_id=1
)

# Extraction events
EventBusPublisher.extraction_started(
    document_id="doc123",
    schema_id=5,
    project_id=1
)

EventBusPublisher.extraction_completed(
    document_id="doc123",
    schema_id=5,
    result_id=42,
    project_id=1
)

# Chat events
EventBusPublisher.chat_message_sent(
    session_id=10,
    message_id=20,
    project_id=1,
    user_id="user456"
)

# Code events
EventBusPublisher.code_created(
    code_id=30,
    project_id=1,
    user_id="user456"
)

EventBusPublisher.code_updated(
    code_id=30,
    project_id=1,
    user_id="user456"
)
```

### Event Priority Control

```python
from app.routes.integration import publish_event
from app.core import EventType, EventPriority

# Publish high-priority event
publish_event(
    EventType.EXTRACTION_COMPLETED.value,
    {"result_id": 42, "status": "success"},
    source="extraction_route",
    priority=EventPriority.HIGH
)
```

---

## 3. Executing Hooks from Routes

### Basic Hook Execution

```python
from app.routes.integration import execute_hooks
from app.core import EventType

# Execute all registered hooks for an event
results = execute_hooks(
    EventType.DOCUMENT_UPLOADED.value,
    operation_name="upload_document",
    context_data={
        "document_id": "doc123",
        "user_id": "user456",
        "project_id": 1
    }
)

# Check results
if results.get("success"):
    print("All hooks executed successfully")
else:
    print(f"Error: {results.get('error')}")
```

### Hooks Execution with Error Isolation

```python
# Hooks are executed with error isolation - one failing hook won't stop others
results = execute_hooks(
    EventType.EXTRACTION_COMPLETED.value,
    operation_name="extraction_completed",
    context_data={
        "document_id": "doc123",
        "schema_id": 5,
        "extracted_data": {"field1": "value1"}
    }
)

# Individual hook results available
for hook_name, hook_result in results.items():
    if "error" in hook_result:
        print(f"Hook {hook_name} failed: {hook_result['error']}")
```

---

## 4. Queuing Background Jobs

### Basic Job Queuing

```python
from app.routes.integration import queue_job, get_job_status
from app.core import JobType, JobPriority

# Queue a job
job_id = queue_job(
    JobType.EXTRACT_DOCUMENT.value,
    {
        "document_id": "doc123",
        "schema_id": 5,
        "project_id": 1,
    },
    priority=JobPriority.HIGH,
    max_retries=3,
    metadata={"user_id": "user456", "source": "api"}
)

if job_id:
    print(f"Job queued: {job_id}")
    
    # Check job status
    status = get_job_status(job_id)
    if status:
        print(f"Job status: {status['status']}")
        print(f"Priority: {status['priority']}")
        print(f"Retry count: {status['retry_count']}/{status['max_retries']}")
```

### Using JobQueueManager Convenience Class

```python
from app.routes.integration import JobQueueManager, get_job_status

# Queue extraction job
extraction_job_id = JobQueueManager.queue_extraction(
    document_id="doc123",
    schema_id=5,
    project_id=1,
    user_id="user456"
)

# Queue report generation job
report_job_id = JobQueueManager.queue_report_generation(
    project_id=1,
    report_type="summary",
    user_id="user456"
)

# Queue index update job
index_job_id = JobQueueManager.queue_index_update(
    project_id=1,
    user_id="user456"
)

# Check job progress asynchronously
if extraction_job_id:
    status = get_job_status(extraction_job_id)
    print(f"Extraction job {extraction_job_id}: {status['status']}")
```

### Job Priority Levels

```python
from app.core import JobPriority

# CRITICAL: Execute immediately
queue_job(job_type, input_data, priority=JobPriority.CRITICAL)

# HIGH: Execute soon
queue_job(job_type, input_data, priority=JobPriority.HIGH)

# NORMAL: Regular priority (default)
queue_job(job_type, input_data, priority=JobPriority.NORMAL)

# LOW: Execute when resources available
queue_job(job_type, input_data, priority=JobPriority.LOW)
```

---

## 5. Unified Operation Flow with Decorator

Use the `@integrated_operation` decorator to automatically integrate EventBus, Hooks, and JobQueue:

```python
from flask import request
from app.routes.integration import integrated_operation, EventBusPublisher
from app.core import EventType, JobType

@app.route('/api/documents/upload', methods=['POST'])
@integrated_operation(
    operation_name="upload_document",
    event_type=EventType.DOCUMENT_UPLOADED.value,
    hooks_before=False,
    hooks_after=True,
    async_job=None
)
def upload_document():
    """Upload and process a document."""
    file = request.files.get('file')
    project_id = request.form.get('project_id')
    
    # Save document (normal route logic)
    document_id = save_document(file, project_id)
    
    return {
        "success": True,
        "document_id": document_id,
        "project_id": project_id,
        "filename": file.filename,
        "file_size": len(file.read())
    }
    # Decorator automatically:
    # 1. Executes after hooks
    # 2. Publishes DOCUMENT_UPLOADED event
    # 3. Returns result with optional async_job_id
```

### Decorator Options

```python
from app.routes.integration import integrated_operation, JobType

@integrated_operation(
    operation_name="extract_document",          # Name for logging
    event_type=EventType.EXTRACTION_STARTED.value,  # Event to publish
    hooks_before=True,                          # Execute hooks before operation
    hooks_after=True,                           # Execute hooks after operation  
    async_job=JobType.EXTRACT_DOCUMENT.value   # Queue async job on success
)
def extract_document():
    """Extract data from document."""
    # Route implementation
    return {"success": True, "result_id": 42}
```

---

## 6. Custom Job Handlers

Register custom handlers for specific job types:

```python
from app.routes.integration import register_job_handler
from app.core import JobType

def custom_extraction_handler(input_data):
    """Custom handler for extraction jobs."""
    document_id = input_data.get("document_id")
    schema_id = input_data.get("schema_id")
    
    try:
        # Perform extraction
        extracted_data = perform_extraction(document_id, schema_id)
        
        return {
            "success": True,
            "document_id": document_id,
            "extracted_data": extracted_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "document_id": document_id
        }

# Register handler
register_job_handler(
    JobType.EXTRACT_DOCUMENT.value,
    custom_extraction_handler
)
```

---

## 7. Error Handling

All integration functions include comprehensive error handling:

```python
from app.routes.integration import publish_event, execute_hooks, queue_job

# publish_event returns False on error
if not publish_event(event_type, data):
    # Handle publication failure
    log_error("Failed to publish event")
    # Note: This won't raise an exception, errors are logged

# execute_hooks returns dict with error field
results = execute_hooks(event_type, operation, context)
if not results.get("success"):
    error_msg = results.get("error")
    log_error(f"Hooks failed: {error_msg}")

# queue_job returns None on error
job_id = queue_job(job_type, input_data)
if job_id is None:
    # Handle queueing failure
    log_error("Failed to queue job")
```

### Graceful Degradation

The integration layer is designed for graceful degradation:

```python
# Even if EventBus fails, route continues
publish_event(...)  # Returns False, doesn't raise

# Even if hooks fail, operation continues
execute_hooks(...)  # Returns error dict, doesn't raise

# Even if job queueing fails, route continues
queue_job(...)  # Returns None, doesn't raise
```

---

## 8. Integration Patterns

### Pattern 1: Upload with Async Processing

```python
@app.route('/api/documents', methods=['POST'])
def upload_document():
    # 1. Save document
    document_id = save_document_to_db(request.files['file'])
    
    # 2. Publish event
    EventBusPublisher.document_uploaded(
        document_id=document_id,
        project_id=1,
        filename=request.files['file'].filename,
        file_size=len(request.files['file'].read())
    )
    
    # 3. Queue async extraction
    job_id = JobQueueManager.queue_extraction(
        document_id=document_id,
        schema_id=request.form['schema_id'],
        project_id=1
    )
    
    return {
        "success": True,
        "document_id": document_id,
        "async_job_id": job_id
    }
```

### Pattern 2: Extraction with Hooks

```python
@app.route('/api/extractions/<doc_id>', methods=['POST'])
def start_extraction(doc_id):
    # 1. Execute before hooks
    execute_hooks(
        EventType.EXTRACTION_STARTED.value,
        "start_extraction",
        {"document_id": doc_id}
    )
    
    # 2. Perform extraction
    result_id = perform_extraction(doc_id)
    
    # 3. Execute after hooks
    execute_hooks(
        EventType.EXTRACTION_COMPLETED.value,
        "extraction_complete",
        {"document_id": doc_id, "result_id": result_id}
    )
    
    # 4. Publish event
    EventBusPublisher.extraction_completed(
        document_id=doc_id,
        schema_id=get_schema_id(doc_id),
        result_id=result_id,
        project_id=1
    )
    
    return {"success": True, "result_id": result_id}
```

### Pattern 3: Monitoring Job Progress

```python
@app.route('/api/jobs/<job_id>', methods=['GET'])
def get_job_progress(job_id):
    status = get_job_status(job_id)
    
    if not status:
        return {"error": "Job not found"}, 404
    
    return {
        "job_id": job_id,
        "status": status['status'],
        "progress": f"{status['retry_count']}/{status['max_retries']}",
        "started_at": status['started_at'],
        "completed_at": status['completed_at'],
        "error": status.get('error_message'),
        "logs": status.get('logs', [])
    }
```

---

## 9. Testing Integration

Example unit tests for integration:

```python
import pytest
from app.routes.integration import (
    publish_event, execute_hooks, queue_job,
    EventBusPublisher, JobQueueManager
)
from app.core import EventType, JobType, JobPriority

def test_publish_document_event():
    """Test publishing document event."""
    success = publish_event(
        EventType.DOCUMENT_UPLOADED.value,
        {"document_id": "test123"}
    )
    assert success is True

def test_event_bus_publisher():
    """Test EventBusPublisher convenience methods."""
    success = EventBusPublisher.document_uploaded(
        "doc123", 1, "test.pdf", 1000
    )
    assert success is True

def test_queue_extraction_job():
    """Test queuing extraction job."""
    job_id = queue_job(
        JobType.EXTRACT_DOCUMENT.value,
        {"document_id": "doc123"}
    )
    assert job_id is not None

def test_job_queue_manager():
    """Test JobQueueManager convenience methods."""
    job_id = JobQueueManager.queue_extraction(
        "doc123", 5, 1
    )
    assert job_id is not None

def test_execute_hooks_integration():
    """Test hook execution in integration flow."""
    results = execute_hooks(
        EventType.DOCUMENT_UPLOADED.value,
        "test_operation",
        {"document_id": "doc123"}
    )
    assert "success" in results
```

---

## 10. Best Practices

### 1. Always Check Return Values

```python
# Good
job_id = queue_job(...)
if job_id:
    # Use job_id
else:
    # Handle failure gracefully
    log_error("Job queueing failed")

# Avoid - Silent failures
job_id = queue_job(...)  # May be None!
# Later: job_id.something  # Will fail
```

### 2. Use Appropriate Event Types

```python
# Good - Specific event types
EventBusPublisher.document_uploaded(...)
EventBusPublisher.extraction_started(...)

# Avoid - Generic events
publish_event("custom_event", ...  )
```

### 3. Include Relevant Metadata

```python
# Good - Rich context
queue_job(
    job_type,
    input_data,
    metadata={
        "user_id": user_id,
        "source": "web_api",
        "initiator": "document_upload"
    }
)

# Avoid - Empty metadata
queue_job(job_type, input_data, metadata={})
```

### 4. Handle Optional Async Jobs

```python
# Good - Check before using
job_id = JobQueueManager.queue_extraction(...)
if job_id:
    response["async_job_id"] = job_id

# Avoid - Assume success
response["async_job_id"] = queue_job(...)  # May be None
```

### 5. Log Integration Operations

```python
# Good - Comprehensive logging
logger.info(f"Publishing {event_type} for {operation}")
logger.info(f"Queued job {job_id} for {job_type}")
logger.error(f"Failed to {operation}: {error}")

# Avoid - No logging
publish_event(...)
queue_job(...)
```

---

## 11. Common Issues and Solutions

### Issue 1: Event Not Being Handled
**Symptom**: Event publishes successfully but hooks don't execute

**Solution**: Verify hook is registered for event type
```python
from app.core import get_hook_registry, EventType

registry = get_hook_registry()
# Check if hook is registered
handlers = registry.get_hooks_for_event(EventType.DOCUMENT_UPLOADED.value)
print(f"Registered hooks: {handlers}")
```

### Issue 2: Job Not Executing
**Symptom**: Job queued but never executes

**Solution**: Verify handler is registered
```python
from app.core import get_job_registry, JobType

registry = get_job_registry()
# Check if handler exists
handler = registry.get(JobType.EXTRACT_DOCUMENT.value)
if not handler:
    print("No handler registered for extraction")
```

### Issue 3: Database Lock
**Symptom**: JobQueue operations timeout

**Solution**: Use WAL mode (already enabled)
```python
# Already configured in JobQueue:
# conn.execute('PRAGMA journal_mode=WAL')
```

---

## 12. Migration Guide

### Migrating Existing Routes

**Before**:
```python
@app.route('/api/documents', methods=['POST'])
def upload():
    # Only database operations
    doc = Document.create(...)
    return {"success": True, "id": doc.id}
```

**After**:
```python
@app.route('/api/documents', methods=['POST'])
def upload():
    # 1. Create document (same as before)
    doc = Document.create(...)
    
    # 2. Add event publishing
    EventBusPublisher.document_uploaded(
        doc.id, doc.project_id, doc.filename, doc.file_size
    )
    
    # 3. Add async processing (optional)
    job_id = JobQueueManager.queue_extraction(
        doc.id, request.json['schema_id'], doc.project_id
    )
    
    return {
        "success": True,
        "id": doc.id,
        "async_job_id": job_id
    }
```

Or use the decorator for minimal changes:
```python
@app.route('/api/documents', methods=['POST'])
@integrated_operation(
    operation_name="upload_document",
    event_type=EventType.DOCUMENT_UPLOADED.value,
    hooks_after=True
)
def upload():
    doc = Document.create(...)
    return {
        "success": True,
        "id": doc.id,
        "document_id": doc.id  # Required for event
    }
```

---

## 13. Performance Considerations

### Event Publishing
- **Time**: < 1ms for async publish
- **Thread-safe**: Yes (uses locks)
- **Memory**: Minimal (in-memory queue)

### Hook Execution
- **Time**: Depends on hook implementation (typically 5-50ms)
- **Isolation**: Error in one hook doesn't affect others
- **Threading**: Synchronous (blocks caller)

### Job Queueing
- **Time**: < 5ms (SQLite write)
- **Threading**: Async execution in background worker
- **Concurrency**: ThreadPoolExecutor with configurable workers

---

## 14. Monitoring and Debugging

### Get Integration Statistics

```python
from app.core import get_event_bus, get_hook_registry, get_job_queue

# Event statistics
bus = get_event_bus()
stats = bus.get_stats()
print(f"Total events: {stats['total_events']}")
print(f"Events by type: {stats['by_type']}")

# Hook statistics  
registry = get_hook_registry()
hook_stats = registry.get_stats()
print(f"Total hooks: {hook_stats['count']}")

# Job statistics
queue = get_job_queue()
job_stats = queue.get_stats()
print(f"Total jobs: {job_stats['total_jobs']}")
print(f"Pending jobs: {job_stats['pending_jobs']}")
```

### Debug Integration Flow

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# This will now show:
# - Event publishing details
# - Hook execution details  
# - Job queueing details
# - Any errors or exceptions
```

---

## 15. API Reference

### Functions

| Function | Purpose | Returns |
|----------|---------|---------|
| `publish_event()` | Publish event to EventBus | bool |
| `execute_hooks()` | Execute hooks for event | dict |
| `queue_job()` | Queue background job | str \| None (job_id) |
| `get_job_status()` | Get detailed job status | dict \| None |
| `register_job_handler()` | Register custom job handler | bool |

### Helper Classes

| Class | Purpose |
|-------|---------|
| `EventBusPublisher` | Convenience methods for common events |
| `JobQueueManager` | Convenience methods for common jobs |
| `RouteIntegrationContext` | Track operation metadata |

### Decorators

| Decorator | Purpose |
|-----------|---------|
| `@integrated_operation()` | Wrap route with unified flow |

---

## Summary

The Route Integration layer provides a clean, consistent API for:
- Publishing events from routes
- Executing hooks automatically
- Queuing background jobs
- Handling errors gracefully
- Monitoring integration flow

All components work together seamlessly with error isolation and comprehensive logging.

