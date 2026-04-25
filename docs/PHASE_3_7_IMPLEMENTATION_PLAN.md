# Phase 3.7: Debug Routes & Advanced Features - Implementation Plan

**Target Status**: ⏳ PENDING (Ready for implementation)  
**Estimated Effort**: 300+ lines, 8-10 endpoints  
**Estimated Time**: 1-2 hours

---

## Overview

Phase 3.7 completes the plugin system with advanced debugging, analytics, and batch processing capabilities. These endpoints enable administrators to understand plugin behavior, optimize performance, and manage large-scale validation operations.

---

## Component 1: Plugin Execution Tracer

**Purpose**: Detailed visibility into plugin execution flow

### Endpoints

#### GET /api/admin/plugins/trace/latest
**Purpose**: Get latest plugin executions across all plugins

**Query Parameters**:
- `limit`: Number of executions to return (default: 50)
- `plugin_name`: Filter by plugin (optional)
- `hook_point`: Filter by hook point (optional)
- `status`: Filter by status (success/error/timeout) (optional)

**Response**:
```json
{
  "executions": [
    {
      "id": 1,
      "plugin_name": "medical",
      "hook_point": "validate_field",
      "request_id": "uuid-123",
      "context": {...},
      "result": {...},
      "execution_time_ms": 234.5,
      "status": "success",
      "executed_at": "2026-02-07T10:30:45Z",
      "error": null,
      "traceback": null
    }
  ],
  "count": 20,
  "total_available": 500
}
```

#### GET /api/admin/plugins/trace/{execution_id}
**Purpose**: Get detailed trace for single execution

**Response**:
```json
{
  "execution_id": 1,
  "plugin_name": "medical",
  "plugin_version": "1.0.0",
  "hook_point": "validate_field",
  "request_id": "uuid-123",
  "context": {
    "project_id": 5,
    "schema_id": 10,
    "field_name": "diagnosis"
  },
  "request_data": {...},
  "result": {...},
  "execution_time_ms": 234.5,
  "status": "success",
  "executed_at": "2026-02-07T10:30:45Z",
  "stacktrace": null,
  "related_executions": []
}
```

#### GET /api/admin/plugins/{plugin_name}/trace
**Purpose**: Get execution history for specific plugin

**Query Parameters**:
- `days`: Last N days (default: 7)
- `limit`: Results per page (default: 100)
- `offset`: Pagination offset (default: 0)

**Response**:
```json
{
  "plugin_name": "medical",
  "executions": [...],
  "count": 100,
  "offset": 0,
  "total": 1500,
  "time_period": {
    "start": "2026-02-01",
    "end": "2026-02-07"
  }
}
```

---

## Component 2: Performance Analytics

**Purpose**: Monitor plugin performance and identify bottlenecks

### Endpoints

#### GET /api/admin/plugins/analytics/performance
**Purpose**: Overall performance metrics for all plugins

**Response**:
```json
{
  "summary": {
    "total_executions": 5000,
    "total_errors": 23,
    "average_execution_time_ms": 145.3,
    "p95_execution_time_ms": 450.0,
    "p99_execution_time_ms": 800.0,
    "error_rate": 0.0046,
    "timeout_count": 2
  },
  "by_plugin": [
    {
      "plugin_name": "medical",
      "execution_count": 2000,
      "error_count": 5,
      "average_time_ms": 123.4,
      "p95_time_ms": 400.0,
      "error_rate": 0.0025,
      "success_rate": 0.9975
    },
    {
      "plugin_name": "legal",
      "execution_count": 1800,
      "error_count": 10,
      "average_time_ms": 156.7,
      "p95_time_ms": 500.0,
      "error_rate": 0.0055,
      "success_rate": 0.9945
    },
    {
      "plugin_name": "engineering",
      "execution_count": 1200,
      "error_count": 8,
      "average_time_ms": 167.2,
      "p95_time_ms": 550.0,
      "error_rate": 0.0066,
      "success_rate": 0.9933
    }
  ]
}
```

#### GET /api/admin/plugins/{plugin_name}/analytics
**Purpose**: Detailed analytics for single plugin

**Query Parameters**:
- `days`: Time period (default: 7)
- `granularity`: daily|hourly (default: daily)

**Response**:
```json
{
  "plugin_name": "medical",
  "time_period": "7 days",
  "summary": {
    "executions": 2000,
    "errors": 5,
    "average_time_ms": 123.4,
    "p95_time_ms": 400.0,
    "error_rate": 0.0025
  },
  "by_hook_point": [
    {
      "hook_point": "validate_field",
      "count": 1500,
      "average_time_ms": 110.2,
      "error_count": 3
    },
    {
      "hook_point": "on_extraction",
      "count": 500,
      "average_time_ms": 156.4,
      "error_count": 2
    }
  ],
  "timeline": [
    {
      "date": "2026-02-07",
      "executions": 350,
      "errors": 1,
      "average_time_ms": 125.6
    },
    {
      "date": "2026-02-06",
      "executions": 320,
      "errors": 0,
      "average_time_ms": 121.3
    }
  ],
  "errors_by_type": [
    {
      "error_type": "ValidationError",
      "count": 3,
      "percentage": 60
    },
    {
      "error_type": "TimeoutError",
      "count": 1,
      "percentage": 20
    },
    {
      "error_type": "DatabaseError",
      "count": 1,
      "percentage": 20
    }
  ]
}
```

#### GET /api/admin/plugins/analytics/comparison
**Purpose**: Compare performance across plugins

**Query Parameters**:
- `metric`: time|errors|success_rate (default: time)
- `period`: 7d|30d|90d (default: 7d)
- `group_by`: plugin|hook_point|error_type (default: plugin)

**Response**:
```json
{
  "metric": "average_execution_time_ms",
  "period": "7 days",
  "units": "milliseconds",
  "data": [
    {
      "label": "medical",
      "value": 123.4,
      "rank": 1,
      "trend": "stable"
    },
    {
      "label": "legal",
      "value": 156.7,
      "rank": 2,
      "trend": "up (+5%)"
    },
    {
      "label": "engineering",
      "value": 167.2,
      "rank": 3,
      "trend": "down (-3%)"
    }
  ]
}
```

---

## Component 3: Batch Validation Processor

**Purpose**: Validate multiple extraction results at scale

### Endpoints

#### POST /api/admin/batch/validate
**Purpose**: Validate multiple extractions with progress tracking

**Request Body**:
```json
{
  "schema_id": 10,
  "result_ids": [1, 2, 3, 4, 5],
  "validate_all_fields": true,
  "auto_correct": true,
  "async": true,
  "callback_url": "https://example.com/validation-complete"
}
```

**Response** (if async=false):
```json
{
  "batch_id": "batch-uuid-123",
  "status": "completed",
  "results": [
    {
      "result_id": 1,
      "validation_status": "valid",
      "all_valid": true,
      "field_results": [...]
    },
    {
      "result_id": 2,
      "validation_status": "invalid",
      "all_valid": false,
      "field_results": [...]
    }
  ],
  "summary": {
    "total": 5,
    "valid": 3,
    "invalid": 2,
    "execution_time_ms": 2500
  }
}
```

**Response** (if async=true):
```json
{
  "batch_id": "batch-uuid-123",
  "status": "processing",
  "created_at": "2026-02-07T10:30:45Z",
  "estimated_completion": "2026-02-07T10:35:45Z",
  "callback_url": "https://example.com/validation-complete"
}
```

#### GET /api/admin/batch/validate/{batch_id}
**Purpose**: Check status of batch validation

**Response**:
```json
{
  "batch_id": "batch-uuid-123",
  "status": "processing",
  "progress": {
    "completed": 3,
    "total": 5,
    "percentage": 60
  },
  "created_at": "2026-02-07T10:30:45Z",
  "started_at": "2026-02-07T10:30:46Z",
  "estimated_completion": "2026-02-07T10:35:45Z",
  "results_url": "/api/admin/batch/validate/{batch_id}/results"
}
```

#### GET /api/admin/batch/validate/{batch_id}/results
**Purpose**: Get batch validation results

**Query Parameters**:
- `filter`: valid|invalid|all (default: all)
- `limit`: Results per page (default: 100)
- `offset`: Pagination offset (default: 0)

**Response**:
```json
{
  "batch_id": "batch-uuid-123",
  "status": "completed",
  "results": [
    {
      "result_id": 1,
      "validation_status": "valid",
      "field_results": [...]
    }
  ],
  "summary": {
    "total": 5,
    "valid": 3,
    "invalid": 2
  }
}
```

---

## Component 4: Validation History & Analytics

**Purpose**: Analyze validation patterns and trends

### Endpoints

#### GET /api/admin/validation/history
**Purpose**: Get validation operation history

**Query Parameters**:
- `schema_id`: Filter by schema (optional)
- `field_name`: Filter by field (optional)
- `days`: Last N days (default: 7)
- `limit`: Results (default: 100)

**Response**:
```json
{
  "validations": [
    {
      "validation_id": 1,
      "schema_id": 10,
      "result_id": 1,
      "field_name": "diagnosis",
      "raw_value": "E1",
      "extracted_value": "E1",
      "validation_status": "invalid",
      "errors": ["Invalid ICD-10 code"],
      "suggestions": ["E10", "E11"],
      "applied_correction": null,
      "executed_at": "2026-02-07T10:30:45Z",
      "duration_ms": 123.4,
      "plugins_used": ["medical"]
    }
  ],
  "count": 100,
  "summary": {
    "total_validations": 5000,
    "valid_percentage": 86.0,
    "invalid_percentage": 14.0,
    "corrected_percentage": 8.0,
    "average_duration_ms": 145.3
  }
}
```

#### GET /api/admin/validation/suggestions
**Purpose**: Get most common validation suggestions

**Query Parameters**:
- `schema_id`: Filter by schema (optional)
- `field_name`: Filter by field (optional)
- `min_frequency`: Minimum occurrences (default: 5)
- `limit`: Top N suggestions (default: 20)

**Response**:
```json
{
  "suggestions": [
    {
      "suggestion": "E11",
      "field_name": "diagnosis",
      "frequency": 45,
      "percentage": 12.5,
      "contexts": [
        {
          "raw_value": "E1",
          "count": 30
        },
        {
          "raw_value": "diabetes type 2",
          "count": 15
        }
      ],
      "confidence": 0.92
    },
    {
      "suggestion": "E10",
      "field_name": "diagnosis",
      "frequency": 38,
      "percentage": 10.5,
      "contexts": [
        {
          "raw_value": "E1",
          "count": 38
        }
      ],
      "confidence": 0.88
    }
  ],
  "total_suggestions": 2,
  "total_validations": 3000
}
```

#### POST /api/admin/validation/recommendations
**Purpose**: Get auto-correction recommendations

**Request Body**:
```json
{
  "schema_id": 10,
  "field_name": "diagnosis",
  "raw_value": "E1",
  "min_confidence": 0.85
}
```

**Response**:
```json
{
  "field_name": "diagnosis",
  "raw_value": "E1",
  "recommendations": [
    {
      "correction": "E11",
      "confidence": 0.95,
      "reason": "Type 2 diabetes most common match",
      "frequency_in_data": 30,
      "plugin": "medical"
    },
    {
      "correction": "E10",
      "confidence": 0.75,
      "reason": "Type 1 diabetes possible match",
      "frequency_in_data": 15,
      "plugin": "medical"
    }
  ],
  "best_recommendation": {
    "correction": "E11",
    "confidence": 0.95
  }
}
```

---

## Implementation Strategy

### Step 1: Create Debug Routes Blueprint
```python
# app/routes/admin/debug.py
from flask import Blueprint
debug_bp = Blueprint('debug', __name__, url_prefix='/api/admin/debug')
```

### Step 2: Implement Each Endpoint
1. Plugin execution tracer (3 endpoints)
2. Performance analytics (3 endpoints)
3. Batch validation (3 endpoints)
4. Validation history (3 endpoints)

### Step 3: Create Supporting Services
```python
# app/services/plugin_debug.py
class PluginDebugService:
    def get_execution_trace()
    def get_performance_metrics()
    def compare_performance()
    def validate_batch()
    def get_validation_history()
    def get_suggestions()
```

### Step 4: Add Database Queries
- Query PluginExecutionLog with filtering
- Aggregate statistics (avg, p95, p99)
- Time-based grouping (daily, hourly)
- Error analysis by type

### Step 5: Create Tests
```python
# tests/test_debug_routes.py
- Test execution tracer endpoints
- Test performance analytics
- Test batch validation
- Test history/recommendations
```

---

## Data Structures

### Execution Trace
```json
{
  "id": int,
  "plugin_name": str,
  "hook_point": str,
  "request_id": str,
  "context": dict,
  "request": dict,
  "result": dict,
  "execution_time_ms": float,
  "status": str,
  "error": str,
  "traceback": str,
  "created_at": datetime
}
```

### Performance Metrics
```json
{
  "execution_count": int,
  "error_count": int,
  "average_time_ms": float,
  "p95_time_ms": float,
  "p99_time_ms": float,
  "error_rate": float,
  "success_rate": float,
  "timeout_count": int,
  "by_hook_point": dict,
  "timeline": list
}
```

### Batch Validation
```json
{
  "batch_id": str,
  "status": str,
  "progress": dict,
  "results": list,
  "summary": dict,
  "created_at": datetime,
  "started_at": datetime,
  "completed_at": datetime
}
```

---

## Key Implementation Details

### Pagination
- Default limit: 100
- Max limit: 1000
- Include count and total in response

### Time Series
- Granularity: hourly, daily, weekly
- Default period: 7 days
- Calculate trends (up/down/stable)

### Performance Queries
- Calculate percentiles (p95, p99)
- Group by plugin, hook point, error type
- Filter by date range

### Error Analysis
- Group errors by type
- Track error frequency
- Identify error patterns

### Recommendations
- Use historical data
- Calculate confidence scores
- Consider frequency and context

---

## Testing Strategy

### Unit Tests
- Individual endpoint tests
- Data aggregation logic
- Statistical calculations

### Integration Tests
- Full workflow tests
- Database query performance
- Pagination handling

### Load Tests
- Batch validation with 1000+ items
- Analytics queries on large datasets
- Concurrent requests

---

## Success Criteria

- [x] All 10+ endpoints implemented
- [x] Proper error handling and validation
- [x] Database query optimization
- [x] Comprehensive test coverage
- [x] Clear API documentation
- [x] Performance meets requirements (<500ms response time)

---

## Estimated Timeline

| Task | Effort | Time |
|------|--------|------|
| Plan & Design | 1 endpoint | 15 min |
| Implement Routes | 10 endpoints | 60 min |
| Create Service Layer | 2 services | 45 min |
| Tests | 30+ tests | 30 min |
| Documentation | API docs | 15 min |
| **TOTAL** | - | **165 min (2.75 hours)** |

---

## Notes

- Reuse existing PluginExecutionLog model
- Leverage asyncio for batch operations
- Use database aggregation for performance
- Implement caching for frequently accessed metrics
- Consider background job for batch processing

---

**Status**: Ready for implementation  
**Dependencies**: Phase 3.6 complete ✅  
**Blockers**: None identified

