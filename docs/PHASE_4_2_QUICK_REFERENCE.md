# Phase 4.2 Quick Reference Guide

**Date**: February 7, 2026  
**Status**: ✅ Complete  
**Version**: 1.0

---

## Quick Start

### Create and Execute a Batch Job

```python
import requests

# 1. Create batch job
response = requests.post(
    'http://localhost:5000/api/batch/jobs',
    json={
        "name": "Batch Analysis",
        "plugins": [1, 2],
        "description": "Process records"
    },
    headers={"Authorization": f"Bearer {token}"}
)
job_id = response.json()['job']['id']

# 2. Start execution
requests.post(
    f'http://localhost:5000/api/batch/jobs/{job_id}/start',
    json={"total_records": 100},
    headers={"Authorization": f"Bearer {token}"}
)

# 3. Execute with data
requests.post(
    f'http://localhost:5000/api/batch/jobs/{job_id}/execute',
    json={
        "records": [
            {"field": "value"},
            {"field": "value2"}
        ],
        "max_workers": 5
    },
    headers={"Authorization": f"Bearer {token}"}
)

# 4. Get results
results = requests.get(
    f'http://localhost:5000/api/batch/jobs/{job_id}/results',
    headers={"Authorization": f"Bearer {token}"}
).json()

# 5. Export
requests.post(
    f'http://localhost:5000/api/batch/jobs/{job_id}/export',
    json={"format": "csv"},
    headers={"Authorization": f"Bearer {token}"}
)
```

---

## API Endpoints Summary

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/batch/jobs` | Create batch job |
| GET | `/api/batch/jobs` | List jobs |
| GET | `/api/batch/jobs/{id}` | Get status |
| POST | `/api/batch/jobs/{id}/start` | Start execution |
| POST | `/api/batch/jobs/{id}/pause` | Pause job |
| POST | `/api/batch/jobs/{id}/cancel` | Cancel job |
| POST | `/api/batch/jobs/{id}/execute` | Execute batch |
| GET | `/api/batch/jobs/{id}/results` | Get results |
| GET | `/api/batch/jobs/{id}/logs` | Get logs |
| POST | `/api/batch/jobs/{id}/export` | Export results |
| GET | `/api/batch/jobs/{id}/download/{fmt}` | Download export |

---

## Job Status Lifecycle

```
PENDING
  ↓
  ├─→ START → RUNNING 
  │   ├─→ PAUSE → PAUSED → RESUME → RUNNING
  │   ├─→ CANCEL → CANCELLED
  │   └─→ COMPLETE → COMPLETED
  └─→ CANCEL → CANCELLED
```

**Valid Transitions**:
- PENDING → RUNNING (start)
- RUNNING → PAUSED (pause)
- PAUSED → RUNNING (resume)
- RUNNING/PAUSED → CANCELLED (cancel)
- RUNNING → COMPLETED (finished)
- RUNNING → FAILED (error)

---

## Models Reference

### BatchJob
```python
{
    "id": 1,
    "user_id": 1,
    "name": "Job Name",
    "description": "Optional description",
    "status": "running",  # pending, running, paused, completed, failed, cancelled
    "progress": 45.5,
    "total_records": 1000,
    "processed_records": 455,
    "successful_records": 450,
    "failed_records": 5,
    "plugins_config": {...},
    "export_format": "csv",
    "created_at": "2026-02-07T10:00:00Z",
    "started_at": "2026-02-07T10:01:00Z",
    "estimated_time_remaining_seconds": 300
}
```

### BatchJobResult
```python
{
    "id": 1,
    "batch_job_id": 1,
    "record_index": 0,
    "plugin_id": 1,
    "plugin_name": "Plugin Name",
    "success": True,
    "result_data": {"key": "value"},
    "error_message": null,
    "execution_time_ms": 150,
    "created_at": "2026-02-07T10:05:30Z"
}
```

### BatchJobLog
```python
{
    "id": 1,
    "batch_job_id": 1,
    "level": "info",  # info, warning, error, debug
    "message": "Log message",
    "record_index": 0,
    "plugin_id": 1,
    "plugin_name": "Plugin Name",
    "created_at": "2026-02-07T10:05:30Z"
}
```

---

## Service Methods Quick Reference

### Create Job
```python
success, msg, job = BatchOperationService.create_batch_job(
    user_id=1,
    name="Job",
    plugins_list=[1, 2, 3]
)
```

### Execute Parallel
```python
success, msg, results = BatchOperationService.execute_batch_parallel(
    job_id=1,
    records=[...],
    max_workers=5
)
```

### Get Status
```python
status = BatchOperationService.get_batch_status(job_id=1)
```

### Export
```python
success, msg, csv = BatchOperationService.export_to_csv(job_id=1)
success, msg, json = BatchOperationService.export_to_json(job_id=1)
```

### Get Results
```python
success, msg, results = BatchOperationService.get_batch_results(
    job_id=1,
    limit=100,
    offset=0,
    filter_success=True  # True: successful only, False: failed only, None: all
)
```

### Get Logs
```python
success, msg, logs = BatchOperationService.get_batch_logs(
    job_id=1,
    level='error',  # Optional: info, warning, error, debug
    limit=100
)
```

---

## Query Parameters

### List Jobs
```
GET /api/batch/jobs?status=running&limit=50&offset=0

Parameters:
- status: pending, running, completed, failed
- limit: 1-500 (default: 100)
- offset: 0+ (default: 0)
```

### Get Results
```
GET /api/batch/jobs/{id}/results?success_only=true&limit=50&offset=0

Parameters:
- success_only: true (success), false (failed), omit (all)
- limit: 1-500 (default: 100)
- offset: 0+ (default: 0)
```

### Get Logs
```
GET /api/batch/jobs/{id}/logs?level=error&limit=100&offset=0

Parameters:
- level: info, warning, error, debug (optional)
- limit: 1-500 (default: 100)
- offset: 0+ (default: 0)
```

---

## Permission Requirements

| Operation | Required Level |
|-----------|----------------|
| Create batch job | READ |
| Start/Execute | EXECUTE |
| Pause/Cancel | CONFIGURE |
| View results | READ |
| Export | READ |
| View logs | READ |

All operations require user authentication via Authorization header.

---

## Error Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad request (validation error) |
| 403 | Forbidden (permission denied) |
| 404 | Not found |
| 500 | Server error |
| 504 | Timeout |

---

## Common Query Examples

### Get running batch jobs
```
GET /api/batch/jobs?status=running&limit=100
```

### Get latest job status
```
GET /api/batch/jobs/42
```

### Export to CSV
```
POST /api/batch/jobs/42/export
Body: {"format": "csv"}
```

### Check only errors
```
GET /api/batch/jobs/42/logs?level=error&limit=50
```

### Get failed results
```
GET /api/batch/jobs/42/results?success_only=false&limit=100
```

---

## Performance Tips

1. **Optimal Workers**: 5 for normal, up to 10 for I/O-bound
2. **Batch Size**: Keep under 10,000 records
3. **Large Datasets**: Split into multiple jobs
4. **Caching**: Cache expensive computations in plugins
5. **Monitoring**: Check logs regularly for failures

---

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| Job timeout | Reduce batch size or increase timeout |
| High failures | Check logs for error details |
| Slow performance | Increase max_workers or optimize plugins |
| Permission denied | Check user's plugin access level (Phase 4.1) |
| Job not found | Verify job_id and user ownership |

---

## Integration Points

### With Phase 4.1 (Permissions)
- Batch execution checks user permission for each plugin
- Skips plugins user lacks EXECUTE access to
- Automatically enforces 5-level access hierarchy

### With Phase 3 (Plugins)
- Uses PluginManager to execute plugins
- Respects plugin configuration
- Stores plugin outputs in results

---

## Monitoring Checklist

- [ ] Check job status: `GET /api/batch/jobs/{id}`
- [ ] Monitor progress percentage
- [ ] Review error logs: `GET /api/batch/jobs/{id}/logs?level=error`
- [ ] Check failed records: `GET /api/batch/jobs/{id}/results?success_only=false`
- [ ] Verify expected result count
- [ ] Export results: `POST /api/batch/jobs/{id}/export`
- [ ] Archive or cleanup old jobs: `POST /api/batch/cleanup`

---

## Code Examples

### Python (Flask Client)
```python
from requests import Session

client = Session()
client.headers.update({"Authorization": f"Bearer {token}"})

# Create job
resp = client.post('http://localhost:5000/api/batch/jobs', json={
    "name": "Analysis",
    "plugins": [1, 2]
})
job_id = resp.json()['job']['id']

# Execute
resp = client.post(f'http://localhost:5000/api/batch/jobs/{job_id}/execute', json={
    "records": [...],
    "max_workers": 5
})

# Check results
results = client.get(f'http://localhost:5000/api/batch/jobs/{job_id}/results').json()
```

### JavaScript (Fetch)
```javascript
const headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
};

// Create job
const jobResp = await fetch('http://localhost:5000/api/batch/jobs', {
    method: 'POST',
    headers,
    body: JSON.stringify({
        name: "Analysis",
        plugins: [1, 2]
    })
});
const { job } = await jobResp.json();

// Execute
const execResp = await fetch(
    `http://localhost:5000/api/batch/jobs/${job.id}/execute`,
    {
        method: 'POST',
        headers,
        body: JSON.stringify({
            records: [...],
            max_workers: 5
        })
    }
);
```

### cURL
```bash
# Create batch job
curl -X POST http://localhost:5000/api/batch/jobs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Batch Analysis",
    "plugins": [1, 2],
    "description": "Test batch"
  }'

# Get job status
curl -X GET http://localhost:5000/api/batch/jobs/1 \
  -H "Authorization: Bearer $TOKEN"

# Execute batch
curl -X POST http://localhost:5000/api/batch/jobs/1/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "records": [...],
    "max_workers": 5
  }'
```

---

## File Locations

| Component | File |
|-----------|------|
| Models | `app/models/researcher/batch_operations.py` |
| Service | `app/services/batch_operations.py` |
| Routes | `app/routes/admin/batch_operations.py` |
| Tests | `tests/test_batch_operations.py` |
| Docs | `docs/PHASE_4_2_BATCH_OPERATIONS.md` |

---

## Next Steps

1. Register routes in main Flask app
2. Run test suite to verify functionality
3. Deploy to production
4. Monitor batch jobs in production
5. Plan Phase 5 (Scheduling)

