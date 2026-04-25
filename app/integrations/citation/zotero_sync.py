"""
Zotero Sync — Two-way synchronization with Zotero Web API v3.

Supports:
  - List user/group libraries and collections
  - Incremental pull using If-Modified-Since-Version
  - Push items from project references → Zotero
  - Import PDF attachments
"""
from __future__ import annotations

import logging
import re
from urllib.parse import unquote
from typing import Any, Dict, List, Optional

import requests

from ..base_connector import ConnectorInfo, ConnectorType, SyncResult
from .base_citation import BaseCitationProvider, CitationItem

logger = logging.getLogger(__name__)


class ZoteroSyncProvider(BaseCitationProvider):
    """
    Zotero Web API v3 connector.

    Credentials dict: {
        "api_key": "...",           # Zotero API key (from zotero.org/settings/keys)
        "user_id": "12345",         # Zotero user ID
        "library_type": "user",     # "user" or "group"
        "group_id": "..."           # only if library_type == "group"
    }
    """

    BASE_URL = "https://api.zotero.org"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config=config, max_retries=3, retry_base_delay=1.0)
        self._api_key: Optional[str] = None
        self._user_id: Optional[str] = None
        self._library_type: str = "user"
        self._group_id: Optional[str] = None
        self._last_version: Optional[int] = None

    @property
    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="zotero",
            display_name="Zotero",
            connector_type=ConnectorType.CITATION,
            description="Sync references with your Zotero library",
            requires_auth=True,
            docs_url="https://www.zotero.org/support/dev/web_api/v3/start",
            config_schema={
                "api_key": {"type": "string", "required": True, "secret": True},
                "user_id": {"type": "string", "required": True},
                "library_type": {"type": "string", "default": "user"},
            },
        )

    @property
    def _library_prefix(self) -> str:
        if self._library_type == "group" and self._group_id:
            return f"/groups/{self._group_id}"
        return f"/users/{self._user_id}"

    def _headers(self, version: Optional[int] = None) -> Dict[str, str]:
        h = {
            "Zotero-API-Key": self._api_key or "",
            "Zotero-API-Version": "3",
        }
        if version is not None:
            h["If-Modified-Since-Version"] = str(version)
        return h

    def _build_item_url(self, item_key: str) -> str:
        return f"https://www.zotero.org{self._library_prefix}/items/{item_key}"

    # ── Connection lifecycle ─────────────────────────────────────────

    def _do_connect(self, credentials: Dict[str, Any]) -> bool:
        self._api_key = credentials.get("api_key")
        self._user_id = credentials.get("user_id")
        self._library_type = credentials.get("library_type", "user")
        self._group_id = credentials.get("group_id")

        if not self._api_key or not self._user_id:
            raise ValueError("api_key and user_id are required")
        return True

    def _do_disconnect(self) -> None:
        self._api_key = None

    def _do_test(self) -> bool:
        try:
            r = requests.get(
                f"{self.BASE_URL}{self._library_prefix}/items/top",
                headers=self._headers(),
                params={"limit": 1, "format": "json"},
                timeout=15,
            )
            return r.status_code == 200
        except Exception:
            return False

    # ── Citation operations ──────────────────────────────────────────

    def list_collections(self) -> List[Dict[str, Any]]:
        """Fetch all collections from the Zotero library."""
        try:
            r = requests.get(
                f"{self.BASE_URL}{self._library_prefix}/collections",
                headers=self._headers(),
                params={"format": "json", "limit": 100},
                timeout=15,
            )
            r.raise_for_status()
            collections = []
            for item in r.json():
                data = item.get("data", {})
                collections.append({
                    "key": data.get("key"),
                    "name": data.get("name"),
                    "parent": data.get("parentCollection", False),
                    "item_count": item.get("meta", {}).get("numItems", 0),
                })
            return collections
        except Exception as e:
            logger.error("Zotero list_collections error: %s", e)
            return []

    def list_items(self, collection_id: Optional[str] = None,
                   since_version: Optional[int] = None,
                   limit: int = 100) -> tuple[List[CitationItem], Optional[int]]:
        """
        Fetch items from Zotero, optionally filtered by collection.

        Uses If-Modified-Since-Version for incremental sync.
        """
        try:
            if collection_id:
                url = f"{self.BASE_URL}{self._library_prefix}/collections/{collection_id}/items/top"
            else:
                url = f"{self.BASE_URL}{self._library_prefix}/items/top"

            r = requests.get(
                url,
                headers=self._headers(version=since_version),
                params={"format": "json", "limit": min(limit, 100), "sort": "dateModified"},
                timeout=30,
            )

            # 304 Not Modified → nothing changed
            if r.status_code == 304:
                return [], since_version

            r.raise_for_status()

            # Track library version for next incremental call
            current_version = int(r.headers.get("Last-Modified-Version", 0))
            self._last_version = current_version

            items = []
            for entry in r.json():
                item = self._parse_item(entry)
                if item:
                    items.append(item)

            return items, current_version

        except Exception as e:
            logger.error("Zotero list_items error: %s", e)
            return [], since_version

    def list_item_attachments(self, item_id: str) -> List[Dict[str, Any]]:
        """Fetch attachment metadata for one Zotero item."""
        try:
            response = requests.get(
                f"{self.BASE_URL}{self._library_prefix}/items/{item_id}/children",
                headers=self._headers(),
                params={"format": "json", "limit": 100},
                timeout=30,
            )
            response.raise_for_status()

            attachments: List[Dict[str, Any]] = []
            for entry in response.json():
                data = entry.get("data", {})
                if data.get("itemType") != "attachment":
                    continue

                item_key = str(data.get("key") or "").strip()
                attachments.append({
                    "item_key": item_key,
                    "title": data.get("title") or data.get("filename") or "Attachment",
                    "filename": data.get("filename") or "",
                    "content_type": data.get("contentType") or "",
                    "link_mode": data.get("linkMode") or "",
                    "url": data.get("url") or "",
                    "item_url": self._build_item_url(item_key) if item_key else "",
                    "date_modified": data.get("dateModified"),
                })

            return attachments
        except Exception as e:
            logger.error("Zotero list_item_attachments error: %s", e)
            raise

    def download_attachment(self, item_id: str) -> Dict[str, Any]:
        """Download one attachment file from Zotero."""
        try:
            response = requests.get(
                f"{self.BASE_URL}{self._library_prefix}/items/{item_id}/file",
                headers=self._headers(),
                timeout=60,
                allow_redirects=True,
            )
            response.raise_for_status()
        except Exception as e:
            logger.error("Zotero download_attachment error: %s", e)
            raise

        content = response.content or b""
        if not content:
            raise ValueError("The requested Zotero attachment did not return any file content.")

        return {
            "content": content,
            "content_type": _normalize_content_type(response.headers.get("Content-Type")),
            "filename": _extract_filename(
                response.headers.get("Content-Disposition"),
                fallback=f"{item_id}",
            ),
            "download_url": response.url,
        }

    def push_items(self, items: List[CitationItem]) -> SyncResult:
        """Create items in the Zotero library."""
        if not items:
            return SyncResult(success=True, items_synced=0)

        try:
            zotero_items = [self._to_zotero_item(item) for item in items]

            r = requests.post(
                f"{self.BASE_URL}{self._library_prefix}/items",
                headers={**self._headers(), "Content-Type": "application/json"},
                json=zotero_items,
                timeout=30,
            )
            r.raise_for_status()
            result = r.json()

            success_count = len(result.get("successful", {}))
            failed = result.get("failed", {})

            return SyncResult(
                success=success_count > 0,
                items_synced=success_count,
                items_failed=len(failed),
                errors=[str(v) for v in failed.values()],
            )

        except Exception as e:
            logger.error("Zotero push error: %s", e)
            return SyncResult(success=False, errors=[str(e)])

    def _do_sync(self, since=None) -> SyncResult:
        """Incremental sync using version tracking."""
        version = None
        if hasattr(self, '_last_version') and self._last_version:
            version = self._last_version

        items, new_version = self.list_items(since_version=version)
        self._last_version = new_version

        return SyncResult(
            success=True,
            items_synced=len(items),
        )

    # ── Parsing ──────────────────────────────────────────────────────

    def _parse_item(self, entry: Dict) -> Optional[CitationItem]:
        """Parse a Zotero API item into a CitationItem."""
        try:
            data = entry.get("data", {})
            item_type = data.get("itemType", "")

            # Skip non-reference types
            if item_type in ("attachment", "note", "annotation"):
                return None

            # Authors
            authors = []
            for creator in data.get("creators", []):
                first = creator.get("firstName", "")
                last = creator.get("lastName", "")
                name = creator.get("name", "") or f"{first} {last}".strip()
                if name:
                    authors.append(name)

            # Tags
            tags = [t.get("tag", "") for t in data.get("tags", []) if t.get("tag")]

            return CitationItem(
                id=data.get("key", ""),
                title=data.get("title", "Untitled"),
                authors=authors,
                year=data.get("date", "")[:4] if data.get("date") else None,
                doi=data.get("DOI"),
                item_type=item_type,
                journal=data.get("publicationTitle", ""),
                volume=data.get("volume", ""),
                issue=data.get("issue", ""),
                pages=data.get("pages", ""),
                abstract=data.get("abstractNote", ""),
                url=data.get("url", ""),
                tags=tags,
                collections=data.get("collections", []),
                metadata={
                    "zotero_key": data.get("key"),
                    "zotero_version": entry.get("version"),
                    "date_added": data.get("dateAdded"),
                    "date_modified": data.get("dateModified"),
                },
            )
        except Exception:
            return None

    @staticmethod
    def _to_zotero_item(item: CitationItem) -> Dict[str, Any]:
        """Convert a CitationItem to Zotero API write format."""
        # Map internal types to Zotero types
        type_map = {
            "article": "journalArticle",
            "book": "book",
            "chapter": "bookSection",
            "conference": "conferencePaper",
            "thesis": "thesis",
            "report": "report",
        }
        zotero_type = type_map.get(item.item_type, "journalArticle")

        creators = []
        for author in item.authors:
            parts = author.rsplit(" ", 1)
            if len(parts) == 2:
                creators.append({"creatorType": "author", "firstName": parts[0], "lastName": parts[1]})
            else:
                creators.append({"creatorType": "author", "name": author})

        return {
            "itemType": zotero_type,
            "title": item.title,
            "creators": creators,
            "date": item.year or "",
            "DOI": item.doi or "",
            "publicationTitle": item.journal,
            "volume": item.volume,
            "issue": item.issue,
            "pages": item.pages,
            "abstractNote": item.abstract,
            "url": item.url,
            "tags": [{"tag": t} for t in item.tags],
        }


def _normalize_content_type(value: Optional[str]) -> str:
    content_type = (value or "").split(";", 1)[0].strip()
    return content_type or "application/octet-stream"


def _extract_filename(content_disposition: Optional[str], *, fallback: str) -> str:
    header = content_disposition or ""
    encoded_match = re.search(r"filename\*=UTF-8''([^;]+)", header, flags=re.IGNORECASE)
    if encoded_match:
        return unquote(encoded_match.group(1))

    quoted_match = re.search(r'filename="([^"]+)"', header, flags=re.IGNORECASE)
    if quoted_match:
        return quoted_match.group(1)

    plain_match = re.search(r"filename=([^;]+)", header, flags=re.IGNORECASE)
    if plain_match:
        return plain_match.group(1).strip().strip('"')

    return fallback
