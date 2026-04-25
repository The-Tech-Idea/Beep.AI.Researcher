"""
Base Citation Provider — Abstract interface for citation manager sync.

Citation providers synchronize reference libraries between the app and
external citation managers (Zotero, Mendeley, etc.).
"""
from __future__ import annotations

import logging
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..base_connector import BaseConnector, ConnectorInfo, ConnectorType, SyncResult

logger = logging.getLogger(__name__)


@dataclass
class CitationItem:
    """Normalized citation/reference item from any citation manager."""
    id: str
    title: str
    authors: List[str] = field(default_factory=list)
    year: Optional[str] = None
    doi: Optional[str] = None
    item_type: str = "article"           # article, book, chapter, etc.
    journal: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    abstract: str = ""
    url: str = ""
    tags: List[str] = field(default_factory=list)
    collections: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    pdf_urls: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "doi": self.doi,
            "item_type": self.item_type,
            "journal": self.journal,
            "tags": self.tags,
            "url": self.url,
        }


class BaseCitationProvider(BaseConnector):
    """
    Abstract base for citation manager integrations.

    Subclasses must implement:
      - info, _do_connect, _do_disconnect, _do_test  (from BaseConnector)
      - list_items(collection)  → List[CitationItem]
      - list_collections()      → List[dict]
      - push_items(items)       → SyncResult
    """

    @abstractmethod
    def list_items(self, collection_id: Optional[str] = None,
                   since_version: Optional[int] = None,
                   limit: int = 100) -> tuple[List[CitationItem], Optional[int]]:
        """
        List citations from the external library.

        Args:
            collection_id: Specific collection/folder to fetch
            since_version: For incremental sync — only items changed since this version
            limit: Max items

        Returns:
            (items, current_version_number)
        """
        ...

    @abstractmethod
    def list_collections(self) -> List[Dict[str, Any]]:
        """List folders/collections in the external library."""
        ...

    @abstractmethod
    def push_items(self, items: List[CitationItem]) -> SyncResult:
        """Push (create/update) citations to the external library."""
        ...
