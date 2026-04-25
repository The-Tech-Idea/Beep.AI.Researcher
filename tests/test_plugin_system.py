"""Tests for plugin system Phase 3.1 (Plugin Architecture)."""
import asyncio
import json
import pytest
from datetime import datetime
from typing import Any, Dict

from app.database import db
from app.models.researcher.plugins import (
    Plugin, PluginConfiguration, PluginHookRegistration,
    PluginExecutionLog, PluginStatus, PluginType, HookPoint
)
from app.services.plugin_base import (
    PluginMetadata, HookContext, HookResult, PluginBase
)
from app.services.plugin_manager import PluginManager, get_plugin_manager
from app.services.plugin_registry import PluginRegistryManager, get_plugin_registry


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def plugin_metadata():
    """Create test plugin metadata."""
    return PluginMetadata(
        name="test_plugin",
        display_name="Test Plugin",
        version="1.0.0",
        description="Test plugin for unit testing",
        author="Test Author",
        author_email="test@example.com",
        plugin_type=PluginType.CUSTOM.value,
        dependencies=["dependency_plugin"],
        config_schema={
            "param1": {"type": "string", "required": True},
            "param2": {"type": "integer", "default": 10},
        },
        default_config={
            "param1": "default_value",
            "param2": 10,
        },
    )


class ConcretePlugin(PluginBase):
    """Concrete plugin implementation for testing."""

    async def on_plugin_load(self, context: HookContext) -> HookResult:
        """Test implementation."""
        return HookResult(
            success=True,
            plugin_name=self.metadata.name,
            hook_point=context.hook_point,
            execution_time_ms=1.5,
        )

    async def on_plugin_unload(self, context: HookContext) -> HookResult:
        """Test implementation."""
        return HookResult(
            success=True,
            plugin_name=self.metadata.name,
            hook_point=context.hook_point,
            execution_time_ms=0.5,
        )

    async def on_extraction(self, context: HookContext) -> HookResult:
        """Test extraction hook."""
        return HookResult(
            success=True,
            plugin_name=self.metadata.name,
            hook_point=context.hook_point,
            execution_time_ms=2.0,
            suggestions=["suggestion1", "suggestion2"],
        )


# ============================================================================
# PluginMetadata Tests
# ============================================================================

class TestPluginMetadata:
    """Test PluginMetadata functionality."""

    def test_metadata_creation(self, plugin_metadata):
        """Test creating plugin metadata."""
        assert plugin_metadata.name == "test_plugin"
        assert plugin_metadata.version == "1.0.0"
        assert len(plugin_metadata.dependencies) == 1
        assert "param1" in plugin_metadata.config_schema

    def test_metadata_to_dict(self, plugin_metadata):
        """Test converting metadata to dict."""
        data = plugin_metadata.to_dict()
        assert isinstance(data, dict)
        assert data["name"] == "test_plugin"
        assert data["version"] == "1.0.0"
        assert isinstance(data["dependencies"], list)
        assert isinstance(data["default_config"], dict)


# ============================================================================
# HookContext Tests
# ============================================================================

class TestHookContext:
    """Test HookContext functionality."""

    def test_context_creation(self):
        """Test creating hook context."""
        context = HookContext(
            hook_point="on_extraction",
            project_id=1,
            tenant_id=1,
            user_id=1,
            data={"field": "value"},
        )
        assert context.hook_point == "on_extraction"
        assert context.project_id == 1
        assert context.data["field"] == "value"

    def test_context_to_dict(self):
        """Test converting context to dict."""
        context = HookContext(
            hook_point="on_extraction",
            project_id=1,
            data={"test": "data"},
        )
        data = context.to_dict()
        assert isinstance(data, dict)
        assert data["hook_point"] == "on_extraction"
        assert data["project_id"] == 1


# ============================================================================
# HookResult Tests
# ============================================================================

class TestHookResult:
    """Test HookResult functionality."""

    def test_result_creation_success(self):
        """Test creating successful hook result."""
        result = HookResult(
            success=True,
            plugin_name="test_plugin",
            hook_point="on_extraction",
            execution_time_ms=2.5,
        )
        assert result.success is True
        assert result.plugin_name == "test_plugin"
        assert result.status == "success"

    def test_result_creation_error(self):
        """Test creating error hook result."""
        result = HookResult(
            success=False,
            plugin_name="test_plugin",
            hook_point="on_extraction",
            execution_time_ms=1.0,
            status="error",
            error_message="Test error",
        )
        assert result.success is False
        assert result.error_message == "Test error"

    def test_result_to_dict(self):
        """Test converting result to dict."""
        result = HookResult(
            success=True,
            plugin_name="test_plugin",
            hook_point="on_extraction",
            execution_time_ms=2.5,
            suggestions=["fix1", "fix2"],
        )
        data = result.to_dict()
        assert isinstance(data, dict)
        assert data["success"] is True
        assert len(data["suggestions"]) == 2


# ============================================================================
# PluginBase Tests
# ============================================================================

class TestPluginBase:
    """Test PluginBase functionality."""

    def test_plugin_initialization(self, plugin_metadata):
        """Test plugin initialization."""
        plugin = ConcretePlugin(plugin_metadata)
        assert plugin.metadata.name == "test_plugin"
        assert plugin.is_loaded is False
        assert len(plugin.hooks) > 0

    def test_plugin_config_management(self, plugin_metadata):
        """Test plugin configuration management."""
        plugin = ConcretePlugin(plugin_metadata)
        
        # Test get config
        config = plugin.get_config()
        assert config["param1"] == "default_value"
        assert config["param2"] == 10

        # Test update config
        plugin.set_config({"param1": "new_value"})
        assert plugin.get_config()["param1"] == "new_value"

    def test_plugin_hooks_registration(self, plugin_metadata):
        """Test hook registration."""
        plugin = ConcretePlugin(plugin_metadata)
        assert "on_plugin_load" in plugin.hooks
        assert "on_plugin_unload" in plugin.hooks
        assert "on_extraction" in plugin.hooks

    @pytest.mark.asyncio
    async def test_plugin_hook_execution(self, plugin_metadata):
        """Test hook execution."""
        plugin = ConcretePlugin(plugin_metadata)
        context = HookContext(hook_point="on_extraction")

        result = await plugin.on_extraction(context)

        assert result.success is True
        assert result.execution_time_ms >= 2.0
        assert len(result.suggestions) == 2

    def test_plugin_metadata_access(self, plugin_metadata):
        """Test accessing plugin metadata."""
        plugin = ConcretePlugin(plugin_metadata)
        metadata = plugin.get_metadata()

        assert metadata.name == plugin_metadata.name
        assert metadata.version == plugin_metadata.version

    def test_plugin_repr(self, plugin_metadata):
        """Test string representation."""
        plugin = ConcretePlugin(plugin_metadata)
        repr_str = repr(plugin)

        assert "test_plugin" in repr_str
        assert "1.0.0" in repr_str


# ============================================================================
# PluginManager Tests
# ============================================================================

class TestPluginManager:
    """Test PluginManager functionality."""

    @pytest.fixture
    def manager(self, app_context):
        """Create plugin manager within app context."""
        return PluginManager()

    @pytest.fixture
    def plugin_record(self, app_context, plugin_metadata):
        """Create plugin database record within app context."""
        plugin = Plugin(
            name=plugin_metadata.name,
            display_name=plugin_metadata.display_name,
            version=plugin_metadata.version,
            description=plugin_metadata.description,
            author=plugin_metadata.author,
            author_email=plugin_metadata.author_email,
            plugin_type=plugin_metadata.plugin_type,
            module_path="app.services.test_plugins.TestPlugin",
            class_name="TestPlugin",
            status=PluginStatus.INSTALLED.value,
        )
        db.session.add(plugin)
        db.session.commit()
        return plugin

    def test_manager_initialization(self, manager):
        """Test manager initialization."""
        assert manager._is_initialized is False
        assert len(manager._plugins) == 0

    @pytest.mark.asyncio
    async def test_execute_hook_no_plugins(self, manager):
        """Test executing hook with no registered plugins."""
        context = HookContext(hook_point="on_extraction")
        results = await manager.execute_hook("on_extraction", context)

        assert isinstance(results, list)
        assert len(results) == 0

    def test_get_plugin_not_loaded(self, manager):
        """Test getting non-existent plugin."""
        plugin = manager.get_plugin("nonexistent")
        assert plugin is None

    def test_list_plugins_empty(self, manager):
        """Test listing plugins when none loaded."""
        plugins = manager.list_plugins()
        assert isinstance(plugins, list)
        assert len(plugins) == 0

    def test_get_hook_registry(self, manager):
        """Test getting hook registry."""
        registry = manager.get_hook_registry()
        assert isinstance(registry, dict)
        assert len(registry) == 0


# ============================================================================
# PluginRegistryManager Tests
# ============================================================================

class TestPluginRegistryManager:
    """Test PluginRegistryManager functionality."""

    @pytest.fixture
    def registry(self, app_context):
        """Create registry manager within app context."""
        return PluginRegistryManager()

    @pytest.mark.asyncio
    async def test_registry_initialization(self, registry):
        """Test registry initialization."""
        result = await registry.initialize()
        assert result is True

    @pytest.mark.asyncio
    async def test_register_registry(self, registry):
        """Test registering a new registry."""
        await registry.initialize()
        registry_record = await registry.register_registry(
            registry_name="test_registry",
            registry_url="https://example.com",
            description="Test registry",
        )

        assert registry_record.registry_name == "test_registry"
        assert registry_record.is_active is True

    @pytest.mark.asyncio
    async def test_register_plugin(self, registry, plugin_metadata):
        """Test registering a plugin."""
        await registry.initialize()
        
        plugin_record = await registry.register_plugin(
            plugin_name=plugin_metadata.name,
            metadata=plugin_metadata,
            module_path="test.module.TestPlugin",
            class_name="TestPlugin",
        )

        assert plugin_record.name == plugin_metadata.name
        assert plugin_record.display_name == plugin_metadata.display_name

    @pytest.mark.asyncio
    async def test_list_plugins(self, registry, plugin_metadata):
        """Test listing plugins."""
        await registry.initialize()
        
        await registry.register_plugin(
            plugin_name=plugin_metadata.name,
            metadata=plugin_metadata,
            module_path="test.module.TestPlugin",
            class_name="TestPlugin",
        )

        plugins = await registry.list_plugins()
        assert len(plugins) > 0
        assert any(p["name"] == plugin_metadata.name for p in plugins)

    @pytest.mark.asyncio
    async def test_discover_plugins(self, registry, plugin_metadata):
        """Test discovering plugins."""
        await registry.initialize()
        
        await registry.register_plugin(
            plugin_name=plugin_metadata.name,
            metadata=plugin_metadata,
            module_path="test.module.TestPlugin",
            class_name="TestPlugin",
        )

        discovered = await registry.discover_plugins()
        assert len(discovered) > 0
        assert any(p["name"] == plugin_metadata.name for p in discovered)

    @pytest.mark.asyncio
    async def test_enable_disable_plugin(self, registry, plugin_metadata):
        """Test enabling/disabling plugins."""
        await registry.initialize()
        
        plugin_record = await registry.register_plugin(
            plugin_name=plugin_metadata.name,
            metadata=plugin_metadata,
            module_path="test.module.TestPlugin",
            class_name="TestPlugin",
        )

        # Enable
        result = await registry.enable_plugin(plugin_metadata.name)
        assert result is True
        
        # Verify enabled
        info = await registry.get_plugin_info(plugin_metadata.name)
        assert info["status"] == PluginStatus.ENABLED.value

        # Disable
        result = await registry.disable_plugin(plugin_metadata.name)
        assert result is True


# ============================================================================
# Plugin Database Models Tests
# ============================================================================

class TestPluginModels:
    """Test plugin database models."""

    def test_plugin_model_creation(self, app_context):
        """Test creating plugin record."""
        plugin = Plugin(
            name="test_plugin",
            display_name="Test Plugin",
            version="1.0.0",
            description="Test",
            author="Test Author",
            plugin_type=PluginType.CUSTOM.value,
            module_path="test.module",
            class_name="TestClass",
            status=PluginStatus.INSTALLED.value,
        )
        db.session.add(plugin)
        db.session.commit()

        assert plugin.id is not None
        assert plugin.created_at is not None

    def test_plugin_configuration_model(self, app_context):
        """Test creating plugin configuration."""
        # Create plugin first
        plugin = Plugin(
            name="test_plugin",
            display_name="Test",
            version="1.0.0",
            module_path="test.module",
            class_name="Test",
            status=PluginStatus.INSTALLED.value,
        )
        db.session.add(plugin)
        db.session.commit()

        # Create configuration
        config = PluginConfiguration(
            plugin_id=plugin.id,
            project_id=1,
            is_enabled=True,
            config_json=json.dumps({"key": "value"}),
        )
        db.session.add(config)
        db.session.commit()

        assert config.id is not None
        assert config.is_enabled is True

    def test_plugin_hook_registration_model(self, app_context):
        """Test creating hook registration."""
        plugin = Plugin(
            name="test_plugin",
            display_name="Test",
            version="1.0.0",
            module_path="test.module",
            class_name="Test",
            status=PluginStatus.INSTALLED.value,
        )
        db.session.add(plugin)
        db.session.commit()

        registration = PluginHookRegistration(
            plugin_id=plugin.id,
            hook_point="on_extraction",
            handler_method="on_extraction",
            execution_order=100,
            is_active=True,
        )
        db.session.add(registration)
        db.session.commit()

        assert registration.id is not None
        assert registration.is_active is True

    def test_plugin_execution_log_model(self, app_context):
        """Test creating execution log."""
        plugin = Plugin(
            name="test_plugin",
            display_name="Test",
            version="1.0.0",
            module_path="test.module",
            class_name="Test",
            status=PluginStatus.INSTALLED.value,
        )
        db.session.add(plugin)
        db.session.commit()

        log = PluginExecutionLog(
            plugin_id=plugin.id,
            project_id=1,
            hook_point="on_extraction",
            handler_method="on_extraction",
            status="success",
            execution_time_ms=2.5,
        )
        db.session.add(log)
        db.session.commit()

        assert log.id is not None
        assert log.status == "success"


# ============================================================================
# Integration Tests
# ============================================================================

class TestPluginIntegration:
    """Integration tests for plugin system."""

    @pytest.mark.asyncio
    async def test_plugin_registration_and_discovery(self, app_context, plugin_metadata):
        """Test complete registration and discovery flow."""
        registry = get_plugin_registry()
        await registry.initialize()

        # Register plugin
        plugin_record = await registry.register_plugin(
            plugin_name=plugin_metadata.name,
            metadata=plugin_metadata,
            module_path="test.module.TestPlugin",
            class_name="TestPlugin",
        )

        # Discover plugins
        discovered = await registry.discover_plugins()

        # Verify
        assert any(p["name"] == plugin_metadata.name for p in discovered)

    @pytest.mark.asyncio
    async def test_hook_context_flow(self):
        """Test hook context flow through system."""
        # Create context
        context = HookContext(
            hook_point="on_extraction",
            project_id=1,
            tenant_id=1,
            user_id=1,
            data={
                "extraction_id": 1,
                "field_name": "test_field",
                "extracted_value": "test_value",
            },
        )

        # Verify context
        assert context.hook_point == "on_extraction"
        assert context.data["field_name"] == "test_field"

        # Convert to dict
        data = context.to_dict()
        assert isinstance(data, dict)
        assert data["project_id"] == 1
