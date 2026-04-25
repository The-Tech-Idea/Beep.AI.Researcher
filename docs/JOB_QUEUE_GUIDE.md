# Job Queue System - Phase 1.3

## Overview

The Job Queue System provides asynchronous background job processing with retry logic, priority queues, and SQLite persistence. Built on top of EventBus for event-driven architecture.

**Key Features**:
- SQLite-backed persistence (no external services)
- Priority-based execution (CRITICAL → LOW)
- Automatic retry with exponential backoff
- Background worker threads for async processing
- Integration with EventBus for job events
- Handler registry for custom job types
- Comprehensive statistics and monitoring

## Architecture

```
┌──────────────────────┐
│  Job Creation        │
│  (create_job)        │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  JobQueue (SQLite)   │
│  - Jobs stored       │
│  - Priority queue    │
│  - Status tracking   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Background Worker   │
│  - Thread pool       │
│  - Job execution     │
│  - Retry logic       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  Handler Registry    │
│  (execute handler)   │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│  EventBus Events     │
│  (job completion)    │
└──────────────────────┘
```

## Job Lifecycle

```
PENDING → RUNNING → COMPLETED
  ↓
  └─→ FAILED → RETRY → RUNNING → COMPLETED
               ↓
               └─→ FAILED (permanent)
```

## Key Components

### Job Class

Represents a unit of work with all metadata:

```python
@dataclass
class Job:
    job_id: str                      # Unique ID (UUID)
    job_type: str                    # Type of job (extract_document, web_search, etc.)
    status: str                      # Current status (pending, running, completed, failed, etc.)
    priority: int                    # Execution priority (CRITICAL=0 → LOW=3)
    input_data: Dict[str, Any]      # Input parameters for handler
    output_data: Dict[str, Any]     # Handler output
    error_message: Optional[str]     # Error if failed
    retry_count: int                 # Number of retries attempted
    max_retries: int                 # Maximum retry attempts (default 3)
    created_at: str                  # Creation timestamp
    started_at: Optional[str]        # Execution start time
    completed_at: Optional[str]      # Completion time
    next_retry_at: Optional[str]     # Time for next retry (exponential backoff)
    metadata: Dict[str, Any]         # Custom metadata
    logs: List[str]                  # Execution logs
```

### JobStatus Enum

```python
PENDING   = "pending"         # Waiting to execute
RUNNING   = "running"         # Currently executing
COMPLETED = "completed"       # Finished successfully
FAILED    = "failed"          # Permanently failed
CANCELLED = "cancelled"       # User cancelled
PAUSED    = "paused"          # Execution paused
RETRY     = "retry"           # Waiting for retry
SKIPPED   = "skipped"         # Skipped execution
```

### JobType Enum

```python
EXTRACT_DOCUMENT = "extract_document"      # Extract document content
WEB_SEARCH       = "web_search"            # Perform web search
PROCESS_DATASET  = "process_dataset"       # Process dataset
GENERATE_REPORT  = "generate_report"       # Generate report
SYSTEM_CLEANUP   = "system_cleanup"        # Cleanup operations
INDEX_UPDATE     = "index_update"          # Update search indexes
NOTIFICATION     = "notification"          # Send notifications
CUSTOM           = "custom"                # Custom job type
```

### JobPriority Enum

```python
CRITICAL = 0    # Highest priority
HIGH     = 1
NORMAL   = 2    # Default
LOW      = 3    # Lowest priority
```

### JobQueue Singleton

Central manager for all jobs:

```python
class JobQueue:
    def create_job(job_type, input_data, priority=Normal, max_retries=3)
    def get_job(job_id) -> Job
    def get_jobs_by_status(status) -> List[Job]
    def get_pending_jobs() -> List[Job]     # Sorted by priority
    def get_job_history(limit=100, offset=0, status=None) -> List[Job]
    def cancel_job(job_id) -> bool
    def retry_job(job_id) -> bool           # Manually retry failed job
    def get_stats() -> Dict
    def reset_stats()
    def stop()
```

### JobRegistry

Register handlers for job types:

```python
class JobRegistry:
    def register(job_type: str, handler: Callable)
    def unregister(job_type: str)
    def get_handler(job_type: str) -> Callable
    def has_handler(job_type: str) -> bool
    def get_all_handlers() -> Dict[str, Callable]
```

## Usage Guide

### Creating and Queuing Jobs

```python
from app.core import get_job_queue, JobPriority, JobType

queue = get_job_queue()

# Create a simple job
job = queue.create_job(
    job_type=JobType.EXTRACT_DOCUMENT.value,
    input_data={"document_id": "doc123", "format": "pdf"},
    priority=JobPriority.NORMAL,
    max_retries=3
)

print(f"Job created: {job.job_id}")

# Create a high-priority job
urgent_job = queue.create_job(
    job_type=JobType.WEB_SEARCH.value,
    input_data={"query": "latest research"},
    priority=JobPriority.CRITICAL
)
```

### Registering Job Handlers

Handlers are functions that process jobs:

```python
from app.core import get_job_registry, JobType

registry = get_job_registry()

# Define handler function
def extract_document_handler(input_data):
    """Handler for document extraction."""
    doc_id = input_data["document_id"]
    format_type = input_data.get("format", "pdf")
    
    # Perform extraction
    extracted_content = extract_from_document(doc_id, format_type)
    
    # Return result as dictionary
    return {
        "document_id": doc_id,
        "content": extracted_content,
        "pages": len(extracted_content),
        "success": True
    }

# Register handler
registry.register(JobType.EXTRACT_DOCUMENT.value, extract_document_handler)

# Handler is automatically called when job executes
```

### Getting Job Status

```python
queue = get_job_queue()

# Get specific job
job = queue.get_job("job_id_here")
print(f"Status: {job.status}")
print(f"Progress: {job.retry_count}/{job.max_retries} retries")
print(f"Logs: {job.logs}")

# Get all pending jobs (sorted by priority)
pending = queue.get_pending_jobs()
for job in pending:
    print(f"{job.job_id}: {job.job_type} (priority={job.priority})")

# Get job history with pagination
history = queue.get_job_history(limit=50, offset=0)
completed_jobs = queue.get_job_history(limit=100, status=JobStatus.COMPLETED)
```

### Controlling Jobs

```python
queue = get_job_queue()

# Cancel a pending/running job
success = queue.cancel_job("job_id")
if success:
    print("Job cancelled")

# Manually retry a failed job
retriable = queue.retry_job("failed_job_id")
if retriable:
    print("Job queued for retry")

# Get statistics
stats = queue.get_stats()
print(f"Total jobs: {stats['total_jobs']}")
print(f"Completed: {stats['completed']}")
print(f"Failed: {stats['failed']}")
print(f"Pending: {stats['jobs_pending']}")
```

## Advanced Features

### Retry Logic with Exponential Backoff

Failed jobs are automatically retried with exponential backoff:

```python
# First failure: retry in 2^1 = 2 seconds
# Second failure: retry in 2^2 = 4 seconds
# Third failure: retry in 2^3 = 8 seconds
# Fourth failure: permanent failure (exceeds max_retries=3)

job = queue.create_job(
    job_type=JobType.WEB_SEARCH.value,
    input_data={"query": "test"},
    max_retries=5  # Allow more retries
)
```

### Priority-Based Execution

Jobs are executed in priority order by the background worker:

```python
# Create jobs with different priorities
critical_job = queue.create_job(
    job_type=JobType.GENERATE_REPORT.value,
    input_data={...},
    priority=JobPriority.CRITICAL  # Executes first
)

high_job = queue.create_job(
    job_type=JobType.EXTRACT_DOCUMENT.value,
    input_data={...},
    priority=JobPriority.HIGH  # Executes second
)

normal_job = queue.create_job(
    job_type=JobType.PROCESS_DATASET.value,
    input_data={...},
    priority=JobPriority.NORMAL  # Executes last
)
```

### Job Metadata and Logging

```python
job = queue.create_job(
    job_type=JobType.EXTRACT_DOCUMENT.value,
    input_data={"doc_id": "doc123"},
    metadata={
        "user_id": "user456",
        "project_id": "proj789",
        "source": "api"
    }
)

# Logs are automatically added during execution
# Access logs to debug job execution
completed_job = queue.get_job(job.job_id)
for log_entry in completed_job.logs:
    print(log_entry)
```

### Handler with Error Handling

```python
def search_handler(input_data):
    """Search with graceful error handling."""
    try:
        query = input_data["query"]
        results = perform_search(query)
        return {
            "query": query,
            "results": results,
            "count": len(results)
        }
    except TimeoutError:
        # Timeout errors should be retriable
        raise TimeoutError("Search timeout")
    except ValueError as e:
        # Value errors should NOT be retriable
        raise ValueError(f"Invalid query: {e}")

registry.register(JobType.WEB_SEARCH.value, search_handler)
```

## Integration with EventBus

Job Queue events are published to EventBus:

```python
from app.core import get_event_bus, EventType

# Listen for job completions
bus = get_event_bus()

@bus.event_handler(EventType.TASK_STATUS_CHANGED.value)
def on_job_complete(event):
    job_id = event.data.get("job_id")
    status = event.data.get("status")
    
    if status == "completed":
        print(f"Job {job_id} completed!")
    elif status == "failed":
        print(f"Job {job_id} failed!")
```

## Configuration

### SQLite Backend

By default, jobs are stored in `job_queue.db`:

```python
# Use custom database path
queue = JobQueue(db_path="/var/lib/app/jobs.db", num_workers=8)

# Load singleton instance
queue = get_job_queue(db_path="custom_path.db", num_workers=4)
```

### Worker Threads

Control concurrency with worker count:

```python
# Default: 4 worker threads
queue = get_job_queue(num_workers=4)

# High concurrency
queue = get_job_queue(num_workers=16)

# Low concurrency
queue = get_job_queue(num_workers=1)
```

## Database Schema

SQLite table structure:

```sql
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL,
    input_data TEXT,              -- JSON string
    output_data TEXT,             -- JSON string
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    next_retry_at TEXT,
    metadata TEXT,                -- JSON string
    logs TEXT,                    -- JSON array
    created_index INTEGER DEFAULT 0
);

CREATE INDEX idx_status ON jobs(status);
CREATE INDEX idx_priority ON jobs(priority);
CREATE INDEX idx_created ON jobs(created_at);
```

## Error Handling & Troubleshooting

### Job Stuck in Running State

```python
# Reset stuck job
stuck_job = queue.get_job("stuck_job_id")
if stuck_job.status == JobStatus.RUNNING.value:
    # Mark as failed and retry
    stuck_job.status = JobStatus.FAILED.value
    queue._save_job_to_db(stuck_job)
    queue.retry_job(stuck_job.job_id)
```

### Handler Not Found

```python
# Ensure handler is registered before job executes
from app.core import get_job_registry, JobType

registry = get_job_registry()

# Check if handler exists
if not registry.has_handler(JobType.EXTRACT_DOCUMENT.value):
    registry.register(
        JobType.EXTRACT_DOCUMENT.value,
        extract_document_handler
    )
```

### Database Issues

```python
# Verify database integrity
queue = get_job_queue()
with queue._get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jobs")
    job_count = cursor.fetchone()[0]
    print(f"Total jobs in database: {job_count}")
```

## Performance Considerations

- **Typical Handler Execution**: <100ms - 1 second
- **Job Creation**: <1ms
- **Database Query**: <5ms
- **Worker Check Interval**: 1 second (configurable)
- **Memory per Job**: ~2KB baseline
- **Max Concurrent Jobs**: Limited by worker threads (default 4)

## Best Practices

### 1. Keep Handlers Lightweight

```python
# ✅ Good - handler does focused work
def extract_handler(data):
    doc_id = data["document_id"]
    return extract_content(doc_id)

# ❌ Avoid - handler does too much
def bad_handler(data):
    doc = fetch_document(data["id"])
    extract = extract_content(doc)
    index = index_document(extract)
    notify = send_notification(user_id)
    return {"all": "results"}
```

### 2. Handle Exceptions Appropriately

```python
# ✅ Good - distinguish retriable vs permanent errors
def api_handler(data):
    try:
        result = call_external_api(data)
        return result
    except ConnectionError:
        raise  # Retriable - connection issues
    except ValueError:
        return {"error": "Invalid input"}  # Not retriable

# ❌ Avoid - catch everything
def bad_handler(data):
    try:
        return risky_operation(data)
    except Exception:
        return None  # Loses error context
```

### 3. Use Appropriate Priority

```python
# ✅ Good - priority matches importance
queue.create_job(
    JobType.EXTRACT_DOCUMENT.value,
    {"id": doc_id},
    priority=JobPriority.CRITICAL  # User-initiated
)

# ❌ Avoid - wrong priority
queue.create_job(
    JobType.SYSTEM_CLEANUP.value,
    {},
    priority=JobPriority.CRITICAL  # Cleanup shouldn't interrupt
)
```

### 4. Set Appropriate Max Retries

```python
# ✅ Good - retry flaky external calls
queue.create_job(
    JobType.WEB_SEARCH.value,
    data,
    max_retries=5  # Network calls can be flaky
)

# ✅ Good - don't retry invalid data
queue.create_job(
    JobType.EXTRACT_DOCUMENT.value,
    data,
    max_retries=1  # Invalid doc won't be fixed by retry
)
```

## Summary

**Phase 1.3 Deliverables**:
- [x] SQLite-backed job queue with persistence
- [x] Background worker threads for async processing
- [x] Retry logic with exponential backoff
- [x] Priority-based execution ordering
- [x] Handler registry for custom job types
- [x] Job lifecycle management (create, execute, retry, cancel)
- [x] Event integration with EventBus
- [x] Comprehensive statistics and monitoring
- [x] 41 unit tests (100% pass rate)
- [x] Complete documentation

**Ready for**: Phase 1.4 (Route Integration)
