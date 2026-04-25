"""
Base Storage Provider — Abstract interface for cloud/file storage integrations.

Storage providers import documents from external file stores into projects.
"""
from __future__ import annotations

import logging
from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..base_connector import BaseConnector, ConnectorInfo, ConnectorType, SyncResult

logger = logging.getLogger(__name__)


@dataclass
class StorageFile:
    """Represents a file in an external storage system."""
    id: str
    name: str
    mime_type: str = ""
    size_bytes: int = 0
    modified_at: Optional[str] = None
    path: str = ""                     # folder path within the storage
    download_url: Optional[str] = None
    is_folder: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "modified_at": self.modified_at,
            "path": self.path,
            "is_folder": self.is_folder,
        }


class BaseStorageProvider(BaseConnector):
    """
    Abstract base for storage integrations.

    Subclasses must implement:
      - info, _do_connect, _do_disconnect, _do_test  (from BaseConnector)
      - list_files(folder_path)  → List[StorageFile]
      - download_file(file_id)   → bytes
    """

    @abstractmethod
    def list_files(self, folder_path: str = "/",
                   page_token: Optional[str] = None,
                   limit: int = 50) -> tuple[List[StorageFile], Optional[str]]:
        """
        List files in a folder.

        Returns: (files, next_page_token)
        """
        ...

    @abstractmethod
    def download_file(self, file_id: str) -> Optional[bytes]:
        """Download file content by ID. Returns raw bytes or None."""
        ...

    def search_files(self, query: str, limit: int = 20) -> List[StorageFile]:
        """Search for files by name/content. Override for providers that support search."""
        return []

    def get_file_metadata(self, file_id: str) -> Optional[StorageFile]:
        """Get metadata for a single file. Override if supported."""
        return None
