"""Tests for legacy config_manager bridge to runtime config manager."""
import copy

from app.config import get_config
from app.config_manager import config_manager


def test_legacy_feature_overrides_sync_to_runtime(app_context):
    runtime = get_config()
    original_features = copy.deepcopy(runtime.get_all_features())
    original_legacy = copy.deepcopy(config_manager.get('features', {}))
    try:
        config_manager.set('features', {'auto_extract': False, 'chat_enabled': False})
        assert runtime.is_feature_enabled('auto_extract') is False
        assert runtime.is_feature_enabled('chat_enabled') is False
    finally:
        # Restore runtime state
        for name, cfg in original_features.items():
            runtime.set_feature_enabled(name, cfg.get('enabled', False))
        config_manager.set('features', original_legacy if isinstance(original_legacy, dict) else {})


def test_legacy_queue_cache_overrides_sync_to_runtime(app_context):
    runtime = get_config()
    original_queue = copy.deepcopy(runtime.get_queue_config())
    original_cache = copy.deepcopy(runtime.get_cache_config())
    original_legacy_queue = copy.deepcopy(config_manager.get('queue', {}))
    original_legacy_cache = copy.deepcopy(config_manager.get('cache', {}))
    try:
        config_manager.set('queue', {'max_workers': 9, 'max_retries': 4, 'job_timeout_seconds': 7200})
        config_manager.set('cache', {'cache_ttl_seconds': 1200, 'max_cache_entries': 1234})

        queue = runtime.get_queue_config()
        cache = runtime.get_cache_config()
        assert queue['max_workers'] == 9
        assert queue['max_retries'] == 4
        assert queue['job_timeout_seconds'] == 7200
        assert cache['cache_ttl_seconds'] == 1200
        assert cache['max_cache_entries'] == 1234
    finally:
        runtime.set_queue_values(original_queue)
        runtime.set_cache_values(original_cache)
        config_manager.set('queue', original_legacy_queue if isinstance(original_legacy_queue, dict) else {})
        config_manager.set('cache', original_legacy_cache if isinstance(original_legacy_cache, dict) else {})


def test_runtime_fallback_when_legacy_value_missing(app_context):
    runtime = get_config()
    original = runtime.get_max_workers()
    original_legacy_queue = copy.deepcopy(config_manager.get('queue', {}))
    try:
        config_manager.set('queue', {})
        runtime.set_queue_values({'max_workers': 7})
        # Ensure legacy path can still read from runtime when key isn't persisted.
        assert config_manager.get('queue.max_workers') == 7
    finally:
        runtime.set_queue_values({'max_workers': original})
        config_manager.set('queue', original_legacy_queue if isinstance(original_legacy_queue, dict) else {})
