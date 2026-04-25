"""Plugin manager for loading and managing plugins (Phase 3.1)."""
import asyncio
import importlib
import logging
import time
import traceback
from typing import Any, Dict, List, Optional, Type
from app.core.time_utils import utcnow_naive

from app.database import db
from app.models.researcher.plugins import (
    Plugin, PluginConfiguration, PluginHookRegistration,
    PluginExecutionLog, PluginStatus, HookPoint
)
from app.services.plugin_base import PluginBase, PluginMetadata, HookContext, HookResult

logger = logging.getLogger(__name__)


class PluginManager:
    """Central plugin manager for loading, registering, and executing plugins.
    
    Features:
    - Load plugins from module paths
    - Register plugins with hook system
    - Execute plugin hooks
    - Manage plugin lifecycle (load/unload/enable/disable)
    - Track plugin execution statistics
    - Handle plugin dependencies
    - Provide plugin configuration management
    """

    def __init__(self):
        """Initialize plugin manager."""
        self._plugins: Dict[str, PluginBase] = {}  # name -> plugin instance
        self._plugin_classes: Dict[str, Type[PluginBase]] = {}  # name -> plugin class
        self._hook_registry: Dict[str, List[str]] = {}  # hook_point -> [plugin_names]
        self._is_initialized = False
        logger.info("PluginManager initialized")

    async def initialize(self) -> bool:
        """Initialize plugin manager by loading builtin plugins.
        
        Returns:
            True if initialization successful
        """
        if self._is_initialized:
            logger.warning("PluginManager already initialized")
            return True

        try:
            # Load all enabled plugins from database
            enabled_plugins = db.session.query(Plugin).filter(
                Plugin.status.in_([PluginStatus.ENABLED.value, PluginStatus.INSTALLED.value])
            ).all()

            for plugin_record in enabled_plugins:
                try:
                    await self.load_plugin(plugin_record)
                except Exception as e:
                    logger.error(f"Failed to load plugin {plugin_record.name}: {e}")
                    plugin_record.status = PluginStatus.ERROR.value
                    plugin_record.error_message = str(e)

            db.session.commit()
            self._is_initialized = True
            logger.info(f"PluginManager initialized with {len(self._plugins)} plugins")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize PluginManager: {e}")
            return False

    async def load_plugin(self, plugin_record: Plugin) -> PluginBase:
        """Load a plugin from database record.
        
        Args:
            plugin_record: Plugin database record
            
        Returns:
            Loaded PluginBase instance
            
        Raises:
            ImportError: If plugin module cannot be imported
            AttributeError: If plugin class not found in module
        """
        if plugin_record.name in self._plugins:
            logger.warning(f"Plugin {plugin_record.name} already loaded")
            return self._plugins[plugin_record.name]

        try:
            # Dynamically import plugin module
            module = importlib.import_module(plugin_record.module_path)
            plugin_class = getattr(module, plugin_record.class_name)

            # Verify it's a PluginBase subclass
            if not issubclass(plugin_class, PluginBase):
                raise TypeError(f"{plugin_record.class_name} must extend PluginBase")

            # Create metadata from database record
            metadata = PluginMetadata(
                name=plugin_record.name,
                display_name=plugin_record.display_name,
                version=plugin_record.version,
                description=plugin_record.description,
                author=plugin_record.author,
                author_email=plugin_record.author_email,
                plugin_type=plugin_record.plugin_type,
            )

            # Instantiate plugin
            plugin_instance = plugin_class(metadata)

            # Load configuration
            if plugin_record.default_config_json:
                import json
                config = json.loads(plugin_record.default_config_json)
                plugin_instance.set_config(config)

            # Register hooks
            await self._register_plugin_hooks(plugin_record, plugin_instance)

            # Call on_plugin_load hook
            context = HookContext(
                hook_point=HookPoint.ON_PLUGIN_LOAD.value,
                data={'plugin_name': plugin_record.name}
            )
            result = await plugin_instance.on_plugin_load(context)

            if not result.success:
                raise RuntimeError(f"on_plugin_load failed: {result.error_message}")

            # Update status
            plugin_record.status = PluginStatus.ENABLED.value
            plugin_record.enabled_at = utcnow_naive()
            plugin_record.error_message = None
            db.session.add(plugin_record)

            # Store plugin instance
            self._plugins[plugin_record.name] = plugin_instance
            plugin_instance.is_loaded = True

            logger.info(f"Plugin {plugin_record.name} loaded successfully")
            return plugin_instance

        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_record.name}: {e}")
            plugin_record.status = PluginStatus.ERROR.value
            plugin_record.error_message = str(e)
            db.session.add(plugin_record)
            raise

    async def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin.
        
        Args:
            plugin_name: Name of plugin to unload
            
        Returns:
            True if successful
        """
        if plugin_name not in self._plugins:
            logger.warning(f"Plugin {plugin_name} not loaded")
            return False

        try:
            plugin = self._plugins[plugin_name]

            # Call on_plugin_unload hook
            context = HookContext(
                hook_point=HookPoint.ON_PLUGIN_UNLOAD.value,
                data={'plugin_name': plugin_name}
            )
            result = await plugin.on_plugin_unload(context)

            if not result.success:
                logger.warning(f"on_plugin_unload returned error: {result.error_message}")

            # Remove from registry
            for hook_plugins in self._hook_registry.values():
                if plugin_name in hook_plugins:
                    hook_plugins.remove(plugin_name)

            del self._plugins[plugin_name]
            plugin.is_loaded = False

            # Update database
            plugin_record = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()
            if plugin_record:
                plugin_record.status = PluginStatus.INSTALLED.value
                plugin_record.disabled_at = utcnow_naive()
                db.session.add(plugin_record)
                db.session.commit()

            logger.info(f"Plugin {plugin_name} unloaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_name}: {e}")
            return False

    async def execute_hook(self, hook_point: str, context: HookContext,
                          project_id: Optional[int] = None,
                          tenant_id: Optional[int] = None) -> List[HookResult]:
        """Execute all plugins registered for a hook point.
        
        Args:
            hook_point: Hook point name (HookPoint enum value)
            context: Hook context with data
            project_id: Optional project context
            tenant_id: Optional tenant context
            
        Returns:
            List of HookResult objects from each plugin
        """
        if hook_point not in self._hook_registry:
            logger.debug(f"No plugins registered for hook {hook_point}")
            return []

        context.hook_point = hook_point
        context.project_id = project_id
        context.tenant_id = tenant_id

        results = []
        plugin_names = self._hook_registry.get(hook_point, [])

        for plugin_name in plugin_names:
            if plugin_name not in self._plugins:
                logger.warning(f"Plugin {plugin_name} not loaded, skipping hook")
                continue

            try:
                # Check if plugin is configured and enabled for this project/tenant
                if not await self._is_plugin_enabled_for_context(plugin_name, project_id, tenant_id):
                    logger.debug(f"Plugin {plugin_name} disabled for context")
                    continue

                plugin = self._plugins[plugin_name]
                hook_method = hook_point.replace('.', '_')

                if not hasattr(plugin, hook_method):
                    logger.debug(f"Plugin {plugin_name} does not implement {hook_method}")
                    continue

                # Execute hook with timeout
                start_time = time.time()
                try:
                    hook_handler = getattr(plugin, hook_method)
                    result = await asyncio.wait_for(
                        hook_handler(context),
                        timeout=30.0  # 30 second timeout per hook
                    )
                except asyncio.TimeoutError:
                    result = HookResult(
                        success=False,
                        plugin_name=plugin_name,
                        hook_point=hook_point,
                        execution_time_ms=(time.time() - start_time) * 1000,
                        status="timeout",
                        error_message="Hook execution timed out (30s)"
                    )
                except Exception as e:
                    result = HookResult(
                        success=False,
                        plugin_name=plugin_name,
                        hook_point=hook_point,
                        execution_time_ms=(time.time() - start_time) * 1000,
                        status="error",
                        error_message=str(e),
                        error_traceback=traceback.format_exc()
                    )

                result.execution_time_ms = (time.time() - start_time) * 1000

                # Log execution
                await self._log_execution(plugin_name, hook_point, context, result)

                # Update statistics
                await self._update_plugin_stats(plugin_name, result)

                results.append(result)

            except Exception as e:
                logger.error(f"Error executing hook {hook_point} on plugin {plugin_name}: {e}")

        return results

    async def _register_plugin_hooks(self, plugin_record: Plugin,
                                    plugin_instance: PluginBase) -> None:
        """Register plugin hooks in the registry.
        
        Args:
            plugin_record: Plugin database record
            plugin_instance: Plugin instance
        """
        for hook_name, hook_method in plugin_instance.hooks.items():
            hook_point = hook_name

            if hook_point not in self._hook_registry:
                self._hook_registry[hook_point] = []

            if plugin_record.name not in self._hook_registry[hook_point]:
                self._hook_registry[hook_point].append(plugin_record.name)

            # Create database record
            existing = db.session.query(PluginHookRegistration).filter(
                PluginHookRegistration.plugin_id == plugin_record.id,
                PluginHookRegistration.hook_point == hook_point,
            ).first()

            if not existing:
                registration = PluginHookRegistration(
                    plugin_id=plugin_record.id,
                    hook_point=hook_point,
                    handler_method=hook_name,
                    execution_order=100,
                    is_active=True,
                )
                db.session.add(registration)

        db.session.commit()

    async def _is_plugin_enabled_for_context(self, plugin_name: str,
                                            project_id: Optional[int] = None,
                                            tenant_id: Optional[int] = None) -> bool:
        """Check if plugin is enabled for given context.
        
        Args:
            plugin_name: Plugin name
            project_id: Optional project context
            tenant_id: Optional tenant context
            
        Returns:
            True if enabled
        """
        plugin_record = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()
        if not plugin_record or plugin_record.status != PluginStatus.ENABLED.value:
            return False

        # Check project-level configuration
        if project_id:
            config = db.session.query(PluginConfiguration).filter(
                PluginConfiguration.plugin_id == plugin_record.id,
                PluginConfiguration.project_id == project_id,
            ).first()
            if config:
                return config.is_enabled

        # Check tenant-level configuration
        if tenant_id:
            config = db.session.query(PluginConfiguration).filter(
                PluginConfiguration.plugin_id == plugin_record.id,
                PluginConfiguration.tenant_id == tenant_id,
            ).first()
            if config:
                return config.is_enabled

        # Default is enabled
        return True

    async def _log_execution(self, plugin_name: str, hook_point: str,
                            context: HookContext, result: HookResult) -> None:
        """Log plugin execution to database.
        
        Args:
            plugin_name: Plugin name
            hook_point: Hook point
            context: Hook context
            result: Hook result
        """
        try:
            plugin_record = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()
            if not plugin_record:
                return

            log_entry = PluginExecutionLog(
                plugin_id=plugin_record.id,
                project_id=context.project_id,
                tenant_id=context.tenant_id,
                hook_point=hook_point,
                handler_method=hook_point.replace('.', '_'),
                status=result.status,
                execution_time_ms=result.execution_time_ms,
                error_message=result.error_message,
                error_traceback=result.error_traceback,
                created_at=utcnow_naive(),
                created_timestamp_ms=int(time.time() * 1000),
            )

            # Store limited request/response data
            if result.data:
                import json
                try:
                    log_entry.request_data_json = json.dumps(
                        context.data,
                        default=str,
                        truncate_safe=False
                    )[:1024]  # Limit to 1KB
                except:
                    pass

            db.session.add(log_entry)
            db.session.commit()

        except Exception as e:
            logger.error(f"Failed to log plugin execution: {e}")

    async def _update_plugin_stats(self, plugin_name: str, result: HookResult) -> None:
        """Update plugin execution statistics.
        
        Args:
            plugin_name: Plugin name
            result: Hook result
        """
        try:
            plugin_record = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()
            if not plugin_record:
                return

            plugin_record.execution_count += 1
            plugin_record.last_execution_time = utcnow_naive()
            plugin_record.total_execution_time_ms += result.execution_time_ms

            if result.status == "error":
                plugin_record.error_count += 1

            db.session.add(plugin_record)
            db.session.commit()

        except Exception as e:
            logger.error(f"Failed to update plugin stats: {e}")

    def get_plugin(self, plugin_name: str) -> Optional[PluginBase]:
        """Get loaded plugin by name.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            PluginBase instance or None
        """
        return self._plugins.get(plugin_name)

    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all loaded plugins.
        
        Returns:
            List of plugin info dictionaries
        """
        return [
            {
                'name': plugin.metadata.name,
                'display_name': plugin.metadata.display_name,
                'version': plugin.metadata.version,
                'is_loaded': plugin.is_loaded,
                'hooks': list(plugin.hooks.keys()),
            }
            for plugin in self._plugins.values()
        ]

    def get_hook_registry(self) -> Dict[str, List[str]]:
        """Get hook registry.
        
        Returns:
            Dictionary of hook_point -> [plugin_names]
        """
        return self._hook_registry.copy()


# Global plugin manager instance
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get global plugin manager instance.
    
    Returns:
        Global PluginManager instance
    """
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


def set_plugin_manager(manager: PluginManager) -> None:
    """Set global plugin manager instance.
    
    Args:
        manager: PluginManager instance
    """
    global _plugin_manager
    _plugin_manager = manager
