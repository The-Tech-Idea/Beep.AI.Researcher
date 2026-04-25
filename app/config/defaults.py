"""
Configuration Defaults - All default configuration values for Beep.AI.Researcher

Provides centralized defaults for:
- Feature flags (auto_extract, web_search_enabled, plugins_enabled)
- Hook configuration (enabled hooks, execution order)
- Queue configuration (max workers, retry settings)
- Cache and general settings
"""

import os
from typing import Dict, Any

# ============================================================================
# FEATURE FLAGS - Feature enablement
# ============================================================================

DEFAULT_FEATURES = {
    # Phase 1 - AI Discovery & Personalized Reading Feed
    "ai_discovery_enabled": {
        "enabled": os.getenv("ENABLE_AI_DISCOVERY", "false").lower() == "true",
        "description": "Enable research-interest inference, personalized feed, and alerts",
        "level": "optional"
    },

    # Document Processing
    "auto_extract": {
        "enabled": os.getenv("ENABLE_AUTO_EXTRACT", "true").lower() == "true",
        "description": "Automatically extract data from uploaded documents",
        "level": "core"  # core, optional, experimental
    },
    
    # Web Search
    "web_search_enabled": {
        "enabled": os.getenv("ENABLE_WEB_SEARCH", "false").lower() == "true",
        "description": "Enable web/academic search integration",
        "level": "optional"
    },
    
    # Plugin System
    "plugins_enabled": {
        "enabled": os.getenv("ENABLE_PLUGINS", "false").lower() == "true",
        "description": "Enable plugin system for extensibility",
        "level": "optional"
    },
    
    # Chat Integration
    "chat_enabled": {
        "enabled": os.getenv("ENABLE_CHAT", "true").lower() == "true",
        "description": "Enable chat interface",
        "level": "core"
    },
    
    # Code Generation
    "code_generation_enabled": {
        "enabled": os.getenv("ENABLE_CODE_GENERATION", "true").lower() == "true",
        "description": "Enable code generation from documents",
        "level": "core"
    },
    
    # RAG Integration
    "rag_enabled": {
        "enabled": os.getenv("ENABLE_RAG", "true").lower() == "true",
        "description": "Enable RAG (Retrieval-Augmented Generation) support",
        "level": "core"
    },
    
    # Notifications
    "notifications_enabled": {
        "enabled": os.getenv("ENABLE_NOTIFICATIONS", "true").lower() == "true",
        "description": "Enable notification system",
        "level": "optional"
    },
    
    # Auditing
    "audit_logging_enabled": {
        "enabled": os.getenv("ENABLE_AUDIT_LOGGING", "true").lower() == "true",
        "description": "Enable audit logging for security tracking",
        "level": "core"
    },
}

# ============================================================================
# HOOK CONFIGURATION - Which hooks are enabled and their execution order
# ============================================================================

DEFAULT_HOOKS = {
    # Auto-extraction hook for document processing
    "auto_extraction_hook": {
        "enabled": True,
        "priority": 100,  # Higher = runs first
        "description": "Automatically extract data from documents",
        "trigger_events": [
            "document.uploaded",
            "document.updated"
        ],
        "max_execution_time_seconds": 300,
        "timeout_behavior": "log_and_continue"  # or "fail_job"
    },
    
    # Validation hook for data quality
    "validation_hook": {
        "enabled": True,
        "priority": 90,
        "description": "Validate extracted data quality",
        "trigger_events": [
            "extraction.completed"
        ],
        "max_execution_time_seconds": 60,
        "timeout_behavior": "log_and_continue"
    },
    
    # Notification hook for user alerts
    "notification_hook": {
        "enabled": True,
        "priority": 50,
        "description": "Send notifications on important events",
        "trigger_events": [
            "document.uploaded",
            "extraction.completed",
            "task.status_changed"
        ],
        "max_execution_time_seconds": 30,
        "timeout_behavior": "log_and_continue"
    },
    
    # Audit logging hook for compliance
    "audit_logging_hook": {
        "enabled": True,
        "priority": 10,  # Runs last
        "description": "Log all operations for audit trail",
        "trigger_events": [
            "document.uploaded",
            "document.deleted",
            "extraction.completed",
            "code.created",
            "code.deleted",
            "task.status_changed"
        ],
        "max_execution_time_seconds": 10,
        "timeout_behavior": "log_and_continue"
    },
}

# ============================================================================
# QUEUE CONFIGURATION - Job queue settings
# ============================================================================

DEFAULT_QUEUE = {
    # Worker settings
    "max_workers": int(os.getenv("JOB_QUEUE_MAX_WORKERS", "4")),
    "min_workers": 1,
    "description": "Number of background worker threads",
    
    # Retry settings
    "max_retries": int(os.getenv("MAX_RETRIES", "3")),
    "initial_retry_delay_seconds": 5,  # First retry after 5 seconds
    "max_retry_delay_seconds": 300,    # Max 5 minutes between retries
    "exponential_backoff_base": 2,     # 2^retry_count
    
    # Job execution settings
    "job_timeout_seconds": int(os.getenv("JOB_TIMEOUT_SECONDS", "3600")),  # 1 hour default
    "poll_interval_seconds": int(os.getenv("QUEUE_POLL_INTERVAL", "5")),   # Check for new jobs every 5 seconds
    "batch_size": int(os.getenv("QUEUE_BATCH_SIZE", "10")),               # Process up to 10 jobs per poll
    
    # Database settings
    "db_path": os.getenv("JOB_QUEUE_DB_PATH", "job_queue.db"),
    "use_wal_mode": True,              # Use WAL (Write-Ahead Logging) for better concurrency
    "connection_timeout_seconds": 30,
    
    # Job history
    "job_history_retention_days": int(os.getenv("JOB_HISTORY_RETENTION_DAYS", "30")),
    "max_job_logs": int(os.getenv("MAX_JOB_LOGS", "100")),  # Max log entries per job
    
    # Monitoring
    "track_statistics": True,
    "enable_metrics": True,
}

# ============================================================================
# CACHE CONFIGURATION
# ============================================================================

DEFAULT_CACHE = {
    # TTL settings
    "cache_ttl_seconds": int(os.getenv("CACHE_TTL_SECONDS", "86400")),  # 24 hours default
    "default_ttl_seconds": 3600,                                        # 1 hour
    "search_results_ttl_seconds": 86400,                                  # 24 hours
    "api_response_ttl_seconds": 300,                                      # 5 minutes
    
    # Size limits
    "max_cache_entries": int(os.getenv("CACHE_MAX_ENTRIES", "10000")),
    "max_cache_size_mb": int(os.getenv("CACHE_MAX_SIZE_MB", "500")),
    
    # Implementation
    "backend": os.getenv("CACHE_BACKEND", "memory"),  # "memory" or "redis"
    "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
}

# ============================================================================
# TENANT CONFIGURATION
# ============================================================================

DEFAULT_TENANT = {
    # Per-tenant overrides
    "enable_feature_overrides": True,
    "enable_queue_overrides": True,
    "enable_hook_overrides": True,
    
    # Default tenant settings
    "max_projects_per_tenant": int(os.getenv("MAX_PROJECTS_PER_TENANT", "100")),
    "max_documents_per_project": int(os.getenv("MAX_DOCUMENTS_PER_PROJECT", "1000")),
    "max_api_calls_per_hour": int(os.getenv("MAX_API_CALLS_PER_HOUR", "10000")),
}

# ============================================================================
# GENERAL SETTINGS
# ============================================================================

DEFAULT_GENERAL = {
    # Environment
    "environment": os.getenv("ENVIRONMENT", "development"),  # development, staging, production
    "debug_mode": os.getenv("DEBUG", "false").lower() == "true",
    "log_level": os.getenv("LOG_LEVEL", "INFO"),
    
    # API Settings
    "api_base_url": os.getenv("API_BASE_URL", "http://localhost:5000"),
    "api_version": "v1",

    # App URLs and host settings
    "app_url": os.getenv("APP_URL", "http://127.0.0.1:5005"),
    "server_host": os.getenv("HOST", "127.0.0.1"),
    "server_port": int(os.getenv("PORT", "5005")),

    # UI/API list limits
    "dashboard_project_limit": int(os.getenv("DASHBOARD_PROJECT_LIMIT", "20")),
    "search_result_limit": int(os.getenv("SEARCH_RESULT_LIMIT", "50")),
    "project_list_limit": int(os.getenv("PROJECT_LIST_LIMIT", "50")),
    "related_docs_limit": int(os.getenv("RELATED_DOCS_LIMIT", "10")),

    # External service integration settings
    "beep_ai_server_url": os.getenv("BEEP_AI_SERVER_URL", ""),
    "beep_ai_server_token": os.getenv("BEEP_AI_SERVER_TOKEN", ""),

    # SMTP settings
    "smtp_host": os.getenv("SMTP_HOST", ""),
    "smtp_port": int(os.getenv("SMTP_PORT", "587")),
    "smtp_user": os.getenv("SMTP_USER", ""),
    "smtp_password": os.getenv("SMTP_PASSWORD", ""),
    "smtp_use_tls": os.getenv("SMTP_USE_TLS", "true").lower() == "true",
    "mail_from": os.getenv("MAIL_FROM", ""),
    
    # Security
    "enable_cors": True,
    "cors_origins": os.getenv("CORS_ORIGINS", "*").split(","),
    
    # Timeouts
    "request_timeout_seconds": 30,
    "database_timeout_seconds": 10,
}

# ============================================================================
# VALIDATION SCHEMAS - For configuration validation
# ============================================================================

FEATURE_FLAG_SCHEMA = {
    "enabled": bool,
    "description": str,
    "level": str,  # "core", "optional", "experimental"
}

HOOK_CONFIG_SCHEMA = {
    "enabled": bool,
    "priority": int,
    "description": str,
    "trigger_events": list,
    "max_execution_time_seconds": int,
    "timeout_behavior": str,
}

QUEUE_CONFIG_SCHEMA = {
    "max_workers": int,
    "max_retries": int,
    "job_timeout_seconds": int,
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_default_config() -> Dict[str, Any]:
    """Get complete default configuration dictionary."""
    return {
        "features": DEFAULT_FEATURES,
        "hooks": DEFAULT_HOOKS,
        "queue": DEFAULT_QUEUE,
        "cache": DEFAULT_CACHE,
        "tenant": DEFAULT_TENANT,
        "general": DEFAULT_GENERAL,
    }


def validate_feature_config(feature_config: Dict[str, Any]) -> bool:
    """Validate feature flag configuration."""
    if not isinstance(feature_config, dict):
        return False
    
    required_keys = {"enabled", "description", "level"}
    for key, value in feature_config.items():
        if not isinstance(value, dict):
            return False
        if not required_keys.issubset(value.keys()):
            return False
        if not isinstance(value["enabled"], bool):
            return False
        if value["level"] not in ("core", "optional", "experimental"):
            return False
    
    return True


def validate_hook_config(hook_config: Dict[str, Any]) -> bool:
    """Validate hook configuration."""
    if not isinstance(hook_config, dict):
        return False
    
    for key, value in hook_config.items():
        if not isinstance(value, dict):
            return False
        required_keys = {"enabled", "priority", "trigger_events", "max_execution_time_seconds"}
        if not required_keys.issubset(value.keys()):
            return False
        if not isinstance(value["enabled"], bool):
            return False
        if not isinstance(value["priority"], int):
            return False
        if not isinstance(value["trigger_events"], list):
            return False
    
    return True


def validate_queue_config(queue_config: Dict[str, Any]) -> bool:
    """Validate queue configuration."""
    required_keys = {"max_workers", "max_retries", "job_timeout_seconds"}
    
    if not required_keys.issubset(queue_config.keys()):
        return False
    
    if not isinstance(queue_config["max_workers"], int) or queue_config["max_workers"] < 1:
        return False
    
    if not isinstance(queue_config["max_retries"], int) or queue_config["max_retries"] < 0:
        return False
    
    if not isinstance(queue_config["job_timeout_seconds"], int) or queue_config["job_timeout_seconds"] < 1:
        return False
    
    return True
