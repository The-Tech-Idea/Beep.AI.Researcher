"""Zotero provider connection helpers."""
from __future__ import annotations

from typing import Any

from app.integrations.citation.zotero_sync import ZoteroSyncProvider


def build_zotero_provider(connection: dict[str, Any]) -> ZoteroSyncProvider:
    """Build and validate a Zotero provider from a resolved user connection."""
    extra_data = connection["extra_data"]
    credentials = {
        "api_key": connection["api_key"],
        "user_id": str(extra_data.get("user_id") or "").strip(),
        "library_type": str(extra_data.get("library_type") or "user").strip() or "user",
        "group_id": str(extra_data.get("group_id") or "").strip() or None,
    }
    if not credentials["user_id"]:
        raise ValueError("Zotero user ID is required before this library can sync.")
    if credentials["library_type"] == "group" and not credentials["group_id"]:
        raise ValueError("Zotero group ID is required when using a group library.")

    provider = ZoteroSyncProvider()
    if not provider.connect(credentials):
        raise ValueError("Could not connect to Zotero with the saved credentials.")
    return provider
