# SQLite-Based Implementation Guide
## (Replacing Redis/External Dependencies)

**Date**: February 7, 2026  
**Purpose**: Reference guide for implementing caching, job queues, and session management using SQLite instead of Redis

---

## Overview

Instead of adding **Redis** as an external dependency, use **SQLite** (already included) with:
- **APScheduler** for background job scheduling
- **SQLAlchemy** ORM for cache tables
- **Python's in-memory caching** (functools.lru_cache) for hot data
- **SQLite WAL mode** for concurrent access

---

## 1. Job Queue with SQLite + APScheduler

### Installation
```bash
pip install apscheduler
```

### Implementation

#### Create Job Queue Model
```python
# beep/models/job.py
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Integer, DateTime, JSON, Boolean
from beep.database import db

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class Job(db.Model):
    __tablename__ = 'jobs'
    
    id = Column(String(36), primary_key=True)  # UUID
    job_type = Column(String(50), nullable=False)  # extract_document, web_search, etc.
    status = Column(String(20), default=JobStatus.PENDING)
    priority = Column(Integer, default=0)
    
    # Payload for job
    payload = Column(JSON, nullable=False)  # {project_id, document_id, extraction_schema_id, ...}
    
    # Results
    result = Column(JSON, nullable=True)
    error_message = Column(String(500), nullable=True)
    
    # Retry tracking
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    next_retry_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # User tracking
    created_by = Column(String(100), nullable=True)
```

#### Create Job Queue Manager
```python
# beep/core/job_queue.py
import uuid
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.threadpool import ThreadPoolExecutor
from beep.models.job import Job, JobStatus
from beep.database import db

class JobQueue:
    def __init__(self, max_workers=4):
        self.scheduler = BackgroundScheduler(
            executor=ThreadPoolExecutor(max_workers=max_workers),
            job_defaults={'coalesce': True, 'max_instances': 1}
        )
        self.max_workers = max_workers
    
    def start(self):
        """Start the job queue processor"""
        if not self.scheduler.running:
            self.scheduler.start()
            print(f"Job queue started with {self.max_workers} workers")
    
    def stop(self):
        """Stop the job queue processor"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("Job queue stopped")
    
    def submit_job(self, job_type: str, payload: dict, priority=0) -> str:
        """
        Submit a job to the queue.
        
        Args:
            job_type: extract_document, web_search, generate_report, etc.
            payload: {project_id, document_id, ...}
            priority: 0 (normal), 1 (high), -1 (low)
        
        Returns:
            job_id
        """
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            job_type=job_type,
            status=JobStatus.PENDING,
            priority=priority,
            payload=payload,
            max_retries=3
        )
        db.session.add(job)
        db.session.commit()
        
        # Schedule immediate processing
        self.scheduler.add_job(
            self._process_job,
            args=[job_id],
            id=job_id,
            replace_existing=True
        )
        
        return job_id
    
    def _process_job(self, job_id: str):
        """Internal: Process a single job"""
        try:
            job = Job.query.get(job_id)
            if not job:
                return
            
            job.status = JobStatus.RUNNING
            job.started_at = datetime.utcnow()
            db.session.commit()
            
            # Execute job based on type
            if job.job_type == "extract_document":
                result = self._execute_extract_document(job.payload)
            elif job.job_type == "web_search":
                result = self._execute_web_search(job.payload)
            elif job.job_type == "generate_report":
                result = self._execute_generate_report(job.payload)
            else:
                raise ValueError(f"Unknown job type: {job.job_type}")
            
            # Mark as completed
            job.status = JobStatus.COMPLETED
            job.result = result
            job.completed_at = datetime.utcnow()
            db.session.commit()
            
        except Exception as e:
            # Handle retry logic
            job = Job.query.get(job_id)
            job.error_message = str(e)
            
            if job.retry_count < job.max_retries:
                job.status = JobStatus.RETRYING
                job.retry_count += 1
                # Exponential backoff: 2^retry_count seconds
                delay_seconds = 2 ** job.retry_count
                job.next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
                
                # Reschedule
                self.scheduler.add_job(
                    self._process_job,
                    args=[job_id],
                    id=job_id,
                    trigger='date',
                    run_date=job.next_retry_at,
                    replace_existing=True
                )
            else:
                job.status = JobStatus.FAILED
                job.completed_at = datetime.utcnow()
            
            db.session.commit()
    
    # Job execution methods (implement these with actual logic)
    def _execute_extract_document(self, payload):
        """Extract data from document"""
        pass
    
    def _execute_web_search(self, payload):
        """Search academic sources"""
        pass
    
    def _execute_generate_report(self, payload):
        """Generate research report"""
        pass
    
    def get_job_status(self, job_id: str) -> dict:
        """Get job status and result"""
        job = Job.query.get(job_id)
        if not job:
            return None
        
        return {
            'id': job.id,
            'type': job.job_type,
            'status': job.status,
            'result': job.result,
            'error_message': job.error_message,
            'retry_count': job.retry_count,
            'max_retries': job.max_retries,
            'created_at': job.created_at.isoformat(),
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        }
    
    def cancel_job(self, job_id: str):
        """Cancel a pending/retrying job"""
        job = Job.query.get(job_id)
        if job and job.status in [JobStatus.PENDING, JobStatus.RETRYING]:
            job.status = JobStatus.FAILED
            job.error_message = "Cancelled by user"
            job.completed_at = datetime.utcnow()
            db.session.commit()
            
            # Remove from scheduler
            try:
                self.scheduler.remove_job(job_id)
            except:
                pass
```

#### Initialize in Flask App
```python
# beep/app.py
from beep.core.job_queue import JobQueue

# Create global job queue
job_queue = JobQueue(max_workers=4)

def create_app():
    app = Flask(__name__)
    
    # ... other setup ...
    
    # Start job queue on app startup
    @app.before_first_request
    def start_job_queue():
        job_queue.start()
    
    # Stop job queue on shutdown
    @app.teardown_appcontext
    def stop_job_queue(exception):
        job_queue.stop()
    
    return app
```

---

## 2. Caching with SQLite + In-Memory LRU

### Create Cache Model
```python
# beep/models/cache.py
from datetime import datetime
from sqlalchemy import Column, String, DateTime, LargeBinary, Integer
from beep.database import db

class Cache(db.Model):
    __tablename__ = 'cache'
    
    key = Column(String(255), primary_key=True)
    value = Column(LargeBinary, nullable=False)  # Pickle serialized value
    expires_at = Column(DateTime, nullable=True)
    hit_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Create Cache Manager
```python
# beep/core/cache_manager.py
import pickle
from functools import lru_cache
from datetime import datetime, timedelta
from beep.models.cache import Cache
from beep.database import db

class CacheManager:
    def __init__(self, memory_size=1000, db_ttl_hours=24):
        """
        Args:
            memory_size: LRU cache size (most frequently used queries)
            db_ttl_hours: How long to keep entries in database
        """
        self.memory_size = memory_size
        self.db_ttl_hours = db_ttl_hours
        self._init_lru_cache()
    
    def _init_lru_cache(self):
        """Initialize in-memory cache"""
        @lru_cache(maxsize=self.memory_size)
        def _memory_cache_get(key):
            """Fetch from memory (hit = cache hit)"""
            return key
        
        self._memory_cache_get = _memory_cache_get
    
    def get(self, key: str):
        """
        Get cached value.
        Tries: memory cache → database
        """
        # Try memory cache first
        try:
            cache_entry = Cache.query.filter_by(key=key).first()
            if cache_entry:
                if cache_entry.expires_at and cache_entry.expires_at < datetime.utcnow():
                    # Expired, delete it
                    db.session.delete(cache_entry)
                    db.session.commit()
                    return None
                
                # Update hit count and return
                cache_entry.hit_count += 1
                db.session.commit()
                
                return pickle.loads(cache_entry.value)
        except:
            pass
        
        return None
    
    def set(self, key: str, value, ttl_hours=None):
        """
        Set cached value.
        Args:
            key: Cache key
            value: Any pickleable Python object
            ttl_hours: Time to live (None = use default 24h)
        """
        ttl = ttl_hours or self.db_ttl_hours
        expires_at = datetime.utcnow() + timedelta(hours=ttl)
        
        # Check if exists
        cache_entry = Cache.query.filter_by(key=key).first()
        if cache_entry:
            cache_entry.value = pickle.dumps(value)
            cache_entry.expires_at = expires_at
            cache_entry.updated_at = datetime.utcnow()
        else:
            cache_entry = Cache(
                key=key,
                value=pickle.dumps(value),
                expires_at=expires_at
            )
            db.session.add(cache_entry)
        
        db.session.commit()
    
    def delete(self, key: str):
        """Delete cached value"""
        Cache.query.filter_by(key=key).delete()
        db.session.commit()
    
    def clear_expired(self):
        """Remove expired entries (run periodically)"""
        Cache.query.filter(Cache.expires_at < datetime.utcnow()).delete()
        db.session.commit()
    
    def invalidate_pattern(self, pattern: str):
        """
        Invalidate keys matching pattern (e.g., 'project_123:*')
        Uses LIKE query
        """
        Cache.query.filter(Cache.key.like(pattern)).delete()
        db.session.commit()
```

### Usage Examples
```python
# Use cache manager
from beep.core.cache_manager import CacheManager

cache = CacheManager()

# Cache search results
cache_key = f"search:{project_id}:{provider}:{query}"
results = cache.get(cache_key)

if not results:
    # Fetch from API
    results = academic_search(provider, query)
    cache.set(cache_key, results, ttl_hours=24)

# Invalidate when new document uploaded
cache.invalidate_pattern(f"search:{project_id}:*")

# Clear expired entries (run via scheduled job weekly)
cache.clear_expired()
```

---

## 3. Session & Data Persistence

### Use SQLAlchemy Sessions
```python
# Sessions are already persistent in SQLAlchemy/SQLite
# No extra config needed - data survives app restarts

# Example: Store conversation state
class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    
    id = Column(String(36), primary_key=True)
    project_id = Column(String(36), nullable=False)
    messages = Column(JSON)  # List of {role, content, timestamp}
    context = Column(JSON)   # {documents, codes, etc.}
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

---

## 4. Database Optimization for Concurrency

### Enable SQLite WAL Mode
```python
# beep/database.py
from sqlalchemy import event
from sqlalchemy.pool import StaticPool

def init_db(app):
    # ... existing setup ...
    
    # Enable WAL mode for better concurrency
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")  # Balance safety/speed
        cursor.execute("PRAGMA cache_size=-64000")   # 64MB cache
        dbapi_connection.commit()
```

### Connection Pooling
```python
# In app config
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
    'max_overflow': 20,
}
```

---

## 5. Migration from Todo.md Tasks

Copy these implementations to your codebase:

### Phase 1 Job Queue Tasks
- [x] Replace "Redis-backed queue" → "SQLite + APScheduler job queue"
- [x] Add Job model migration
- [x] Update config to use SQLite

### Phase 2 Caching Tasks
- [x] Replace "Redis cache" → "SQLite cache + in-memory LRU"
- [x] Add Cache model migration  
- [x] Implement CacheManager

### DevOps / Configuration
- [x] Replace "Redis URL config" → "SQLite WAL mode config"
- [x] Update monitoring (job queue table size instead of Redis memory)
- [x] Add cache cleanup job (weekly)

---

## 6. Performance Considerations

### When to use In-Memory vs Database Cache

| Use Case | Cache Type | Why |
|----------|-----------|-----|
| Hot queries (web search) | Memory LRU | <1ms access time |
| Session data (chat) | Database | Survives restarts |
| Job results | Database | Needed for retry logic |
| Rate limiting counters | Database | Persisted across processes |
| Code snippets (recently used) | Memory LRU | Fast access pattern |

### Scaling Considerations

**If you need to scale horizontally** (multiple app servers):
- Use database cache (auto-synced)
- Job queue works across servers (SQLite with file locking)
- Consider future migration to PostgreSQL (drop-in replacement)

**For single-server deployments** (most cases initially):
- SQLite + WAL is perfectly fine
- In-memory LRU + database hybrid is fast
- No external infrastructure

---

## 7. Testing

### Unit Tests for Job Queue
```python
def test_submit_job():
    job_id = job_queue.submit_job("extract_document", {"doc_id": "123"})
    assert job_id is not None
    
    status = job_queue.get_job_status(job_id)
    assert status['status'] in ['pending', 'running']

def test_job_retry():
    # Submit failing job, verify retry
    job_id = job_queue.submit_job("failing_job", {})
    time.sleep(2)  # Wait for retry
    
    status = job_queue.get_job_status(job_id)
    assert status['retry_count'] == 1
```

### Unit Tests for Cache
```python
def test_cache_set_get():
    cache.set("key1", {"data": "value"})
    assert cache.get("key1") == {"data": "value"}

def test_cache_expiration():
    cache.set("key2", "value", ttl_hours=0.001)  # ~4 seconds
    time.sleep(5)
    assert cache.get("key2") is None

def test_cache_invalidate_pattern():
    cache.set("search:proj1:query1", "result1")
    cache.set("search:proj1:query2", "result2")
    cache.set("search:proj2:query1", "result3")
    
    cache.invalidate_pattern("search:proj1:*")
    
    assert cache.get("search:proj1:query1") is None
    assert cache.get("search:proj2:query1") is not None
```

---

## 8. No Additional Dependencies

### Only New Package Required
```bash
pip install apscheduler
```

That's it! No Redis, Celery, or memcached needed.

### Existing Packages Used
- SQLAlchemy ✅ (already have)
- SQLite ✅ (built into Python)
- Python stdlib: pickle, functools ✅

---

## Summary

| Feature | Old (Redis) | New (SQLite) | Benefit |
|---------|------------|-------------|---------|
| Job Queue | Redis + Celery | SQLite + APScheduler | No external service |
| Caching | Redis | SQLite + LRU | No external service |
| Sessions | Redis | SQLAlchemy | Already integrated |
| Concurrency | Single queue | SQLite WAL | Better isolation |
| Persistence | Volatile | Durable | Survives restarts |
| Setup | complex | simple | Just run app |

✅ **All features work with SQLite** - no Redis needed!
