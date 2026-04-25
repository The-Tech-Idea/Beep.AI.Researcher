"""
Sync Engine — Incremental synchronization with external services.

Tracks last-sync timestamps per integration per project and fetches
only changed items since the last successful sync.
"""
from __future__ import annotations

import logging
from datetime import datetime
from app.core.time_utils import utcnow_naive
from typing import Any, Dict, List, Optional

from .base_connector import BaseConnector, SyncResult

logger = logging.getLogger(__name__)


class SyncRecord:
    """Tracks sync state for one integration + project pair."""

    def __init__(self, integration_name: str, project_id: int):
        self.integration_name = integration_name
        self.project_id = project_id
        self.last_sync_at: Optional[datetime] = None
        self.last_cursor: Optional[str] = None
        self.last_status: str = "idle"          # idle, syncing, success, error
        self.last_error: Optional[str] = None
        self.total_synced: int = 0
        self.history: List[Dict[str, Any]] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "integration_name": self.integration_name,
            "project_id": self.project_id,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "last_cursor": self.last_cursor,
            "last_status": self.last_status,
            "last_error": self.last_error,
            "total_synced": self.total_synced,
        }


class SyncEngine:
    """
    Manages incremental sync across all integrations.

    Usage:
        engine = get_sync_engine()
        result = engine.sync("zotero", project_id=1, connector=zotero_connector)
    """

    _instance: Optional["SyncEngine"] = None

    def __init__(self):
        # Key: (integration_name, project_id) → SyncRecord
        self._records: Dict[tuple, SyncRecord] = {}

    @classmethod
    def get_instance(cls) -> "SyncEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _key(self, name: str, project_id: int) -> tuple:
        return (name, project_id)

    def _get_record(self, name: str, project_id: int) -> SyncRecord:
        key = self._key(name, project_id)
        if key not in self._records:
            self._records[key] = SyncRecord(name, project_id)
        return self._records[key]

    def sync(self, integration_name: str, project_id: int,
             connector: BaseConnector) -> SyncResult:
        """
        Run incremental sync for an integration + project.

        Uses the last_sync_at timestamp for incremental fetching.
        """
        record = self._get_record(integration_name, project_id)
        record.last_status = "syncing"

        try:
            result = connector.sync(since=record.last_sync_at)

            if result.success:
                record.last_sync_at = result.synced_at
                record.last_cursor = result.next_cursor
                record.last_status = "success"
                record.last_error = None
                record.total_synced += result.items_synced
            else:
                record.last_status = "error"
                record.last_error = "; ".join(result.errors) if result.errors else "Unknown error"

            record.history.append({
                "at": utcnow_naive().isoformat(),
                "success": result.success,
                "items": result.items_synced,
                "errors": result.errors,
            })
            # Keep last 50 entries
            record.history = record.history[-50:]

            return result

        except Exception as e:
            record.last_status = "error"
            record.last_error = str(e)
            logger.error("Sync error for %s (project %d): %s", integration_name, project_id, e)
            return SyncResult(success=False, errors=[str(e)])

    def get_status(self, integration_name: str, project_id: int) -> Dict[str, Any]:
        """Get sync status for a specific integration + project."""
        return self._get_record(integration_name, project_id).to_dict()

    def get_all_status(self, project_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all sync statuses, optionally filtered by project."""
        records = self._records.values()
        if project_id is not None:
            records = [r for r in records if r.project_id == project_id]
        return [r.to_dict() for r in records]

    def reset(self, integration_name: str, project_id: int) -> None:
        """Reset sync state — forces full re-sync on next run."""
        key = self._key(integration_name, project_id)
        if key in self._records:
            del self._records[key]


def get_sync_engine() -> SyncEngine:
    """Convenience function."""
    return SyncEngine.get_instance()
