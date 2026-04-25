# Phase 1.5: Configuration Management Guide

**Status**: ✅ Complete

**Overview**: Centralized configuration management system for Beep.AI.Researcher with feature flags, hook configuration, job queue settings, and tenant-level overrides.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Feature Flags](#feature-flags)
4. [Hook Configuration](#hook-configuration)
5. [Queue Configuration](#queue-configuration)
6. [Tenant Configuration](#tenant-configuration)
7. [Usage Examples](#usage-examples)
8. [Environment Variables](#environment-variables)
9. [Best Practices](#best-practices)
10. [API Reference](#api-reference)

---

## Overview

Phase 1.5 provides a centralized, flexible configuration system for managing:

- **Feature Flags**: Enable/disable features (auto_extract, web_search, plugins, etc.)
- **Hook Configuration**: Control which hooks are enabled and their execution order
- **Queue Configuration**: Control job queue behavior (workers, retries, timeouts)
- **Cache Settings**: Control caching behavior and TTLs
- **Tenant Overrides**: Per-tenant configuration customization

### Key Benefits

✅ **Centralized**: All configuration in one place  
✅ **Flexible**: Support for global and tenant-level overrides  
✅ **Environment Variables**: Configure via environment without code changes  
✅ **Hot Reload**: Change configuration at runtime  
✅ **Validation**: Automatic configuration validation  
✅ **Zero Dependencies**: Works standalone with SQLite backend  

---

## Architecture

### Configuration Hierarchy

```
1. Defaults (app/config/defaults.py)
   ↓
2. Environment Variables (loaded into defaults)
   ↓  
3. Tenant Overrides (set via ConfigManager API)
   ↓
4. Runtime Changes (set via ConfigManager API)
```

### Core Components

**`defaults.py`**: Contains all default configuration values
- `DEFAULT_FEATURES`: Feature flag definitions
- `DEFAULT_HOOKS`: Hook configuration
- `DEFAULT_QUEUE`: Job queue settings
- `DEFAULT_CACHE`: Cache configuration
- `DEFAULT_TENANT`: Tenant settings
- `DEFAULT_GENERAL`: General application settings

**`manager.py`**: ConfigManager singleton
- Manages configuration state
- Validates configuration
- Provides access to settings
- Handles tenant overrides
- Enables/disables features and hooks

**`__init__.py`**: Public API
- Exports ConfigManager
- Exports convenience functions
- Exports default values

---

## Feature Flags

Feature flags allow you to enable/disable features without code changes.

### Predefined Features

| Feature | Default | Environment Variable | Description |
|---------|---------|----------------------|-------------|
| auto_extract | true | ENABLE_AUTO_EXTRACT | Auto-extract from uploaded documents |
| web_search_enabled | false | ENABLE_WEB_SEARCH | Web/academic search integration |
| plugins_enabled | false | ENABLE_PLUGINS | Plugin system |
| chat_enabled | true | ENABLE_CHAT | Chat interface |
| code_generation_enabled | true | ENABLE_CODE_GENERATION | Code generation |
| rag_enabled | true | ENABLE_RAG | RAG support |
| notifications_enabled | true | ENABLE_NOTIFICATIONS | Notification system |
| audit_logging_enabled | true | ENABLE_AUDIT_LOGGING | Audit logging |

### Checking Features

```python
from app.config import get_config, is_feature_enabled

# Method 1: Using ConfigManager instance
config = get_config()
if config.is_feature_enabled("auto_extract"):
    # Feature is enabled
    perform_auto_extraction()

# Method 2: Using convenience function
if is_feature_enabled("web_search_enabled"):
    # Feature is enabled
    enable_web_search()

# Method 3: Check with tenant override
if config.is_feature_enabled("auto_extract", tenant_id="tenant123"):
    # Check tenant-specific setting
```

### Enabling/Disabling Features

```python
config = get_config()

# Enable a feature
config.set_feature_enabled("web_search_enabled", True)

# Disable a feature
config.set_feature_enabled("chat_enabled", False)

# Get feature configuration
feature_config = config.get_feature_config("auto_extract")
print(f"Enabled: {feature_config['enabled']}")
print(f"Level: {feature_config['level']}")  # core, optional, experimental

# Get all features
all_features = config.get_all_features()
for feature_name, feature_config in all_features.items():
    print(f"{feature_name}: {feature_config['enabled']}")
```

---

## Hook Configuration

Hooks allow you to extend functionality at key points. Configuration controls which hooks run and their execution order.

### Predefined Hooks

| Hook | Priority | Default | Trigger Events |
|------|----------|---------|-----------------|
| auto_extraction_hook | 100 | enabled | document.uploaded, document.updated |
| validation_hook | 90 | enabled | extraction.completed |
| notification_hook | 50 | enabled | document.uploaded, extraction.completed, task.status_changed |
| audit_logging_hook | 10 | enabled | All important events |

### Checking Hook Configuration

```python
config = get_config()

# Check if hook is enabled
if config.is_hook_enabled("auto_extraction_hook"):
    # Hook is enabled and will execute

# Get hook configuration
hook_config = config.get_hook_config("auto_extraction_hook")
print(f"Enabled: {hook_config['enabled']}")
print(f"Priority: {hook_config['priority']}")
print(f"Events: {hook_config['trigger_events']}")

# Get all enabled hooks (sorted by priority)
enabled_hooks = config.get_enabled_hooks()
for hook_name, hook_config in enabled_hooks:
    print(f"{hook_name}: priority={hook_config['priority']}")

# Get hooks for specific event
hooks_for_event = config.get_hooks_for_event("document.uploaded")
for hook_name in hooks_for_event:
    print(f"Hook for document.uploaded: {hook_name}")
```

### Enabling/Disabling Hooks

```python
config = get_config()

# Disable a hook
config.set_hook_enabled("validation_hook", False)

# Enable a hook
config.set_hook_enabled("validation_hook", True)
```

### Hook Configuration Details

Each hook has these settings:

```python
{
    "enabled": True,                    # Hook is active
    "priority": 100,                    # Higher = runs first (0-100)
    "description": "Auto-extract data",
    "trigger_events": [
        "document.uploaded",
        "document.updated"
    ],
    "max_execution_time_seconds": 300,  # Kill hook if exceeds this
    "timeout_behavior": "log_and_continue"  # What to do on timeout
}
```

---

## Queue Configuration

The job queue needs configuration for workers, retries, and timeouts.

### Queue Settings

| Setting | Default | Environment Variable | Description |
|---------|---------|----------------------|-------------|
| max_workers | 4 | JOB_QUEUE_MAX_WORKERS | Number of background threads |
| max_retries | 3 | MAX_RETRIES | Max retry attempts |
| job_timeout_seconds | 3600 | JOB_TIMEOUT_SECONDS | Kill job if exceeds this |
| poll_interval_seconds | 5 | QUEUE_POLL_INTERVAL | How often to check for jobs |
| job_history_retention_days | 30 | JOB_HISTORY_RETENTION_DAYS | Keep job history for X days |

### Accessing Queue Configuration

```python
config = get_config()

# Get entire queue config
queue_config = config.get_queue_config()

# Get specific settings
max_workers = config.get_max_workers()        # Default: 4
max_retries = config.get_max_retries()        # Default: 3
job_timeout = config.get_job_timeout_seconds() # Default: 3600 (1 hour)

# Calculate retry delay with exponential backoff
retry_0_delay = config.get_retry_delay_seconds(0)  # Initial delay
retry_1_delay = config.get_retry_delay_seconds(1)  # Longer delay
retry_2_delay = config.get_retry_delay_seconds(2)  # Even longer
# Delay increases until max_retry_delay_seconds is reached
```

### Using in Job Queue

```python
from app.config import get_config
from app.core import get_job_queue, JobType

config = get_config()

# Create job queue with configured workers
queue = get_job_queue()

# Queue respects max_workers internally
job = queue.create_job(
    job_type=JobType.EXTRACT_DOCUMENT.value,
    input_data={"document_id": "doc123"},
    max_retries=config.get_max_retries(),  # Use configured max retries
)

# On failure, job queue uses configured retry delays
```

---

## Tenant Configuration

Tenants can have their own configuration overrides.

### Setting Tenant Configuration

```python
config = get_config()

# Disable auto_extract for specific tenant
config.set_tenant_config("tenant123", {
    "features": {
        "auto_extract": {
            "enabled": False,
            "description": "Disabled for this tenant",
            "level": "core"
        }
    }
})

# Override queue settings for tenant
config.set_tenant_config("tenant456", {
    "queue": {
        "max_workers": 8,      # More workers for this tenant
        "max_retries": 5,      # More retries
        "job_timeout_seconds": 7200  # 2 hour timeout
    }
})

# Multiple overrides
config.set_tenant_config("tenant789", {
    "features": {
        "web_search_enabled": {
            "enabled": True,
            "description": "Enabled for tenant789",
            "level": "optional"
        }
    },
    "hooks": {
        "validation_hook": {
            "enabled": False,
            "priority": 90,
            "description": "Disabled",
            "trigger_events": ["extraction.completed"],
            "max_execution_time_seconds": 60,
            "timeout_behavior": "log_and_continue"
        }
    },
    "queue": {
        "max_workers": 2,  # Fewer workers
        "max_retries": 1
    }
})
```

### Checking Tenant Configuration

```python
config = get_config()

# Check feature with tenant override
auto_extract_global = config.is_feature_enabled("auto_extract")
auto_extract_tenant = config.is_feature_enabled("auto_extract", "tenant123")

# Get tenant config
tenant_config = config.get_tenant_config("tenant123")
if tenant_config:
    print(f"Tenant has custom config")
else:
    print(f"Tenant uses global config")

# Get with tenant override
max_workers_global = config.get_max_workers()
max_workers_tenant = config.get_max_workers("tenant456")

# Check hooks with tenant override
enabled_hooks_global = config.get_enabled_hooks()
enabled_hooks_tenant = config.get_enabled_hooks("tenant789")
```

### Removing Tenant Configuration

```python
config = get_config()

# Remove overrides (tenant goes back to using global config)
config.remove_tenant_config("tenant123")
```

---

## Usage Examples

### Example 1: Conditional Auto-Extraction

```python
from flask import request
from app.config import is_feature_enabled, get_config

@app.route('/api/documents', methods=['POST'])
def upload_document():
    file = request.files['file']
    
    # Check if auto-extract is enabled for this tenant
    tenant_id = request.headers.get('X-Tenant-ID')
    config = get_config()
    
    if config.is_feature_enabled("auto_extract", tenant_id):
        # Queue extraction job
        from app.routes.integration import JobQueueManager
        job_id = JobQueueManager.queue_extraction(
            doc_id, schema_id, project_id
        )
        return {"success": True, "async_job_id": job_id}
    else:
        # Just save without auto-extraction
        return {"success": True}
```

### Example 2: Scaling Job Queue

```python
from app.config import get_config
from app.core import JobType

# Get configured number of workers
config = get_config()
max_workers = config.get_max_workers()

# Start job queue with configured workers
queue = get_job_queue()
print(f"Job queue started with {max_workers} workers")

# Queue respects max retries
max_retries = config.get_max_retries()
job = queue.create_job(
    job_type=JobType.EXTRACT_DOCUMENT.value,
    input_data={"document_id": "doc123"},
    max_retries=max_retries
)
```

### Example 3: Hook Execution Order

```python
from app.config import get_config

config = get_config()

# Get hooks for an event, in priority order
hooks = config.get_hooks_for_event("document.uploaded")

# Execute hooks
for hook_name in hooks:
    if config.is_hook_enabled(hook_name):
        hook = HookRegistry.get(hook_name)
        hook.execute(event_data)
        # Higher priority hooks run first
```

### Example 4: Multi-Tenant Configuration

```python
from app.config import get_config

# You have many tenants with different needs
tenants = {
    "enterprise_customer": {
        "features": {
            "auto_extract": {"enabled": True, "description": "...", "level": "core"},
            "web_search_enabled": {"enabled": True, "description": "...", "level": "optional"},
            "plugins_enabled": {"enabled": True, "description": "...", "level": "optional"}
        },
        "queue": {
            "max_workers": 16,
            "max_retries": 5
        }
    },
    "small_startup": {
        "features": {
            "auto_extract": {"enabled": True, "description": "...", "level": "core"},
            "web_search_enabled": {"enabled": False, "description": "...", "level": "optional"},
            "plugins_enabled": {"enabled": False, "description": "...", "level": "optional"}
        },
        "queue": {
            "max_workers": 2,
            "max_retries": 2
        }
    }
}

config = get_config()

# Set up configuration for each tenant
for tenant_id, tenant_config in tenants.items():
    config.set_tenant_config(tenant_id, tenant_config)

# Later, when processing requests
def process_request(tenant_id, request_data):
    if config.is_feature_enabled("web_search_enabled", tenant_id):
        # Run web search for this tenant
        pass
    
    max_workers = config.get_max_workers(tenant_id)
    # Scale job processing based on tenant
```

---

## Environment Variables

Configure settings without changing code:

```bash
# Feature Flags
export ENABLE_AUTO_EXTRACT=true
export ENABLE_WEB_SEARCH=false
export ENABLE_PLUGINS=false
export ENABLE_CHAT=true
export ENABLE_CODE_GENERATION=true
export ENABLE_RAG=true
export ENABLE_NOTIFICATIONS=true
export ENABLE_AUDIT_LOGGING=true

# Job Queue
export JOB_QUEUE_MAX_WORKERS=4
export MAX_RETRIES=3
export JOB_TIMEOUT_SECONDS=3600
export QUEUE_POLL_INTERVAL=5
export JOB_HISTORY_RETENTION_DAYS=30
export QUEUE_BATCH_SIZE=10

# Cache
export CACHE_TTL_SECONDS=86400
export CACHE_MAX_ENTRIES=10000
export CACHE_MAX_SIZE_MB=500

# Tenant
export MAX_PROJECTS_PER_TENANT=100
export MAX_DOCUMENTS_PER_PROJECT=1000
export MAX_API_CALLS_PER_HOUR=10000

# General
export ENVIRONMENT=production
export DEBUG=false
export LOG_LEVEL=INFO
```

---

## Best Practices

### 1. Use Feature Flags for New Features

```python
# Good: New feature behind flag
if config.is_feature_enabled("new_feature_xyz"):
    # New code path
else:
    # Fallback to old behavior

# Avoid: Hard-coded feature availability
if True:  # Always on
    # New feature
```

### 2. Check at Route Entry Point

```python
# Good: Check once at function start
@app.route('/api/search')
def search():
    if not config.is_feature_enabled("web_search_enabled"):
        return {"error": "Feature not enabled"}, 403
    # ... rest of handler

# Avoid: Checking in multiple places
def search():
    if config.is_feature_enabled("..."):
        if config.is_feature_enabled("..."):
            if config.is_feature_enabled("..."):
                # nested checks
```

### 3. Use Tenant Configuration for Multi-tenant Apps

```python
# Good: Check with tenant ID
tenant_id = request.headers.get('X-Tenant-ID')
if config.is_feature_enabled("premium_feature", tenant_id):
    # Premium feature for this tenant

# Avoid: Checking only global config
if config.is_feature_enabled("premium_feature"):
    # All tenants get same behavior
```

### 4. Configure via Environment in Production

```bash
# Good: Configure in environment
export JOB_QUEUE_MAX_WORKERS=8
export ENABLE_WEB_SEARCH=true

# Avoid: Hard-coding configuration
# DEFAULT_QUEUE = {"max_workers": 8, ...}
```

### 5. Reload Configuration for Updates

```python
config = get_config()

# Make configuration changes
# ... time passes ...

# Reload to pick up environment variable changes
if config.reload_config():
    print("Configuration reloaded")
else:
    print("Configuration reload failed")
```

### 6. Validate Configuration on Startup

```python
import logging

logger = logging.getLogger(__name__)
config = get_config()

# Validate configuration
if not config.validate_config():
    for error in config.get_validation_errors():
        logger.error(f"Config error: {error}")
    sys.exit(1)

logger.info("Configuration valid")
```

---

## API Reference

### ConfigManager Methods

#### Feature Management

```python
# Check if feature is enabled
is_enabled: bool = config.is_feature_enabled(feature_name: str, tenant_id: Optional[str])

# Set feature enabled/disabled
success: bool = config.set_feature_enabled(feature_name: str, enabled: bool)

# Get feature configuration
config: Dict = config.get_feature_config(feature_name: str, tenant_id: Optional[str])

# Get all features
features: Dict = config.get_all_features(tenant_id: Optional[str])
```

#### Hook Management

```python
# Get hook configuration
config: Dict = config.get_hook_config(hook_name: str, tenant_id: Optional[str])

# Check if hook is enabled
is_enabled: bool = config.is_hook_enabled(hook_name: str, tenant_id: Optional[str])

# Get all enabled hooks (sorted by priority)
hooks: List[Tuple] = config.get_enabled_hooks(tenant_id: Optional[str])

# Get hooks for specific event
hooks: List[str] = config.get_hooks_for_event(event_name: str, tenant_id: Optional[str])

# Set hook enabled/disabled
success: bool = config.set_hook_enabled(hook_name: str, enabled: bool)
```

#### Queue Management

```python
# Get queue configuration
config: Dict = config.get_queue_config(tenant_id: Optional[str])

# Get max workers
workers: int = config.get_max_workers(tenant_id: Optional[str])

# Get max retries
retries: int = config.get_max_retries(tenant_id: Optional[str])

# Get job timeout
timeout: int = config.get_job_timeout_seconds(tenant_id: Optional[str])

# Calculate retry delay
delay: int = config.get_retry_delay_seconds(retry_count: int, tenant_id: Optional[str])
```

#### Cache Management

```python
# Get cache configuration
config: Dict = config.get_cache_config(tenant_id: Optional[str])

# Get cache TTL
ttl: int = config.get_cache_ttl_seconds(tenant_id: Optional[str])
```

#### Tenant Management

```python
# Set tenant configuration
success: bool = config.set_tenant_config(tenant_id: str, config_overrides: Dict)

# Get tenant configuration
config: Optional[Dict] = config.get_tenant_config(tenant_id: str)

# Remove tenant configuration
success: bool = config.remove_tenant_config(tenant_id: str)
```

#### Configuration Management

```python
# Validate configuration
is_valid: bool = config.validate_config()

# Get validation errors
errors: List[str] = config.get_validation_errors()

# Reload configuration
success: bool = config.reload_config()

# Get last reload time
time: datetime = config.get_last_reload_time()

# Export configuration
config_dict: Dict = config.export_config(include_sensitive: bool = False)

# Get configuration summary
summary: Dict = config.get_config_summary()
```

### Convenience Functions

```python
from app.config import (
    get_config,                  # Get ConfigManager instance
    is_feature_enabled,          # Check feature enabled
    get_max_workers,             # Get max workers
    get_queue_ttl                # Get cache TTL
)
```

---

## Summary

Phase 1.5 Configuration Management provides:

✅ **Feature Flags**: Enable/disable features without code changes  
✅ **Hook Configuration**: Control hook execution order and behavior  
✅ **Queue Configuration**: Control job queue workers and retry behavior  
✅ **Tenant Overrides**: Per-tenant customization  
✅ **Environment Variables**: Configure via environment  
✅ **Validation**: Automatic configuration validation  
✅ **Hot Reload**: Change configuration at runtime  
✅ **Zero Dependencies**: Works with existing SQLite backend  

For more information, see [PHASE_15_COMPLETE.md](PHASE_15_COMPLETE.md).

