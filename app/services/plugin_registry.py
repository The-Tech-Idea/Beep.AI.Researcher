"""Plugin registry and loader system (Phase 3.1)."""
import json
import logging
import os
from typing import Any, Dict, List, Optional, Type

from app.database import db
from app.models.researcher.plugins import Plugin, PluginRegistry, PluginStatus, PluginType
from app.services.plugin_base import PluginBase, PluginMetadata

logger = logging.getLogger(__name__)


class PluginRegistryManager:
    """Manage plugin discovery, installation, and registration.
    
    Features:
    - Auto-discover builtin plugins
    - Register plugins in database
    - Validate plugin requirements
    - Manage plugin dependencies
    - Handle plugin updates
    """

    def __init__(self):
        """Initialize registry manager."""
        self._registries: Dict[str, Any] = {}  # registry_name -> config
        self._discovered_plugins: Dict[str, Dict] = {}  # name -> plugin_info
        logger.info("PluginRegistryManager initialized")

    async def initialize(self) -> bool:
        """Initialize registry by discovering builtin plugins.
        
        Returns:
            True if successful
        """
        try:
            # Ensure builtin registry exists
            await self.register_registry(
                registry_name="builtin",
                registry_url=None,
                description="Built-in plugins"
            )

            # Auto-discover current plugins in database
            await self.discover_plugins()

            return True
        except Exception as e:
            logger.error(f"Failed to initialize PluginRegistryManager: {e}")
            return False

    async def register_registry(self, registry_name: str, registry_url: Optional[str] = None,
                               description: str = "") -> PluginRegistry:
        """Register a plugin registry.
        
        Args:
            registry_name: Name of registry
            registry_url: URL to registry (optional)
            description: Description
            
        Returns:
            PluginRegistry record
        """
        registry = db.session.query(PluginRegistry).filter(
            PluginRegistry.registry_name == registry_name
        ).first()

        if registry:
            logger.debug(f"Registry {registry_name} already exists")
            return registry

        registry = PluginRegistry(
            registry_name=registry_name,
            registry_url=registry_url,
            description=description,
            is_active=True,
        )
        db.session.add(registry)
        db.session.commit()
        logger.info(f"Registered plugin registry: {registry_name}")
        return registry

    async def discover_plugins(self) -> List[Dict[str, Any]]:
        """Discover available plugins in database.
        
        Returns:
            List of discovered plugin info
        """
        try:
            plugins = db.session.query(Plugin).all()
            self._discovered_plugins.clear()

            for plugin_record in plugins:
                plugin_info = {
                    'id': plugin_record.id,
                    'name': plugin_record.name,
                    'display_name': plugin_record.display_name,
                    'version': plugin_record.version,
                    'plugin_type': plugin_record.plugin_type,
                    'status': plugin_record.status,
                    'module_path': plugin_record.module_path,
                    'class_name': plugin_record.class_name,
                    'description': plugin_record.description,
                }
                self._discovered_plugins[plugin_record.name] = plugin_info

            logger.info(f"Discovered {len(self._discovered_plugins)} plugins")
            return list(self._discovered_plugins.values())

        except Exception as e:
            logger.error(f"Failed to discover plugins: {e}")
            return []

    async def register_plugin(self, plugin_name: str, metadata: PluginMetadata,
                             module_path: str, class_name: str,
                             plugin_type: str = PluginType.CUSTOM.value,
                             registry_name: str = "builtin") -> Plugin:
        """Register a plugin in the database.
        
        Args:
            plugin_name: Unique plugin name
            metadata: PluginMetadata object
            module_path: Python module path
            class_name: Plugin class name
            plugin_type: Plugin type (builtin | custom | external)
            registry_name: Registry to register in
            
        Returns:
            Plugin database record
        """
        # Check if already registered
        existing = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()
        if existing:
            logger.warning(f"Plugin {plugin_name} already registered, updating...")
            existing.display_name = metadata.display_name
            existing.version = metadata.version
            existing.description = metadata.description
            existing.module_path = module_path
            existing.class_name = class_name
            db.session.add(existing)
            db.session.commit()
            return existing

        # Create new plugin record
        plugin = Plugin(
            name=plugin_name,
            display_name=metadata.display_name,
            description=metadata.description,
            version=metadata.version,
            author=metadata.author,
            author_email=metadata.author_email,
            plugin_type=plugin_type,
            module_path=module_path,
            class_name=class_name,
            status=PluginStatus.INSTALLED.value,
            config_schema_json=json.dumps(metadata.config_schema) if metadata.config_schema else None,
            default_config_json=json.dumps(metadata.default_config) if metadata.default_config else None,
            dependencies_json=json.dumps(metadata.dependencies) if metadata.dependencies else None,
        )

        db.session.add(plugin)
        db.session.commit()

        logger.info(f"Registered plugin: {plugin_name} v{metadata.version}")
        return plugin

    async def unregister_plugin(self, plugin_name: str) -> bool:
        """Unregister and remove a plugin.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            True if successful
        """
        try:
            plugin = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()
            if not plugin:
                logger.warning(f"Plugin {plugin_name} not found")
                return False

            # Only allow unregistering custom plugins
            if plugin.plugin_type == PluginType.BUILTIN.value:
                logger.error(f"Cannot unregister builtin plugin {plugin_name}")
                return False

            db.session.delete(plugin)
            db.session.commit()

            if plugin_name in self._discovered_plugins:
                del self._discovered_plugins[plugin_name]

            logger.info(f"Unregistered plugin: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to unregister plugin {plugin_name}: {e}")
            return False

    async def get_plugin_info(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get plugin information.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            Plugin info dictionary or None
        """
        plugin = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()
        if not plugin:
            return None

        return plugin.to_dict(include_config=True)

    async def list_plugins(self, plugin_type: Optional[str] = None,
                          status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List plugins with optional filtering.
        
        Args:
            plugin_type: Filter by plugin type
            status: Filter by status
            
        Returns:
            List of plugin info dictionaries
        """
        query = db.session.query(Plugin)

        if plugin_type:
            query = query.filter(Plugin.plugin_type == plugin_type)

        if status:
            query = query.filter(Plugin.status == status)

        plugins = query.all()
        return [plugin.to_dict(include_config=False) for plugin in plugins]

    async def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a plugin.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            True if successful
        """
        try:
            plugin = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()
            if not plugin:
                logger.error(f"Plugin {plugin_name} not found")
                return False

            plugin.status = PluginStatus.ENABLED.value
            plugin.enabled_at = db.func.now()
            db.session.add(plugin)
            db.session.commit()

            logger.info(f"Enabled plugin: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to enable plugin {plugin_name}: {e}")
            return False

    async def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a plugin.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            True if successful
        """
        try:
            plugin = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()
            if not plugin:
                logger.error(f"Plugin {plugin_name} not found")
                return False

            plugin.status = PluginStatus.DISABLED.value
            plugin.disabled_at = db.func.now()
            db.session.add(plugin)
            db.session.commit()

            logger.info(f"Disabled plugin: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to disable plugin {plugin_name}: {e}")
            return False

    async def validate_plugin_dependencies(self, plugin_name: str) -> Dict[str, Any]:
        """Validate plugin dependencies are met.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            Validation result with status and details
        """
        plugin = db.session.query(Plugin).filter(Plugin.name == plugin_name).first()
        if not plugin:
            return {'valid': False, 'error': f"Plugin {plugin_name} not found"}

        if not plugin.dependencies_json:
            return {'valid': True, 'dependencies': []}

        try:
            dependencies = json.loads(plugin.dependencies_json)
            missing = []

            for dep_name in dependencies:
                dep_plugin = db.session.query(Plugin).filter(
                    Plugin.name == dep_name,
                    Plugin.status == PluginStatus.ENABLED.value
                ).first()
                if not dep_plugin:
                    missing.append(dep_name)

            if missing:
                return {'valid': False, 'missing_dependencies': missing}

            return {'valid': True, 'dependencies': dependencies}

        except Exception as e:
            return {'valid': False, 'error': str(e)}

    def get_discovered_plugins(self) -> Dict[str, Dict]:
        """Get all discovered plugins from cache.
        
        Returns:
            Dictionary of discovered plugins
        """
        return self._discovered_plugins.copy()


# Global registry manager instance
_registry_manager: Optional[PluginRegistryManager] = None


def get_plugin_registry() -> PluginRegistryManager:
    """Get global plugin registry manager.
    
    Returns:
        Global PluginRegistryManager instance
    """
    global _registry_manager
    if _registry_manager is None:
        _registry_manager = PluginRegistryManager()
    return _registry_manager


def set_plugin_registry(registry: PluginRegistryManager) -> None:
    """Set global plugin registry manager.
    
    Args:
        registry: PluginRegistryManager instance
    """
    global _registry_manager
    _registry_manager = registry
