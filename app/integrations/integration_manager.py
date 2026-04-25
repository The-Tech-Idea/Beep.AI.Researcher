"""
Integration Manager — Central registry for all external integrations.

Follows the SearchManager singleton pattern.  Manages:
  - Registration / discovery of connector classes
  - Per-project enablement with credential binding
  - Health dashboards
"""
from __future__ import annotations

import logging
from threading import Lock
from typing import Any, Dict, List, Optional, Type

from .base_connector import BaseConnector, ConnectorInfo, ConnectorType

logger = logging.getLogger(__name__)


class IntegrationManager:
    """
    Singleton registry of available integration connectors.

    Usage:
        mgr = IntegrationManager.get_instance()
        mgr.register("google_drive", GoogleDriveConnector)
        connector = mgr.create("google_drive", config={...})
        connector.connect(credentials)
    """

    _instance: Optional["IntegrationManager"] = None
    _lock = Lock()

    def __init__(self):
        self._registry: Dict[str, Type[BaseConnector]] = {}
        self._active: Dict[str, BaseConnector] = {}      # name → live instance

    @classmethod
    def get_instance(cls) -> "IntegrationManager":
        """Thread-safe singleton."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    cls._instance._auto_register()
        return cls._instance

    # ── Registration ─────────────────────────────────────────────────

    def register(self, name: str, connector_class: Type[BaseConnector]) -> bool:
        """Register a connector class by name."""
        if name in self._registry:
            logger.warning("Connector '%s' already registered — overwriting", name)
        self._registry[name] = connector_class
        logger.info("Registered integration: %s", name)
        return True

    def unregister(self, name: str) -> bool:
        """Remove a connector class."""
        if name in self._active:
            self._active[name].disconnect()
            del self._active[name]
        return self._registry.pop(name, None) is not None

    # ── Discovery ────────────────────────────────────────────────────

    def list_available(self) -> List[Dict[str, Any]]:
        """List all registered connector types with their info."""
        result = []
        for name, cls in self._registry.items():
            try:
                instance = cls()
                info = instance.info.to_dict()
                info["registered_name"] = name
                result.append(info)
            except Exception as e:
                result.append({"registered_name": name, "error": str(e)})
        return result

    def list_active(self) -> List[Dict[str, Any]]:
        """List currently active (instantiated) connectors."""
        return [c.get_status() for c in self._active.values()]

    # ── Lifecycle ────────────────────────────────────────────────────

    def create(self, name: str, config: Optional[Dict[str, Any]] = None) -> Optional[BaseConnector]:
        """Create an instance of a registered connector."""
        cls = self._registry.get(name)
        if not cls:
            logger.error("Unknown integration: %s", name)
            return None
        instance = cls(config=config)
        self._active[name] = instance
        return instance

    def get(self, name: str) -> Optional[BaseConnector]:
        """Get an active connector instance."""
        return self._active.get(name)

    def connect_integration(self, name: str, credentials: Dict[str, Any],
                             config: Optional[Dict[str, Any]] = None) -> bool:
        """Create, configure, and connect an integration in one call."""
        connector = self.create(name, config)
        if not connector:
            return False
        return connector.connect(credentials)

    def disconnect_integration(self, name: str) -> bool:
        """Disconnect and remove an active integration."""
        connector = self._active.pop(name, None)
        if connector:
            connector.disconnect()
            return True
        return False

    def get_status_dashboard(self) -> Dict[str, Any]:
        """Return health status of all active integrations."""
        return {
            "registered_count": len(self._registry),
            "active_count": len(self._active),
            "integrations": self.list_active(),
        }

    # ── Auto-registration ────────────────────────────────────────────

    def _auto_register(self):
        """Auto-detect and register built-in connectors."""
        # Search providers are already managed by SearchManager.
        # This method registers non-search connectors as they are implemented.
        # Example:
        #   from .storage.google_drive import GoogleDriveConnector
        #   self.register("google_drive", GoogleDriveConnector)
        logger.info("IntegrationManager: auto-registration complete (%d connectors)",
                     len(self._registry))


def get_integration_manager() -> IntegrationManager:
    """Convenience function."""
    return IntegrationManager.get_instance()
