"""
App Integrations Package

Contains integrations with external services and APIs.
"""

from . import search

# Phase 1 — Foundation infrastructure
from .base_connector import BaseConnector, ConnectorInfo, ConnectorType, ConnectorStatus, SyncResult
from .credential_vault import CredentialVault, get_vault
from .integration_manager import IntegrationManager, get_integration_manager
from .event_bridge import EventBridge, EventType, get_event_bridge
from .sync_engine import SyncEngine, get_sync_engine

__all__ = [
    'search',
    'BaseConnector', 'ConnectorInfo', 'ConnectorType', 'ConnectorStatus', 'SyncResult',
    'CredentialVault', 'get_vault',
    'IntegrationManager', 'get_integration_manager',
    'EventBridge', 'EventType', 'get_event_bridge',
    'SyncEngine', 'get_sync_engine',
]
