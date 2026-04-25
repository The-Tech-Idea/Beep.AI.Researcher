# Phase 4: Advanced Features & User Permissions - Implementation Plan

**Start Date**: February 7, 2026  
**Status**: ⏳ PENDING IMPLEMENTATION  
**Overall Goal**: Add user permissions, batch operations, monitoring, and search to plugin system

---

## Phase 4 Overview

Phase 4 extends the plugin system with advanced user-facing features:

1. **User Permission Integration** - Plugin access control per user/role
2. **Batch Operations Service** - Bulk validation, export, processing
3. **Advanced Search** - Search extraction results with plugin-powered enrichment
4. **Real-time Monitoring** - Dashboard APIs for plugin metrics
5. **Notification System** - Alerts for validation failures, plugin errors
6. **Export Capabilities** - Export to CSV, JSON, Word, PDF

---

## Phase 4.1: User Permission & RBAC Integration

**Purpose**: Control which users can access and execute specific plugins

**Estimated Effort**: 400+ lines, 3-4 days

### Architecture

```
User
  ↓
Role (Admin, Reviewer, Extractor, Validator)
  ↓
Permission (execute_plugin_X, configure_plugin_X, view_logs_X)
  ↓
Plugin (medical, legal, engineering)
```

### Database Models

**PluginPermission**:
- id, plugin_id, role_id
- can_execute (bool), can_configure (bool), can_view_logs (bool)
- created_at, updated_at

**PluginRoleAssignment**:
- id, user_id, plugin_id
- access_level (read|write|admin)
- expiry_date (optional)
- created_at

**PluginAudit**:
- id, plugin_id, user_id, action (execute|configure|disable)
- timestamp, ip_address, success (bool)

### Middleware/Decorators

```python
@plugin_access_required('medical', 'execute')
@plugin_access_required('legal', 'configure')
```

### API Changes

All existing plugin routes updated to:
1. Check user permissions
2. Log access in PluginAudit
3. Return 403 Forbidden if lacking permissions
4. Include user_id in execution context

### Scenarios Supported

- Reviewer can only view medical plugin validation results
- Extractor can execute medical plugin but not legal
- Admin can configure all plugins
- Audit trail tracks who did what

---

## Phase 4.2: Batch Operations Service

**Purpose**: Process multiple extractions/validations/exports at scale

**Estimated Effort**: 500+ lines, 4-5 days

### Components

**BatchJob Model**:
- id, job_type (validate|export|process), status, creator_id
- input_config (JSON), output_config (JSON)
- progress (%), created_at, started_at, completed_at
- result_file_path, error_message

**BatchJobResult**:
- id, batch_id, item_id (result_id or schema_id)
- status (success|failed|skipped)
- result_data (JSON), error

### Endpoints

```
POST /projects/{id}/batch/validate
  {
    "schema_ids": [1, 2, 3],
    "result_ids": [10, 11, 12],
    "auto_correct": true,
    "async": true
  }
  → Returns batch_id

GET /projects/{id}/batch/{batch_id}/status
  {
    "progress": 45,
    "total": 100,
    "completed": 45,
    "failed": 2
  }

GET /projects/{id}/batch/{batch_id}/results
  [
    {
      "result_id": 10,
      "status": "success",
      "validations": [...],
      "corrections_applied": 5
    }
  ]

POST /projects/{id}/batch/export
  {
    "format": "csv|json|xlsx",
    "schema_ids": [1],
    "include_fields": ["diagnosis", "medication"],
    "filters": { "validation_status": "invalid" }
  }

GET /projects/{id}/batch/{batch_id}/download
  → Returns file
```

### Features

- ✅ Parallel processing (configurable workers)
- ✅ Progress tracking with WebSocket updates
- ✅ Auto-retry with exponential backoff
- ✅ CSV/JSON/Excel export
- ✅ Filtering and field selection
- ✅ Scheduled batch jobs
- ✅ Result compression (for large datasets)

---

## Phase 4.3: Real-time Monitoring Dashboard APIs

**Purpose**: APIs for real-time plugin and validation monitoring

**Estimated Effort**: 400+ lines, 3-4 days

### Endpoints

**Metrics Stream**:
```
GET /api/admin/monitor/metrics/stream
  (WebSocket: /ws/metrics)
  
Response (every 5 seconds):
{
  "timestamp": "2026-02-07T10:30:45Z",
  "plugins": {
    "medical": {
      "executions_per_minute": 12.5,
      "error_rate": 0.02,
      "avg_time_ms": 145.3,
      "p95_time_ms": 450.0,
      "active_users": 3
    }
  },
  "validations": {
    "pending": 120,
    "success_rate": 0.86,
    "avg_time_ms": 234.5
  }
}
```

**Active Jobs**:
```
GET /api/admin/monitor/jobs
  [
    {
      "job_id": "job-123",
      "type": "validate",
      "progress": 45,
      "started_at": "...",
      "estimated_completion": "..."
    }
  ]
```

**System Health Dashboard**:
```
GET /api/admin/monitor/health/detailed
  {
    "overall_status": "healthy",
    "components": {
      "plugin_system": { "status": "healthy", "response_time_ms": 50 },
      "database": { "status": "healthy", "connection_pool": "8/10" },
      "cache": { "status": "degraded", "hit_rate": 0.65 },
      "queue": { "status": "healthy", "pending_jobs": 12 }
    },
    "alerts": [
      {
        "severity": "warning",
        "message": "Medical plugin execution time trending up",
        "timestamp": "..."
      }
    ]
  }
```

**Real-time Alerts**:
```
WebSocket /ws/alerts
  {
    "type": "error",
    "plugin": "medical",
    "message": "Plugin execution timeout",
    "severity": "high"
  }
```

### Features

- ✅ WebSocket for real-time updates
- ✅ Per-plugin metrics streaming
- ✅ System health aggregation
- ✅ Alert generation
- ✅ Historical data snapshots
- ✅ Custom alert thresholds
- ✅ Performance trending

---

## Phase 4.4: Advanced Search Integration

**Purpose**: Search extraction results with plugin-powered enrichment

**Estimated Effort**: 300+ lines, 2-3 days

### Endpoints

**Full-text Search**:
```
GET /projects/{id}/search
  ?q=diabetes
  &schema_id=1
  &fields=diagnosis,medication
  &validation_status=invalid
  &page=1&limit=20

Response:
{
  "results": [
    {
      "result_id": 1,
      "schema_id": 1,
      "matches": [
        {
          "field": "diagnosis",
          "value": "E11 Type 2 Diabetes",
          "match_text": "Type 2 Diabetes",
          "confidence": 0.95
        }
      ],
      "validation_status": "valid",
      "plugin_suggestions": ["E11", "E10"]
    }
  ],
  "total": 145,
  "page": 1,
  "pages": 8
}
```

**Advanced Filters**:
```
POST /projects/{id}/search/advanced
{
  "filters": [
    {
      "field": "validation_status",
      "operator": "in",
      "values": ["invalid", "corrected"]
    },
    {
      "field": "created_at",
      "operator": "gte",
      "value": "2026-02-01"
    },
    {
      "field": "confidence_score",
      "operator": "lte",
      "value": 0.8
    }
  ],
  "sort": [
    { "field": "confidence_score", "direction": "asc" }
  ],
  "limit": 50
}
```

**Plugin-Enhanced Search**:
```
GET /projects/{id}/search/enriched
  ?q=heart condition
  &enrichment_plugin=medical
  &include_suggestions=true

Response:
{
  "results": [
    {
      "raw_match": "heart condition",
      "icd10_codes": ["I50.9", "I51.9"],
      "related_terms": ["cardiac", "cardiovascular"],
      "severity": "high"
    }
  ]
}
```

### Features

- ✅ Full-text search (SQLite FTS or Elasticsearch)
- ✅ Complex filtering and sorting
- ✅ Plugin-powered query enrichment
- ✅ Faceted search (validation status, plugin, date)
- ✅ Saved search queries
- ✅ Search result export
- ✅ Search analytics

---

## Phase 4.5: Notification System

**Purpose**: Alert users about validation failures and plugin events

**Estimated Effort**: 300+ lines, 2-3 days

### Database Models

**Notification**:
- id, user_id, type (validation_failed|plugin_error|job_complete)
- title, message, severity (info|warning|error)
- is_read, created_at, read_at

**NotificationPreference**:
- id, user_id, notification_type
- enabled (bool), delivery_method (in_app|email|slack|webhook)
- frequency (immediate|daily|weekly)

**WebhookEndpoint**:
- id, user_id, url, events ([])
- is_active, secret_key, created_at

### Endpoints

**Get Notifications**:
```
GET /notifications
  ?type=validation_failed
  &limit=20
  &unread_only=true

GET /notifications/{id}/mark-read
```

**Notification Preferences**:
```
PUT /users/{id}/notification-preferences
{
  "validation_failed": {
    "enabled": true,
    "delivery": ["in_app", "email"],
    "frequency": "immediate"
  }
}
```

**Webhook Management**:
```
POST /webhooks
{
  "url": "https://example.com/webhook",
  "events": ["validation.failed", "plugin.error", "batch.completed"],
  "secret": "webhook-secret"
}
```

### Events

- `validation.created` - New validation started
- `validation.completed` - Validation finished
- `validation.failed` - Validation failed
- `plugin.enabled/disabled` - Plugin status changed
- `plugin.error` - Plugin execution error
- `batch.completed` - Batch job completed
- `batch.failed` - Batch job failed
- `correction.suggested` - Auto-correction available

### Features

- ✅ In-app notifications
- ✅ Email notifications
- ✅ Slack integration
- ✅ Custom webhooks
- ✅ Notification preferences per user
- ✅ Notification history
- ✅ Smart grouping (don't spam)

---

## Phase 4.6: Export Capabilities

**Purpose**: Export extraction data in multiple formats

**Estimated Effort**: 250+ lines, 2 days

### Formats Supported

1. **CSV** - Flat export, one row per result
2. **JSON** - Structured export with metadata
3. **Excel (XLSX)** - Multi-sheet with formatting
4. **Word (DOCX)** - Formatted report with tables
5. **PDF** - Printable report

### Endpoints

**Single Export**:
```
GET /projects/{id}/extractions/{result_id}/export?format=pdf

Response: PDF file
```

**Batch Export**:
```
POST /projects/{id}/batch/export
{
  "format": "xlsx",
  "result_ids": [1, 2, 3],
  "include": ["raw_values", "validations", "suggestions"],
  "schema_id": 1
}

Returns: File download URL
```

**Template-based Export**:
```
POST /projects/{id}/export/template
{
  "template_id": "medical_report",
  "result_ids": [1, 2, 3],
  "include_charts": true,
  "include_summary": true
}
```

### Features

- ✅ Multi-format export
- ✅ Custom field selection
- ✅ Formatting options (colors, fonts)
- ✅ Watermarks and headers
- ✅ Charts and summaries
- ✅ Filtered exports
- ✅ Scheduled exports

---

## Phase 4 Timeline & Effort

| Component | Files | Lines | Tests | Days |
|-----------|-------|-------|-------|------|
| 4.1: Permissions | 4 | 400+ | 30+ | 3-4 |
| 4.2: Batch Ops | 5 | 500+ | 35+ | 4-5 |
| 4.3: Monitoring | 4 | 400+ | 25+ | 3-4 |
| 4.4: Search | 3 | 300+ | 20+ | 2-3 |
| 4.5: Notifications | 4 | 300+ | 25+ | 2-3 |
| 4.6: Export | 3 | 250+ | 20+ | 2 |
| **TOTAL** | **~23** | **~2,150+** | **~155+** | **16-22 days** |

---

## Implementation Strategy

### Week 1 (4.1 + 4.2)
- Monday-Tuesday: User permissions & RBAC
- Wednesday-Friday: Batch operations service

### Week 2 (4.3 + 4.4)
- Monday-Wednesday: Real-time monitoring APIs
- Thursday-Friday: Advanced search

### Week 3 (4.5 + 4.6 + Testing)
- Monday-Wednesday: Notifications system
- Thursday: Export capabilities
- Friday: Testing & documentation

---

## Dependencies & Blockers

✅ **All Phase 3 features must be complete** - Required for plugins
✅ **Database schema finalized** - No major changes expected
⏳ **User/Role models** - Assume existing from Phases 1-2
⏳ **Queue system** - May need Redis/Celery for batch jobs

---

## Next Steps

1. **Phase 4.1 Start**: User Permission & RBAC Integration
   - Create permission models
   - Implement decorators
   - Add audit logging
   - 30+ tests

2. **Database Preparation**: Add new tables
   - PluginPermission
   - PluginRoleAssignment
   - PluginAudit
   - BatchJob + BatchJobResult
   - Notification tables

3. **API Integration Points**:
   - All plugin routes check permissions
   - All batch operations tracked
   - All user actions audited

---

## Success Criteria

- ✅ All 4.1-4.6 components implemented
- ✅ 155+ tests created and passing
- ✅ Comprehensive documentation
- ✅ No breaking changes to Phase 3
- ✅ Performance maintained (<500ms per request)
- ✅ Security best practices followed

---

**Status**: Ready for Phase 4.1 implementation  
**Next Action**: Begin user permissions & RBAC integration
