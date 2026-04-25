"""
Job Queue System for asynchronous background job processing.

Provides SQLite-backed job queue with retry logic, priority execution,
and background worker threads. Integrates with EventBus for job events.

Uses APScheduler for scheduling and ThreadPoolExecutor for execution.
Zero external service dependencies (no Redis/Celery needed).
"""

import sqlite3
import threading
import time
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import traceback

from app.core.event_bus import Event, EventType, get_event_bus

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    RETRY = "retry"
    SKIPPED = "skipped"


class JobType(str, Enum):
    """Types of jobs that can be queued."""
    EXTRACT_DOCUMENT = "extract_document"
    WEB_SEARCH = "web_search"
    PROCESS_DATASET = "process_dataset"
    GENERATE_REPORT = "generate_report"
    PDF_DOWNLOAD = "pdf_download"
    SYSTEM_CLEANUP = "system_cleanup"
    INDEX_UPDATE = "index_update"
    NOTIFICATION = "notification"
    CUSTOM = "custom"


class JobPriority(int, Enum):
    """Job priority for execution ordering."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3

    def __lt__(self, other):
        if not isinstance(other, JobPriority):
            return NotImplemented
        return self.value < other.value


@dataclass
class JobResult:
    """Result of job execution."""
    success: bool
    output: Any = None
    error: Optional[str] = None
    executed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    execution_time_ms: float = 0.0


@dataclass
class Job:
    """Job object for queue processing."""
    job_id: str = field(default_factory=lambda: str(uuid4()))
    job_type: str = field(default=JobType.CUSTOM.value)
    status: str = field(default=JobStatus.PENDING.value)
    priority: int = field(default=JobPriority.NORMAL.value)
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    next_retry_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    created_index: int = 0  # For database ordering

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for storage."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert job to JSON string."""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Create job from dictionary."""
        return cls(**data)

    def add_log(self, message: str) -> None:
        """Add log message to job."""
        timestamp = datetime.now(timezone.utc).isoformat()
        self.logs.append(f"[{timestamp}] {message}")

    def is_retriable(self) -> bool:
        """Check if job can be retried."""
        return self.retry_count < self.max_retries and self.status == JobStatus.FAILED.value

    def mark_for_retry(self) -> None:
        """Mark job for retry with exponential backoff."""
        if not self.is_retriable():
            return

        self.retry_count += 1
        # Exponential backoff: 2^retry_count seconds
        delay_seconds = 2 ** self.retry_count
        self.next_retry_at = (datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)).isoformat()
        self.status = JobStatus.RETRY.value
        self.add_log(f"Marked for retry (attempt {self.retry_count}/{self.max_retries}) in {delay_seconds}s")


class JobRegistry:
    """Registry of handler functions for job types."""
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}

    @classmethod
    def get_instance(cls) -> "JobRegistry":
        """Get singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, job_type: str, handler: Callable) -> None:
        """Register handler for job type."""
        if not callable(handler):
            raise ValueError(f"Handler must be callable, got {type(handler)}")
        self._handlers[job_type] = handler
        logger.info(f"Registered handler for job type: {job_type}")

    def unregister(self, job_type: str) -> None:
        """Unregister handler for job type."""
        if job_type in self._handlers:
            del self._handlers[job_type]
            logger.info(f"Unregistered handler for job type: {job_type}")

    def get_handler(self, job_type: str) -> Optional[Callable]:
        """Get handler for job type."""
        return self._handlers.get(job_type)

    def has_handler(self, job_type: str) -> bool:
        """Check if handler exists for job type."""
        return job_type in self._handlers

    def get_all_handlers(self) -> Dict[str, Callable]:
        """Get all registered handlers."""
        return self._handlers.copy()


class JobQueue:
    """SQLite-backed job queue with background worker."""
    _instance = None
    _lock = threading.Lock()

    def __init__(self, db_path: str = "job_queue.db", num_workers: int = 4):
        self.db_path = db_path
        self.num_workers = num_workers
        self._executor = ThreadPoolExecutor(max_workers=num_workers, thread_name_prefix="job-worker")
        self._worker_running = False
        self._worker_thread = None
        self._jobs: Dict[str, Job] = {}  # In-memory cache
        self._statistics = {
            "total_jobs": 0,
            "completed": 0,
            "failed": 0,
            "retried": 0,
            "cancelled": 0,
            "skipped": 0,
        }
        self._init_db()
        self._start_worker()

    @classmethod
    def get_instance(cls, db_path: str = "job_queue.db", num_workers: int = 4) -> "JobQueue":
        """Get singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(db_path, num_workers)
        return cls._instance

    def _init_db(self) -> None:
        """Initialize SQLite database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    input_data TEXT,
                    output_data TEXT,
                    error_message TEXT,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    next_retry_at TEXT,
                    metadata TEXT,
                    logs TEXT,
                    created_index INTEGER DEFAULT 0
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_priority ON jobs(priority)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_created ON jobs(created_at)
            """)
            conn.commit()
            logger.info(f"Job queue database initialized at {self.db_path}")

    @contextmanager
    def _get_connection(self):
        """Context manager for database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _load_jobs_from_db(self) -> None:
        """Load all jobs from database into memory cache."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs")
            rows = cursor.fetchall()
            for row in rows:
                job_data = dict(row)
                # Parse JSON fields
                if job_data.get("input_data"):
                    job_data["input_data"] = json.loads(job_data["input_data"])
                if job_data.get("output_data"):
                    job_data["output_data"] = json.loads(job_data["output_data"])
                if job_data.get("metadata"):
                    job_data["metadata"] = json.loads(job_data["metadata"])
                if job_data.get("logs"):
                    job_data["logs"] = json.loads(job_data["logs"])
                else:
                    job_data["logs"] = []
                
                self._jobs[job_data["job_id"]] = Job.from_dict(job_data)

    def _save_job_to_db(self, job: Job) -> None:
        """Save job to database."""
        job_dict = job.to_dict()
        job_dict["input_data"] = json.dumps(job.input_data)
        job_dict["output_data"] = json.dumps(job.output_data)
        job_dict["metadata"] = json.dumps(job.metadata)
        job_dict["logs"] = json.dumps(job.logs)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO jobs
                (job_id, job_type, status, priority, input_data, output_data, 
                 error_message, retry_count, max_retries, created_at, started_at, 
                 completed_at, next_retry_at, metadata, logs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.job_id, job.job_type, job.status, job.priority,
                job_dict["input_data"], job_dict["output_data"],
                job.error_message, job.retry_count, job.max_retries,
                job.created_at, job.started_at, job.completed_at,
                job.next_retry_at, job_dict["metadata"], job_dict["logs"]
            ))
            conn.commit()

    def create_job(self, job_type: str, input_data: Dict[str, Any],
                   priority: JobPriority = JobPriority.NORMAL,
                   max_retries: int = 3, metadata: Dict[str, Any] = None) -> Job:
        """Create new job and add to queue."""
        job = Job(
            job_type=job_type,
            priority=priority.value,
            input_data=input_data,
            max_retries=max_retries,
            metadata=metadata or {}
        )
        self._jobs[job.job_id] = job
        self._save_job_to_db(job)
        self._statistics["total_jobs"] += 1
        
        # Publish event
        bus = get_event_bus()
        event = Event(
            event_type=EventType.TASK_CREATED.value,
            data={"job_id": job.job_id, "job_type": job.job_type, "status": "created"},
            source="job_queue"
        )
        bus.publish(event)
        
        logger.info(f"Created job {job.job_id} of type {job.job_type}")
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return self._jobs.get(job_id)

    def get_jobs_by_status(self, status: JobStatus) -> List[Job]:
        """Get all jobs with given status."""
        return [job for job in self._jobs.values() if job.status == status.value]

    def get_pending_jobs(self) -> List[Job]:
        """Get pending jobs sorted by priority."""
        pending = [job for job in self._jobs.values() 
                  if job.status in (JobStatus.PENDING.value, JobStatus.RETRY.value)]
        return sorted(pending, key=lambda j: j.priority)

    def get_job_history(self, limit: int = 100, offset: int = 0,
                        status: Optional[JobStatus] = None) -> List[Job]:
        """Get job history with pagination."""
        jobs = list(self._jobs.values())
        
        if status:
            jobs = [j for j in jobs if j.status == status.value]
        
        # Sort by created_at descending
        jobs = sorted(jobs, key=lambda j: j.created_at, reverse=True)
        
        return jobs[offset:offset + limit]

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        job = self.get_job(job_id)
        if not job:
            return False

        if job.status in (JobStatus.COMPLETED.value, JobStatus.FAILED.value):
            return False  # Can't cancel finished jobs

        job.status = JobStatus.CANCELLED.value
        job.completed_at = datetime.now(timezone.utc).isoformat()
        self._save_job_to_db(job)
        self._statistics["cancelled"] += 1
        
        logger.info(f"Cancelled job {job_id}")
        return True

    def retry_job(self, job_id: str) -> bool:
        """Manually retry a failed job."""
        job = self.get_job(job_id)
        if not job or job.status != JobStatus.FAILED.value:
            return False

        if not job.is_retriable():
            return False

        job.mark_for_retry()
        self._save_job_to_db(job)
        self._statistics["retried"] += 1
        
        logger.info(f"Manually retried job {job_id}")
        return True

    def _execute_job(self, job: Job) -> JobResult:
        """Execute a job with registered handler."""
        job.started_at = datetime.now(timezone.utc).isoformat()
        job.status = JobStatus.RUNNING.value
        self._save_job_to_db(job)

        start_time = time.time()
        result = None

        try:
            registry = JobRegistry.get_instance()
            handler = registry.get_handler(job.job_type)

            if not handler:
                error_msg = f"No handler registered for job type: {job.job_type}"
                job.add_log(error_msg)
                job.status = JobStatus.FAILED.value
                job.error_message = error_msg
                self._statistics["failed"] += 1
                return JobResult(success=False, error=error_msg)

            # Execute handler
            job.add_log(f"Starting execution with handler: {handler.__name__}")
            output = handler(job.input_data)
            
            execution_time = time.time() - start_time
            job.output_data = output if isinstance(output, dict) else {"result": output}
            job.status = JobStatus.COMPLETED.value
            job.completed_at = datetime.now(timezone.utc).isoformat()
            job.add_log(f"Completed successfully in {execution_time:.2f}s")
            self._statistics["completed"] += 1

            result = JobResult(success=True, output=job.output_data, 
                             execution_time_ms=execution_time * 1000)

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"{type(e).__name__}: {str(e)}"
            job.error_message = error_msg
            job.add_log(f"Execution failed: {error_msg}")
            job.add_log(f"Traceback: {traceback.format_exc()}")

            # Mark as failed first
            job.status = JobStatus.FAILED.value
            
            # Then check if retriable
            if job.is_retriable():
                job.mark_for_retry()
                self._statistics["retried"] += 1
                logger.warning(f"Job {job.job_id} failed, will retry. Attempt {job.retry_count}/{job.max_retries}")
            else:
                job.completed_at = datetime.now(timezone.utc).isoformat()
                self._statistics["failed"] += 1
                logger.error(f"Job {job.job_id} failed permanently: {error_msg}")

            result = JobResult(success=False, error=error_msg, 
                             execution_time_ms=execution_time * 1000)

        finally:
            self._save_job_to_db(job)
            # Publish event
            bus = get_event_bus()
            event = Event(
                event_type=EventType.TASK_STATUS_CHANGED.value,
                data={
                    "job_id": job.job_id,
                    "job_type": job.job_type,
                    "status": job.status,
                    "success": result.success if result else False,
                    "error": result.error if result else None
                },
                source="job_queue"
            )
            bus.publish(event)

        return result

    def _worker(self) -> None:
        """Background worker thread that processes jobs."""
        logger.info(f"Job queue worker started with {self.num_workers} threads")
        
        while self._worker_running:
            try:
                pending = self.get_pending_jobs()
                
                if pending:
                    for job in pending:
                        # Check if retry job is ready
                        if job.status == JobStatus.RETRY.value:
                            if job.next_retry_at:
                                retry_time = datetime.fromisoformat(job.next_retry_at)
                                if datetime.now(timezone.utc) < retry_time:
                                    continue  # Not ready yet

                        # Submit for execution
                        self._executor.submit(self._execute_job, job)

                time.sleep(1)  # Check every second for new jobs
            except Exception as e:
                logger.error(f"Error in job queue worker: {e}", exc_info=True)
                time.sleep(1)

    def _start_worker(self) -> None:
        """Start background worker thread."""
        self._load_jobs_from_db()
        self._worker_running = True
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()
        logger.info("Job queue worker thread started")

    def stop(self) -> None:
        """Stop job queue and background workers."""
        logger.info("Stopping job queue...")
        self._worker_running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5)
        self._executor.shutdown(wait=True)
        logger.info("Job queue stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            **self._statistics,
            "jobs_pending": len(self.get_pending_jobs()),
            "jobs_running": len(self.get_jobs_by_status(JobStatus.RUNNING)),
            "workers_available": self.num_workers,
        }

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._statistics = {
            "total_jobs": len(self._jobs),
            "completed": 0,
            "failed": 0,
            "retried": 0,
            "cancelled": 0,
            "skipped": 0,
        }


def get_job_queue(db_path: str = "job_queue.db", num_workers: int = 4) -> JobQueue:
    """Get singleton job queue instance."""
    return JobQueue.get_instance(db_path, num_workers)


def get_job_registry() -> JobRegistry:
    """Get singleton job registry instance."""
    return JobRegistry.get_instance()
