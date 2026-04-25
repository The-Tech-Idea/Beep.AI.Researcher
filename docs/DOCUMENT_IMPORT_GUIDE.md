# Phase 2.4: Document Ingestion from Search Guide

**Status**: Complete | **Version**: 1.0  
**Date**: February 7, 2026  
**Related Guides**: [Extended Search API Guide](EXTENDED_SEARCH_GUIDE.md), [Caching & Indexing Guide](CACHING_INDEXING_GUIDE.md)

## Overview

Phase 2.4 adds automatic document import functionality to Beep.AI.Researcher, enabling users to:
- **Import search results** directly into project documents
- **Auto-download PDFs** from search results  
- **Track import history** with audit logging
- **Monitor import progress** via background jobs
- **Organize source metadata** for traceability

This guide covers setup, usage, API endpoints, and troubleshooting for document imports.

## Features

### 1. Direct Import from Search Results

Import individual search results from extended search endpoints:

```bash
POST /projects/1/web-search/12345/import

# Response: 202 Accepted
{
  "document_id": 456,
  "title": "Machine Learning in Healthcare",
  "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345",
  "job_id": "pdf_download_job_789",
  "status": "importing",
  "message": "Document created. PDF download queued."
}
```

### 2. Batch Import Multiple Results

Import multiple search results in one operation:

```bash
POST /projects/1/web-search/batch-import

{
  "result_ids": ["pubmed:12345", "arxiv:2301.05000", "pubmed:67890"]
}

# Response: 202 Accepted
{
  "job_id": "batch_import_job_123",
  "results_count": 3,
  "status": "queued",
  "message": "Batch import queued. Check job status with job_id."
}
```

### 3. Automatic PDF Downloading

PDFs are automatically downloaded from search results:
- **Timeout**: 30 seconds per PDF
- **Retry**: Up to 3 attempts on failure
- **Storage**: `data/projects/{id}/documents/`
- **Formats**: Support for PDF, HTML snapshots

### 4. Source Metadata Tracking

Every imported document retains source information:
```python
{
  "source_type": "pubmed",        # web_search | pubmed | arxiv | etc
  "source_id": "12345",           # Provider-specific ID
  "source_url": "https://...",    # Original article URL
  "imported_at": "2024-01-15"     # Import timestamp
}
```

### 5. Import Audit Trail

Complete audit log of all import operations:
- Document count per source
- Success/failure tracking
- Error messages and reasons
- Import duration metrics

## Setup

### Prerequisites

1. **Extended Search API** enabled (Phase 2.3)
   - Multi-source searching functional
   - SearchResult objects available

2. **JobQueue** configured (Phase 1.3)
   - Background job processing enabled
   - PDF download handler registered

3. **EventBus** active (Phase 1.1)
   - Event publishing enabled
   - Event handlers registered

4. **Project Storage** configured
   - Document storage path accessible
   - Write permissions for `data/projects/` directory

### Configuration

No special configuration required. Document import works out-of-the-box if dependencies are met.

#### Optional: PDF Download Timeout

```python
# In app/jobs/pdf_download_handler.py
PDF_DOWNLOAD_TIMEOUT = 30  # seconds (default)
PDF_DOWNLOAD_RETRIES = 3   # attempts (default)
```

#### Optional: Storage Location

```python
# In configuration
DOCUMENT_STORAGE_PATH = 'data/projects/{project_id}/documents/'
```

## Usage Guide

### Single Document Import

#### Step 1: Search for Results

```bash
GET /projects/1/search?query=machine%20learning&page=1&per_page=5

# Returns SearchResult objects with IDs
```

#### Step 2: Import Selected Result

```bash
POST /projects/1/web-search/pubmed:12345/import

# Headers
Content-Type: application/json
Authorization: Bearer <token>

# Response (202 Accepted)
{
  "document_id": 456,
  "title": "Machine Learning in Healthcare",
  "source_type": "pubmed",
  "source_id": "pubmed:12345",
  "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345",
  "pdf_download_job_id": "job_xyz_789",
  "status": "importing",
  "message": "Document created. PDF download queued.",
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### Step 3: Monitor PDF Download

```bash
GET /projects/1/jobs/job_xyz_789

# Check job status periodically
{
  "job_id": "job_xyz_789",
  "type": "pdf_download",
  "status": "completed",
  "result": {
    "document_id": 456,
    "file_path": "data/projects/1/documents/pubmed_12345.pdf",
    "file_size": 2048576,
    "mime_type": "application/pdf",
    "duration_seconds": 3.45
  }
}
```

### Batch Import Workflow

#### Step 1: Prepare Result IDs

Gather IDs from search results:
```python
search_results = [...]  # From search API
result_ids = [r['id'] for r in search_results[:10]]
```

#### Step 2: Submit Batch Import

```bash
POST /projects/1/web-search/batch-import

{
  "result_ids": [
    "pubmed:12345",
    "pubmed:67890",
    "arxiv:2301.05000"
  ]
}

# Response (202 Accepted)
{
  "job_id": "batch_import_job_123",
  "results_count": 3,
  "status": "queued",
  "message": "Batch import queued. Monitor with GET /projects/1/jobs/batch_import_job_123"
}
```

#### Step 3: Monitor Batch Progress

```bash
GET /projects/1/jobs/batch_import_job_123

{
  "job_id": "batch_import_job_123",
  "type": "batch_document_import",
  "status": "in_progress",
  "progress": {
    "total": 3,
    "completed": 2,
    "failed": 0,
    "in_progress": 1
  },
  "details": {
    "imported_documents": [456, 457],
    "queued_pdfs": [1],
    "failed_imports": []
  }
}
```

## API Reference

### POST /projects/{id}/web-search/{result_id}/import

Import a single search result as a project document.

**Parameters**:
- `id` (path, required): Project ID
- `result_id` (path, required): Search result ID (e.g., pubmed:12345)

**Request Body**: (empty)

**Response** (202 Accepted):
```json
{
  "document_id": integer,
  "title": string,
  "source_type": string,
  "source_id": string,
  "source_url": string,
  "pdf_download_job_id": string,
  "status": "importing",
  "message": string,
  "created_at": ISO datetime
}
```

**Status Codes**:
- `202`: Import queued successfully
- `400`: Invalid result_id or project_id
- `401`: Not authenticated
- `403`: Not authorized
- `404`: Project or result not found
- `500`: Server error

### POST /projects/{id}/web-search/batch-import

Import multiple search results as a batch job.

**Parameters**:
- `id` (path, required): Project ID

**Request Body**:
```json
{
  "result_ids": [string, ...],
  "auto_extract": boolean  (optional, default: false)
}
```

**Response** (202 Accepted):
```json
{
  "job_id": string,
  "results_count": integer,
  "status": "queued",
  "message": string,
  "estimate_duration_seconds": integer,
  "created_at": ISO datetime
}
```

**Status Codes**:
- `202`: Batch import queued
- `400`: Invalid request (result_ids missing or invalid)
- `401`: Not authenticated
- `403`: Not authorized
- `404`: Project not found
- `413`: Too many results (limit: 100)
- `500`: Server error

**Notes**:
- Maximum 100 results per batch
- Results are queued immediately
- PDFs download in parallel (up to 10 concurrent)

### GET /projects/{id}/documents/imports

List all imports for a project with pagination.

**Parameters**:
- `id` (path, required): Project ID
- `page` (query, optional, default: 1): Page number
- `per_page` (query, optional, default: 20, max: 100): Results per page
- `status` (query, optional): Filter by status (importing, completed, failed)
- `source` (query, optional): Filter by source type (pubmed, arxiv, etc)

**Response**:
```json
{
  "data": [
    {
      "document_id": integer,
      "title": string,
      "source_type": string,
      "source_id": string,
      "source_url": string,
      "pdf_status": "downloading" | "completed" | "failed",
      "pdf_path": string,
      "pdf_size": integer,
      "imported_at": ISO datetime,
      "error": string (if failed)
    }
  ],
  "pagination": {
    "page": integer,
    "per_page": integer,
    "total": integer,
    "pages": integer
  }
}
```

## Events

Document import triggers three EventBus events:

### 1. import.started

Fired when import begins.

```json
{
  "event_type": "import.started",
  "data": {
    "project_id": 1,
    "job_id": "job_xyz",
    "result_id": "pubmed:12345",
    "title": "Machine Learning in Healthcare",
    "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345"
  }
}
```

**Handlers**: Extract hooks trigger immediately

### 2. import.completed

Fired when PDF downloaded and document fully imported.

```json
{
  "event_type": "import.completed",
  "data": {
    "project_id": 1,
    "job_id": "job_xyz",
    "document_id": 456,
    "source_result_id": "pubmed:12345",
    "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345",
    "file_path": "data/projects/1/documents/pubmed_12345.pdf",
    "file_size": 2048576,
    "mime_type": "application/pdf",
    "duration_seconds": 3.45
  }
}
```

**Handlers**: 
- Update search cache (invalidate)
- Trigger extraction hooks
- Send user notification

### 3. import.failed

Fired when import fails (404 PDF, timeout, etc).

```json
{
  "event_type": "import.failed",
  "data": {
    "project_id": 1,
    "job_id": "job_xyz",
    "document_id": 456,
    "source_url": "https://pubmed.ncbi.nlm.nih.gov/12345",
    "error": "PDF download failed: 404 Not Found",
    "error_code": "pdf_404",
    "attempt": 3,
    "max_attempts": 3
  }
}
```

**Handlers**:
- Log error
- Notify user
- Update document status

## Code Examples

### Python: Import Search Result

```python
import requests

project_id = 1
result_id = "pubmed:12345"
token = "your_auth_token"

# Import the result
response = requests.post(
    f"http://localhost:5000/projects/{project_id}/web-search/{result_id}/import",
    headers={"Authorization": f"Bearer {token}"}
)

if response.status_code == 202:
    job = response.json()
    print(f"Import queued: {job['pdf_download_job_id']}")
    
    # Poll for completion
    while True:
        job_response = requests.get(
            f"http://localhost:5000/projects/{project_id}/jobs/{job['pdf_download_job_id']}",
            headers={"Authorization": f"Bearer {token}"}
        )
        job_status = job_response.json()
        
        if job_status['status'] in ['completed', 'failed']:
            print(f"Import {job_status['status']}")
            break
            
        time.sleep(2)
```

### Python: Batch Import

```python
import requests

project_id = 1
token = "your_auth_token"

# Results to import
result_ids = [
    "pubmed:12345",
    "pubmed:67890",
    "arxiv:2301.05000"
]

# Submit batch
response = requests.post(
    f"http://localhost:5000/projects/{project_id}/web-search/batch-import",
    json={"result_ids": result_ids},
    headers={"Authorization": f"Bearer {token}"}
)

if response.status_code == 202:
    batch = response.json()
    print(f"Batch {batch['job_id']} queued: {batch['results_count']} results")
```

### JavaScript/Node.js: Monitor Import

```javascript
async function monitorImport(projectId, jobId, token) {
  const baseUrl = 'http://localhost:5000';
  
  while (true) {
    const response = await fetch(
      `${baseUrl}/projects/${projectId}/jobs/${jobId}`,
      { headers: { 'Authorization': `Bearer ${token}` } }
    );
    
    const job = await response.json();
    
    if (job.status === 'completed') {
      console.log('Import complete!');
      console.log(`Document: ${job.result.document_id}`);
      console.log(`File: ${job.result.file_path}`);
      break;
    } else if (job.status === 'failed') {
      console.error(`Import failed: ${job.error}`);
      break;
    }
    
    console.log(`Status: ${job.status}...`);
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
}
```

## Error Handling

### Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `404 PDF Not Found` | URL invalid or access denied | Check PDF URL, verify access permissions |
| `PDF Download Timeout` | Network slow or PDF large | Increase timeout in configuration |
| `Storage Full` | Disk space exhausted | Free up space in `data/` directory |
| `Invalid Result ID` | Result not found in cache | Verify result ID from search response |
| `Project Not Found` | Project doesn't exist | Check project ID in database |

### Retry Logic

PDF downloads automatically retry up to 3 times:
- **1st attempt**: Immediate
- **2nd attempt**: After 5 seconds
- **3rd attempt**: After 10 seconds

If all 3 fail, `import.failed` event is triggered.

### Failed Imports

Failed imports still create documents but without PDF:
```json
{
  "id": 456,
  "title": "Machine Learning in Healthcare",
  "file_path": null,
  "file_size": 0,
  "mime_type": null,
  "status": "pending_pdf",
  "import_error": "PDF download failed after 3 attempts"
}
```

Users can manually upload PDF later.

## Performance Considerations

### Throughput

- **Single import**: 30-300ms (database insert) + 1-10s (PDF download)
- **Batch import**: Parallel processing, ~1-5s per PDF
- **Concurrent limits**: Up to 10 parallel PDF downloads per project

### Storage

- **Per document**: 500 bytes - 50+ MB (varies by PDF size)
- **Metadata**: ~500 bytes per document
- **Audit log**: ~200 bytes per import

### Network

- **PDF download**: HTTP with timeout and retry
- **Streaming**: PDFs chunked (8KB chunks) to manage memory

## Troubleshooting

### PDF Not Downloading

**Symptoms**: Import queued but PDF never arrives

**Diagnosis**:
```bash
# Check job status
GET /projects/1/jobs/job_xyz_789

# Check document storage
ls -la data/projects/1/documents/
```

**Solutions**:
1. Verify PDF URL is publicly accessible
2. Check network connectivity
3. Increase PDF_DOWNLOAD_TIMEOUT
4. Check server logs for detailed error

### Batch Import Failing

**Symptoms**: Some results imported, others fail

**Diagnosis**:
```bash
GET /projects/1/jobs/batch_job_123

# Check failed_imports in response
```

**Solutions**:
1. Check individual result URLs
2. Verify access permissions
3. Retry failed imports individually
4. Check for API rate limits

### Storage Issues

**Symptoms**: Import fails with "Storage Full" error

**Diagnosis**:
```bash
df -h data/
du -sh data/projects/1/documents/
```

**Solutions**:
1. Clean up old documents
2. Expand storage capacity
3. Archive old imports

## Advanced Usage

### Custom Header Configuration

For sources requiring authentication headers:

```python
from app.models.researcher import LibrarySource

source = LibrarySource.query.first()
source.headers_json = json.dumps({
    'Authorization': 'Bearer api_key_123',
    'User-Agent': 'BeepAI/2.4'
})
db.session.commit()
```

### Extraction Hook Integration

Automatically extract on import:

```bash
POST /projects/1/web-search/pubmed:12345/import

{
  "auto_extract": true,
  "extraction_schema_id": 5
}
```

### Import with Metadata

Add custom metadata during import:

```bash
POST /projects/1/web-search/pubmed:12345/import

{
  "metadata": {
    "relevance_score": 0.95,
    "tags": ["machine-learning", "healthcare"],
    "notes": "Important for literature review"
  }
}
```

## Integration with Phase 2.5 Caching

Imports automatically invalidate search caches:

```
1. SearchResult found in cache
2. User imports result
3. import.completed event fired
4. Cache invalidation triggered
5. Next search doesn't use stale cache
```

This ensures imports are immediately reflected in search results.

## Monitoring and Analytics

### Import Statistics

```bash
GET /projects/1/import-stats

{
  "total_imported": 234,
  "by_source": {
    "pubmed": 120,
    "arxiv": 80,
    "web_search": 34
  },
  "by_status": {
    "completed": 200,
    "pending_pdf": 20,
    "failed": 14
  },
  "average_pdf_size_mb": 2.3,
  "total_storage_mb": 460,
  "success_rate": 0.94
}
```

## Related Documentation

- [Extended Search API Guide](EXTENDED_SEARCH_GUIDE.md) - How to search before importing
- [Caching & Indexing Guide](CACHING_INDEXING_GUIDE.md) - How imports affect caching
- [JobQueue Guide](JOB_QUEUE_GUIDE.md) - Background job processing
- [EventBus Guide](EVENT_BUS_GUIDE.md) - Event-driven architecture
- [Phase 2.4 Completion Report](PHASE_24_COMPLETE.md) - Complete technical details

## FAQ

**Q: Can I import without downloading PDF?**  
A: Yes, setting `pdf_required=false` in import request skips PDF download but still creates document.

**Q: What happens if PDF URL is broken?**  
A: Import retries 3 times, then marks as failed. Document still exists for manual PDF upload.

**Q: How do I cancel an import?**  
A: POST /projects/{id}/jobs/{job_id}/cancel (if still queued)

**Q: Can I import from custom sources?**  
A: Yes, via LibrarySource configuration (Phase 2.2)

**Q: Does import trigger extraction?**  
A: Only if `auto_extract=true` and extraction hooks are configured

**Q: What's the import rate limit?**  
A: No hard limit; limited by available worker threads (default: 4 concurrent)

---

**Last Updated**: February 7, 2026  
**Version**: 1.0  
**Status**: COMPLETE
