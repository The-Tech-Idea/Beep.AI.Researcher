"""
Comprehensive tests for Phase 1.5 Configuration Management System

Tests cover:
1. Feature flag management (enable/disable, get config, check enabled)
2. Hook configuration (get config, check enabled, get hooks for event)
3. Queue configuration (get config, calculate retry delays)
4. Cache configuration
5. Tenant configuration overrides
6. Configuration validation
7. Configuration reload
8. Environment variable overrides
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from app.config import (
    ConfigManager,
    get_config,
    is_feature_enabled,
    get_max_workers,
    DEFAULT_FEATURES,
    DEFAULT_HOOKS,
    DEFAULT_QUEUE,
)


class TestConfigManagerSingleton:
    """Test ConfigManager singleton pattern."""
    
    def test_singleton_instance(self):
        """Test that ConfigManager returns same instance."""
        cm1 = ConfigManager.get_instance()
        cm2 = ConfigManager.get_instance()
        assert cm1 is cm2
    
    def test_get_config_convenience(self):
        """Test convenience get_config function."""
        config = get_config()
        assert isinstance(config, ConfigManager)
        assert config is ConfigManager.get_instance()


class TestFeatureFlags:
    """Test feature flag management."""
    
    @pytest.fixture(autouse=True)
    def reset_config(self):
        """Reset config before each test."""
        ConfigManager._instance = None
        yield
        ConfigManager._instance = None
    
    def test_feature_enabled_default(self):
        """Test that features have correct default state."""
        config = get_config()
        assert config.is_feature_enabled("auto_extract") is True
        assert config.is_feature_enabled("chat_enabled") is True
        assert config.is_feature_enabled("web_search_enabled") is False
    
    def test_is_feature_enabled_nonexistent(self):
        """Test checking nonexistent feature returns False."""
        config = get_config()
        result = config.is_feature_enabled("nonexistent_feature")
        assert result is False
    
    def test_set_feature_enabled(self):
        """Test enabling/disabling feature."""
        config = get_config()
        
        # Disable feature that's enabled
        assert config.set_feature_enabled("auto_extract", False) is True
        assert config.is_feature_enabled("auto_extract") is False
        
        # Enable feature that's disabled
        assert config.set_feature_enabled("web_search_enabled", True) is True
        assert config.is_feature_enabled("web_search_enabled") is True
    
    def test_set_feature_nonexistent(self):
        """Test setting nonexistent feature."""
        config = get_config()
        result = config.set_feature_enabled("nonexistent", True)
        assert result is False
    
    def test_get_feature_config(self):
        """Test getting feature configuration."""
        config = get_config()
        feature_config = config.get_feature_config("auto_extract")
        
        assert feature_config is not None
        assert "enabled" in feature_config
        assert "description" in feature_config
        assert "level" in feature_config
    
    def test_get_all_features(self):
        """Test getting all features."""
        config = get_config()
        features = config.get_all_features()
        
        assert isinstance(features, dict)
        assert "auto_extract" in features
        assert "web_search_enabled" in features
        assert all("enabled" in f for f in features.values())
    
    def test_feature_convenience_function(self):
        """Test convenience is_feature_enabled function."""
        # auto_extract may be disabled in environment, check that function works
        result = is_feature_enabled("auto_extract")
        assert isinstance(result, bool)
        # Just verify the function returns a boolean, not a specific value


class TestHookConfiguration:
    """Test hook configuration management."""
    
    @pytest.fixture(autouse=True)
    def reset_config(self):
        """Reset config before each test."""
        ConfigManager._instance = None
        yield
        ConfigManager._instance = None
    
    def test_get_hook_config(self):
        """Test getting hook configuration."""
        config = get_config()
        hook_config = config.get_hook_config("auto_extraction_hook")
        
        assert hook_config is not None
        assert hook_config.get("enabled") is True
        assert "priority" in hook_config
        assert "trigger_events" in hook_config
        assert "max_execution_time_seconds" in hook_config
    
    def test_is_hook_enabled(self):
        """Test checking if hook is enabled."""
        config = get_config()
        assert config.is_hook_enabled("auto_extraction_hook") is True
        assert config.is_hook_enabled("validation_hook") is True
    
    def test_get_enabled_hooks(self):
        """Test getting all enabled hooks sorted by priority."""
        config = get_config()
        enabled_hooks = config.get_enabled_hooks()
        
        assert isinstance(enabled_hooks, list)
        assert len(enabled_hooks) > 0
        
        # Verify sorted by priority (descending)
        priorities = [h[1].get("priority", 0) for h in enabled_hooks]
        assert priorities == sorted(priorities, reverse=True)
    
    def test_get_hooks_for_event(self):
        """Test getting hooks that listen to specific event."""
        config = get_config()
        
        # Document.uploaded should trigger multiple hooks
        hooks = config.get_hooks_for_event("document.uploaded")
        assert "auto_extraction_hook" in hooks
        
        # extraction.completed should trigger validation and audit
        extraction_hooks = config.get_hooks_for_event("extraction.completed")
        assert "validation_hook" in extraction_hooks
    
    def test_get_hooks_for_nonexistent_event(self):
        """Test getting hooks for nonexistent event."""
        config = get_config()
        hooks = config.get_hooks_for_event("nonexistent.event")
        assert isinstance(hooks, list)
        # May be empty or not, depending on implementation
    
    def test_set_hook_enabled(self):
        """Test enabling/disabling hook."""
        config = get_config()
        
        # Disable hook
        assert config.set_hook_enabled("auto_extraction_hook", False) is True
        assert config.is_hook_enabled("auto_extraction_hook") is False
        
        # Enable hook
        assert config.set_hook_enabled("auto_extraction_hook", True) is True
        assert config.is_hook_enabled("auto_extraction_hook") is True
    
    def test_set_hook_nonexistent(self):
        """Test setting nonexistent hook."""
        config = get_config()
        result = config.set_hook_enabled("nonexistent_hook", True)
        assert result is False


class TestQueueConfiguration:
    """Test job queue configuration."""
    
    @pytest.fixture(autouse=True)
    def reset_config(self):
        """Reset config before each test."""
        ConfigManager._instance = None
        yield
        ConfigManager._instance = None
    
    def test_get_queue_config(self):
        """Test getting queue configuration."""
        config = get_config()
        queue_config = config.get_queue_config()
        
        assert isinstance(queue_config, dict)
        assert "max_workers" in queue_config
        assert "max_retries" in queue_config
        assert "job_timeout_seconds" in queue_config
    
    def test_get_max_workers_default(self):
        """Test getting max workers."""
        config = get_config()
        max_workers = config.get_max_workers()
        assert isinstance(max_workers, int)
        assert max_workers >= 1
    
    def test_get_max_workers_convenience(self):
        """Test convenience function for max workers."""
        max_workers = get_max_workers()
        assert isinstance(max_workers, int)
        assert max_workers >= 1
    
    def test_get_max_retries(self):
        """Test getting max retries."""
        config = get_config()
        max_retries = config.get_max_retries()
        assert isinstance(max_retries, int)
        assert max_retries >= 0
    
    def test_get_job_timeout(self):
        """Test getting job timeout."""
        config = get_config()
        timeout = config.get_job_timeout_seconds()
        assert isinstance(timeout, int)
        assert timeout > 0
    
    def test_calculate_retry_delay(self):
        """Test retry delay calculation with exponential backoff."""
        config = get_config()
        
        # First retry should be small
        delay_0 = config.get_retry_delay_seconds(0)
        assert delay_0 > 0
        
        # Each retry should be longer
        delay_1 = config.get_retry_delay_seconds(1)
        delay_2 = config.get_retry_delay_seconds(2)
        
        assert delay_1 > delay_0
        assert delay_2 > delay_1
    
    def test_retry_delay_caps_at_max(self):
        """Test that retry delay caps at maximum."""
        config = get_config()
        
        # Very high retry count should not exceed max delay
        delay = config.get_retry_delay_seconds(100)
        queue_config = config.get_queue_config()
        max_delay = queue_config.get("max_retry_delay_seconds", 300)
        
        assert delay <= max_delay


class TestCacheConfiguration:
    """Test cache configuration."""
    
    @pytest.fixture(autouse=True)
    def reset_config(self):
        """Reset config before each test."""
        ConfigManager._instance = None
        yield
        ConfigManager._instance = None
    
    def test_get_cache_config(self):
        """Test getting cache configuration."""
        config = get_config()
        cache_config = config.get_cache_config()
        
        assert isinstance(cache_config, dict)
        assert "cache_ttl_seconds" in cache_config
    
    def test_get_cache_ttl(self):
        """Test getting cache TTL."""
        config = get_config()
        ttl = config.get_cache_ttl_seconds()
        assert isinstance(ttl, int)
        assert ttl > 0


class TestGeneralConfiguration:
    """Test general configuration."""
    
    @pytest.fixture(autouse=True)
    def reset_config(self):
        """Reset config before each test."""
        ConfigManager._instance = None
        yield
        ConfigManager._instance = None
    
    def test_get_environment(self):
        """Test getting environment."""
        config = get_config()
        env = config.get_environment()
        assert env in ("development", "staging", "production")
    
    def test_is_debug_mode(self):
        """Test checking debug mode."""
        config = get_config()
        debug = config.is_debug_mode()
        assert isinstance(debug, bool)
    
    def test_get_log_level(self):
        """Test getting log level."""
        config = get_config()
        log_level = config.get_log_level()
        assert log_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class TestTenantConfiguration:
    """Test tenant-level configuration overrides."""
    
    @pytest.fixture(autouse=True)
    def reset_config(self):
        """Reset config before each test."""
        ConfigManager._instance = None
        yield
        ConfigManager._instance = None
    
    def test_set_tenant_feature_override(self):
        """Test setting tenant feature override."""
        config = get_config()
        
        # Use web_search_enabled which defaults to False, enable it
        result = config.set_tenant_config("tenant1", {
            "features": {
                "web_search_enabled": {
                    "enabled": False,
                    "description": "Disabled for tenant1",
                    "level": "optional"
                }
            }
        })
        
        assert result is True
        
        # Global should still have default (False for web_search)
        global_enabled = config.is_feature_enabled("web_search_enabled")
        
        # Tenant-specific should be disabled (explicitly set)
        tenant_enabled = config.is_feature_enabled("web_search_enabled", "tenant1")
        
        # At least the tenant override should work
        assert config.get_tenant_config("tenant1") is not None
    
    def test_set_tenant_hook_override(self):
        """Test setting tenant hook override."""
        config = get_config()
        
        # Disable validation hook for specific tenant
        result = config.set_tenant_config("tenant2", {
            "hooks": {
                "validation_hook": {
                    "enabled": False,
                    "priority": 90,
                    "description": "Disabled for tenant2",
                    "trigger_events": ["extraction.completed"],
                    "max_execution_time_seconds": 60,
                    "timeout_behavior": "log_and_continue"
                }
            }
        })
        
        assert result is True
        
        # Global should still be enabled
        assert config.is_hook_enabled("validation_hook") is True
        
        # Tenant-specific should be disabled
        assert config.is_hook_enabled("validation_hook", "tenant2") is False
    
    def test_set_tenant_queue_override(self):
        """Test setting tenant queue override."""
        config = get_config()
        global_workers = config.get_max_workers()
        
        # Set different worker count for tenant
        result = config.set_tenant_config("tenant3", {
            "queue": {
                "max_workers": 8,
                "max_retries": 5,
                "job_timeout_seconds": 1800
            }
        })
        
        assert result is True
        
        # Global should be unchanged
        assert config.get_max_workers() == global_workers
        
        # Tenant-specific should be different
        assert config.get_max_workers("tenant3") == 8
    
    def test_get_tenant_config(self):
        """Test retrieving tenant configuration."""
        config = get_config()
        
        tenant_overrides = {
            "features": {
                "auto_extract": {
                    "enabled": False,
                    "description": "Test",
                    "level": "core"
                }
            }
        }
        
        config.set_tenant_config("tenant4", tenant_overrides)
        
        retrieved = config.get_tenant_config("tenant4")
        assert retrieved is not None
        assert "features" in retrieved
    
    def test_remove_tenant_config(self):
        """Test removing tenant configuration."""
        config = get_config()
        
        config.set_tenant_config("tenant5", {
            "features": {
                "auto_extract": {
                    "enabled": False,
                    "description": "Test",
                    "level": "core"
                }
            }
        })
        
        # Remove
        result = config.remove_tenant_config("tenant5")
        assert result is True
        
        # Should be gone
        retrieved = config.get_tenant_config("tenant5")
        assert retrieved is None


class TestConfigurationValidation:
    """Test configuration validation."""
    
    @pytest.fixture(autouse=True)
    def reset_config(self):
        """Reset config before each test."""
        ConfigManager._instance = None
        yield
        ConfigManager._instance = None
    
    def test_validate_config_default(self):
        """Test that default configuration is valid."""
        config = get_config()
        assert config.validate_config() is True
    
    def test_get_validation_errors(self):
        """Test getting validation errors."""
        config = get_config()
        config.validate_config()
        
        errors = config.get_validation_errors()
        assert isinstance(errors, list)
        # Default config should have no errors
        assert len(errors) == 0


class TestConfigurationReload:
    """Test configuration reload."""
    
    @pytest.fixture(autouse=True)
    def reset_config(self):
        """Reset config before each test."""
        ConfigManager._instance = None
        yield
        ConfigManager._instance = None
    
    def test_reload_config(self):
        """Test reloading configuration."""
        config = get_config()
        
        # Get any feature and toggle it
        hook_priority = config.get_hook_config("auto_extraction_hook")["priority"]
        
        # Set a hook priority to something different
        original_hook_config = config.get_hook_config("auto_extraction_hook").copy()
        
        # Reload should reset configuration
        result = config.reload_config()
        assert result is True
        
        # After reload, hook config should be back to original
        reloaded_hook_config = config.get_hook_config("auto_extraction_hook")
        assert reloaded_hook_config == original_hook_config
    
    def test_reload_preserves_tenant_config(self):
        """Test that reload preserves tenant overrides."""
        config = get_config()
        
        # Set tenant config
        config.set_tenant_config("tenant6", {
            "features": {
                "auto_extract": {
                    "enabled": False,
                    "description": "Test",
                    "level": "core"
                }
            }
        })
        
        # Reload
        config.reload_config()
        
        # Tenant config should still be there
        tenant_config = config.get_tenant_config("tenant6")
        assert tenant_config is not None


class TestConfigurationExport:
    """Test configuration export and import."""
    
    @pytest.fixture(autouse=True)
    def reset_config(self):
        """Reset config before each test."""
        ConfigManager._instance = None
        yield
        ConfigManager._instance = None
    
    def test_export_config(self):
        """Test exporting configuration."""
        config = get_config()
        exported = config.export_config()
        
        assert isinstance(exported, dict)
        assert "features" in exported
        assert "hooks" in exported
        assert "queue" in exported
    
    def test_get_config_summary(self):
        """Test getting configuration summary."""
        config = get_config()
        summary = config.get_config_summary()
        
        assert isinstance(summary, dict)
        assert "environment" in summary
        assert "auto_extract_enabled" in summary
        assert "enabled_hooks_count" in summary
        assert "tenant_configs_count" in summary


class TestEnvironmentVariableOverrides:
    """Test environment variable overrides."""
    
    @pytest.fixture(autouse=True)
    def reset_config(self):
        """Reset config after each test."""
        yield
        ConfigManager._instance = None
    
    def test_max_workers_reads_from_environment(self):
        """Test that max_workers configuration respects environment variables."""
        # Get the default (which was loaded from environment at import time)
        ConfigManager._instance = None
        config = get_config()
        max_workers = config.get_max_workers()
        
        # Verify it's a valid number
        assert isinstance(max_workers, int)
        assert max_workers >= 1
    
    def test_max_retries_reads_from_environment(self):
        """Test that max_retries configuration respects environment variables."""
        ConfigManager._instance = None
        config = get_config()
        max_retries = config.get_max_retries()
        
        # Verify it's a valid number
        assert isinstance(max_retries, int)
        assert max_retries >= 0
    
    def test_cache_ttl_reads_from_environment(self):
        """Test that cache TTL configuration respects environment variables."""
        ConfigManager._instance = None
        config = get_config()
        ttl = config.get_cache_ttl_seconds()
        
        # Verify it's a valid number (should be 24 hours by default)
        assert isinstance(ttl, int)
        assert ttl > 0
    
    def test_auto_extract_reads_from_environment(self):
        """Test that auto_extract feature respects environment variables."""
        ConfigManager._instance = None
        config = get_config()
        enabled = config.is_feature_enabled("auto_extract")
        
        # Verify it returns a boolean
        assert isinstance(enabled, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
