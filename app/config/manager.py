"""Compatibility shim — all config logic now lives in app.config_manager.

This file is kept so that legacy imports such as::

    from app.config.manager import get_config
    from app.config import get_config

continue to work without modification.
"""

# Re-export everything from the unified module so that existing call-sites
# importing from app.config.manager keep working unchanged.
from app.config_manager import (  # noqa: F401
    ConfigManager,
    config_manager,
    get_config,
    is_feature_enabled,
    get_max_workers,
    get_queue_ttl,
)
from app.config.defaults import (  # noqa: F401
    get_default_config,
    validate_feature_config,
    validate_hook_config,
    validate_queue_config,
    DEFAULT_FEATURES,
    DEFAULT_HOOKS,
    DEFAULT_QUEUE,
    DEFAULT_CACHE,
    DEFAULT_TENANT,
    DEFAULT_GENERAL,
)


class _REMOVED_ConfigManager:
    """
    Centralized configuration manager using singleton pattern.
    
    Features:
    - Load defaults from defaults.py
    - Override with environment variables
    - Override with database configuration (for tenants)
    - Validate all configuration
    - Provide hot reload capability
    - Thread-safe access
    """
    
    _instance = None
    _lock = Lock()
    
    def __init__(self):
        """Initialize configuration manager with defaults."""
        self._config = get_default_config()
        self._tenant_configs = {}  # tenant_id -> config overrides
        self._last_reload = datetime.now()
        self._validation_errors = []
        
        logger.info("ConfigManager initialized with defaults")
    
    @classmethod
    def get_instance(cls) -> "ConfigManager":
        """Get singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    # ========================================================================
    # FEATURE FLAG MANAGEMENT
    # ========================================================================
    
    def is_feature_enabled(self, feature_name: str, tenant_id: Optional[str] = None) -> bool:
        """
        Check if a feature is enabled.
        
        Args:
            feature_name: Name of feature (e.g., "auto_extract")
            tenant_id: Optional tenant ID for tenant-level override
        
        Returns:
            True if feature is enabled
        
        Example:
            if config.is_feature_enabled("auto_extract"):
                # Auto-extract is enabled
        """
        try:
            # Check tenant override first
            if tenant_id and tenant_id in self._tenant_configs:
                tenant_config = self._tenant_configs[tenant_id]
                if "features" in tenant_config and feature_name in tenant_config["features"]:
                    return tenant_config["features"][feature_name].get("enabled", False)
            
            # Check global config
            if feature_name in self._config["features"]:
                return self._config["features"][feature_name]["enabled"]
            
            logger.warning(f"Feature '{feature_name}' not found in configuration")
            return False
            
        except Exception as e:
            logger.error(f"Error checking feature '{feature_name}': {e}")
            return False
    
    def set_feature_enabled(self, feature_name: str, enabled: bool) -> bool:
        """
        Enable or disable a feature at runtime.
        
        Args:
            feature_name: Name of feature
            enabled: True to enable, False to disable
        
        Returns:
            True if successful
        """
        try:
            if feature_name not in self._config["features"]:
                logger.error(f"Feature '{feature_name}' not found")
                return False
            
            self._config["features"][feature_name]["enabled"] = enabled
            logger.info(f"Feature '{feature_name}' set to {enabled}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting feature '{feature_name}': {e}")
            return False
    
    def get_feature_config(self, feature_name: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get complete feature configuration.
        
        Returns:
            Feature config dict or None if not found
        """
        # Check tenant override first
        if tenant_id and tenant_id in self._tenant_configs:
            tenant_config = self._tenant_configs[tenant_id]
            if "features" in tenant_config and feature_name in tenant_config["features"]:
                return tenant_config["features"][feature_name]
        
        # Check global config
        if feature_name in self._config["features"]:
            return self._config["features"][feature_name]
        
        return None
    
    def get_all_features(self, tenant_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """Get all feature configurations."""
        features = self._config["features"].copy()
        
        # Apply tenant overrides
        if tenant_id and tenant_id in self._tenant_configs:
            tenant_config = self._tenant_configs[tenant_id]
            if "features" in tenant_config:
                features.update(tenant_config["features"])
        
        return features
    
    # ========================================================================
    # HOOK CONFIGURATION MANAGEMENT
    # ========================================================================
    
    def get_hook_config(self, hook_name: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get hook configuration.
        
        Args:
            hook_name: Name of hook (e.g., "auto_extraction_hook")
            tenant_id: Optional tenant ID for override
        
        Returns:
            Hook config dict or None
        """
        # Check tenant override first
        if tenant_id and tenant_id in self._tenant_configs:
            tenant_config = self._tenant_configs[tenant_id]
            if "hooks" in tenant_config and hook_name in tenant_config["hooks"]:
                return tenant_config["hooks"][hook_name]
        
        # Check global config
        if hook_name in self._config["hooks"]:
            return self._config["hooks"][hook_name]
        
        return None
    
    def is_hook_enabled(self, hook_name: str, tenant_id: Optional[str] = None) -> bool:
        """
        Check if a hook is enabled.
        
        Returns:
            True if hook is enabled and feature is enabled
        """
        hook_config = self.get_hook_config(hook_name, tenant_id)
        if not hook_config:
            return False
        
        return hook_config.get("enabled", False)
    
    def get_enabled_hooks(self, tenant_id: Optional[str] = None) -> List[tuple]:
        """
        Get all enabled hooks sorted by priority (highest first).
        
        Returns:
            List of (hook_name, hook_config) tuples sorted by priority
        """
        hooks = self._config["hooks"].copy()
        
        # Apply tenant overrides
        if tenant_id and tenant_id in self._tenant_configs:
            tenant_config = self._tenant_configs[tenant_id]
            if "hooks" in tenant_config:
                hooks.update(tenant_config["hooks"])
        
        # Filter enabled hooks and sort by priority (descending)
        enabled = [
            (name, config) for name, config in hooks.items()
            if config.get("enabled", False)
        ]
        
        return sorted(enabled, key=lambda x: x[1].get("priority", 0), reverse=True)
    
    def get_hooks_for_event(self, event_name: str, tenant_id: Optional[str] = None) -> List[str]:
        """
        Get all enabled hooks that listen for a specific event.
        
        Args:
            event_name: Name of event (e.g., "document.uploaded")
            tenant_id: Optional tenant ID
        
        Returns:
            List of hook names in priority order
        """
        enabled_hooks = self.get_enabled_hooks(tenant_id)
        
        matching = []
        for hook_name, hook_config in enabled_hooks:
            trigger_events = hook_config.get("trigger_events", [])
            if event_name in trigger_events:
                matching.append(hook_name)
        
        return matching
    
    def set_hook_enabled(self, hook_name: str, enabled: bool) -> bool:
        """Enable or disable a hook at runtime."""
        try:
            if hook_name not in self._config["hooks"]:
                logger.error(f"Hook '{hook_name}' not found")
                return False
            
            self._config["hooks"][hook_name]["enabled"] = enabled
            logger.info(f"Hook '{hook_name}' set to {enabled}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting hook '{hook_name}': {e}")
            return False
    
    # ========================================================================
    # QUEUE CONFIGURATION MANAGEMENT
    # ========================================================================
    
    def get_queue_config(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get job queue configuration.
        
        Returns:
            Queue configuration dict
        """
        config = self._config["queue"].copy()
        
        # Apply tenant overrides
        if tenant_id and tenant_id in self._tenant_configs:
            tenant_config = self._tenant_configs[tenant_id]
            if "queue" in tenant_config:
                config.update(tenant_config["queue"])
        
        return config

    def set_queue_values(self, values: Dict[str, Any]) -> bool:
        """Set global queue configuration values at runtime."""
        try:
            if not isinstance(values, dict):
                return False
            for key, value in values.items():
                if key in self._config["queue"] and value is not None:
                    self._config["queue"][key] = value
            return validate_queue_config(self._config["queue"])
        except Exception as e:
            logger.error(f"Error setting queue values: {e}")
            return False
    
    def get_max_workers(self, tenant_id: Optional[str] = None) -> int:
        """Get max number of job queue workers."""
        config = self.get_queue_config(tenant_id)
        return config.get("max_workers", 4)
    
    def get_max_retries(self, tenant_id: Optional[str] = None) -> int:
        """Get max number of job retries."""
        config = self.get_queue_config(tenant_id)
        return config.get("max_retries", 3)
    
    def get_job_timeout_seconds(self, tenant_id: Optional[str] = None) -> int:
        """Get job execution timeout in seconds."""
        config = self.get_queue_config(tenant_id)
        return config.get("job_timeout_seconds", 3600)
    
    def get_retry_delay_seconds(self, retry_count: int, tenant_id: Optional[str] = None) -> int:
        """
        Calculate exponential backoff delay for retry.
        
        Args:
            retry_count: Number of retries already attempted
            tenant_id: Optional tenant ID
        
        Returns:
            Delay in seconds before next retry
        """
        config = self.get_queue_config(tenant_id)
        
        base = config.get("exponential_backoff_base", 2)
        initial = config.get("initial_retry_delay_seconds", 5)
        max_delay = config.get("max_retry_delay_seconds", 300)
        
        delay = initial * (base ** retry_count)
        return min(delay, max_delay)
    
    # ========================================================================
    # CACHE CONFIGURATION MANAGEMENT
    # ========================================================================
    
    def get_cache_config(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get cache configuration."""
        config = self._config["cache"].copy()
        
        if tenant_id and tenant_id in self._tenant_configs:
            tenant_config = self._tenant_configs[tenant_id]
            if "cache" in tenant_config:
                config.update(tenant_config["cache"])
        
        return config

    def set_cache_values(self, values: Dict[str, Any]) -> bool:
        """Set global cache configuration values at runtime."""
        try:
            if not isinstance(values, dict):
                return False
            for key, value in values.items():
                if key in self._config["cache"] and value is not None:
                    self._config["cache"][key] = value
            return True
        except Exception as e:
            logger.error(f"Error setting cache values: {e}")
            return False
    
    def get_cache_ttl_seconds(self, tenant_id: Optional[str] = None) -> int:
        """Get default cache TTL."""
        config = self.get_cache_config(tenant_id)
        return config.get("cache_ttl_seconds", 86400)
    
    # ========================================================================
    # GENERAL CONFIGURATION
    # ========================================================================
    
    def get_environment(self) -> str:
        """Get current environment (development, staging, production)."""
        return self._config["general"]["environment"]
    
    def is_debug_mode(self) -> bool:
        """Check if debug mode is enabled."""
        return self._config["general"]["debug_mode"]
    
    def get_log_level(self) -> str:
        """Get log level."""
        return self._config["general"]["log_level"]

    def get_general_config(self) -> Dict[str, Any]:
        """Get general runtime configuration."""
        return self._config["general"].copy()

    def get_general_value(self, key: str, default: Any = None) -> Any:
        """Get a single general configuration value."""
        return self._config["general"].get(key, default)

    def set_general_values(self, values: Dict[str, Any]) -> bool:
        """Set general configuration values at runtime."""
        try:
            if not isinstance(values, dict):
                return False
            for key, value in values.items():
                if key in self._config["general"] and value is not None:
                    self._config["general"][key] = value
            return True
        except Exception as e:
            logger.error(f"Error setting general values: {e}")
            return False
    
    # ========================================================================
    # TENANT CONFIGURATION MANAGEMENT
    # ========================================================================
    
    def set_tenant_config(self, tenant_id: str, config_overrides: Dict[str, Any]) -> bool:
        """
        Set configuration overrides for a specific tenant.
        
        Args:
            tenant_id: Tenant ID
            config_overrides: Dict with "features", "hooks", "queue" keys for overrides
        
        Returns:
            True if successful
        
        Example:
            config.set_tenant_config("tenant123", {
                "features": {"auto_extract": {"enabled": False}},
                "queue": {"max_workers": 8}
            })
        """
        try:
            # Validate overrides
            if "features" in config_overrides:
                if not validate_feature_config(config_overrides["features"]):
                    logger.error(f"Invalid feature config for tenant {tenant_id}")
                    return False
            
            if "hooks" in config_overrides:
                if not validate_hook_config(config_overrides["hooks"]):
                    logger.error(f"Invalid hook config for tenant {tenant_id}")
                    return False
            
            if "queue" in config_overrides:
                if not validate_queue_config(config_overrides["queue"]):
                    logger.error(f"Invalid queue config for tenant {tenant_id}")
                    return False
            
            self._tenant_configs[tenant_id] = config_overrides
            logger.info(f"Tenant config set for {tenant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting tenant config: {e}")
            return False
    
    def get_tenant_config(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get configuration overrides for a tenant."""
        return self._tenant_configs.get(tenant_id)
    
    def remove_tenant_config(self, tenant_id: str) -> bool:
        """Remove configuration overrides for a tenant."""
        if tenant_id in self._tenant_configs:
            del self._tenant_configs[tenant_id]
            logger.info(f"Tenant config removed for {tenant_id}")
            return True
        return False
    
    # ========================================================================
    # CONFIGURATION VALIDATION & HEALTH
    # ========================================================================
    
    def validate_config(self) -> bool:
        """
        Validate entire configuration.
        
        Returns:
            True if valid, False otherwise
        """
        self._validation_errors = []
        
        try:
            # Validate features
            if not validate_feature_config(self._config["features"]):
                self._validation_errors.append("Invalid feature configuration")
                return False
            
            # Validate hooks
            if not validate_hook_config(self._config["hooks"]):
                self._validation_errors.append("Invalid hook configuration")
                return False
            
            # Validate queue
            if not validate_queue_config(self._config["queue"]):
                self._validation_errors.append("Invalid queue configuration")
                return False
            
            logger.info("Configuration validation passed")
            return True
            
        except Exception as e:
            self._validation_errors.append(str(e))
            logger.error(f"Configuration validation failed: {e}")
            return False
    
    def get_validation_errors(self) -> List[str]:
        """Get list of validation errors."""
        return self._validation_errors.copy()
    
    def reload_config(self) -> bool:
        """
        Reload configuration from defaults and environment variables.
        
        Note: Tenant overrides are preserved.
        
        Returns:
            True if successful
        """
        try:
            old_tenant_configs = self._tenant_configs.copy()
            
            self._config = get_default_config()
            self._tenant_configs = old_tenant_configs
            self._last_reload = datetime.now()
            
            if self.validate_config():
                logger.info("Configuration reloaded successfully")
                return True
            else:
                logger.error("Configuration reload failed validation")
                return False
                
        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")
            return False
    
    def get_last_reload_time(self) -> datetime:
        """Get time of last configuration reload."""
        return self._last_reload
    
    # ========================================================================
    # CONFIGURATION EXPORT & IMPORT
    # ========================================================================
    
    def export_config(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """
        Export current configuration.
        
        Args:
            include_sensitive: Whether to include sensitive values (API keys, etc)
        
        Returns:
            Configuration dictionary
        """
        config = self._config.copy()
        
        if not include_sensitive:
            # Remove sensitive values
            if "cache" in config and "redis_url" in config["cache"]:
                config["cache"]["redis_url"] = "***"
            
            if "queue" in config and "db_path" in config["queue"]:
                config["queue"]["db_path"] = "***"
        
        return config
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get summary of configuration (useful for debugging)."""
        return {
            "environment": self.get_environment(),
            "debug_mode": self.is_debug_mode(),
            "max_workers": self.get_max_workers(),
            "max_retries": self.get_max_retries(),
            "auto_extract_enabled": self.is_feature_enabled("auto_extract"),
            "web_search_enabled": self.is_feature_enabled("web_search_enabled"),
            "enabled_hooks_count": len(self.get_enabled_hooks()),
            "enabled_features_count": sum(1 for f in self._config["features"].values() if f.get("enabled")),
            "tenant_configs_count": len(self._tenant_configs),
            "last_reload": self._last_reload.isoformat(),
        }


# Convenience functions were moved to app.config_manager and are
# re-exported at the top of this shim.  Do NOT redefine them here.
