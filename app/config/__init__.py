"""
Configuration package - Centralized configuration management for Beep.AI.Researcher

Provides easy access to:
- Feature flags (auto_extract, web_search_enabled, plugins_enabled)
- Hook configuration (enabled hooks, execution order)
- Queue configuration (max workers, retry settings)
- Environment variable overrides
- Tenant-level configuration overrides

Usage:
    from app.config import get_config, is_feature_enabled
    
    config = get_config()
    if is_feature_enabled("auto_extract"):
        # Feature is enabled
    
    # Get queue configuration
    max_workers = config.get_max_workers()
    max_retries = config.get_max_retries()
    
    # Get hooks for an event
    hooks = config.get_hooks_for_event("document.uploaded")
    
    # Set tenant configuration
    config.set_tenant_config("tenant123", {
        "features": {"auto_extract": {"enabled": False}},
        "queue": {"max_workers": 8}
    })
"""

from app.config_manager import (
    ConfigManager,
    config_manager,
    get_config,
    is_feature_enabled,
    get_max_workers,
    get_queue_ttl,
)
from app.config.defaults import (
    get_default_config,
    DEFAULT_FEATURES,
    DEFAULT_HOOKS,
    DEFAULT_QUEUE,
    DEFAULT_CACHE,
    DEFAULT_TENANT,
    DEFAULT_GENERAL,
)

__all__ = [
    # Manager
    "ConfigManager",
    "get_config",
    
    # Convenience functions
    "is_feature_enabled",
    "get_max_workers",
    "get_queue_ttl",
    
    # Defaults
    "get_default_config",
    "DEFAULT_FEATURES",
    "DEFAULT_HOOKS",
    "DEFAULT_QUEUE",
    "DEFAULT_CACHE",
    "DEFAULT_TENANT",
    "DEFAULT_GENERAL",
]
