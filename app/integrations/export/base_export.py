"""
Base Export Provider — Abstract interface for exporting research data.
"""
from __future__ import annotations

import logging
from abc import abstractmethod
from typing import Any, Dict, List, Optional

from ..base_connector import BaseConnector, ConnectorInfo, ConnectorType

logger = logging.getLogger(__name__)


class BaseExportProvider(BaseConnector):
    """
    Abstract base for export integrations.

    Subclasses must implement:
      - info, _do_connect, _do_disconnect, _do_test  (from BaseConnector)
      - export_report(project_data)   → str/bytes
      - export_references(references) → str/bytes
    """

    @abstractmethod
    def export_report(self, project_data: Dict[str, Any]) -> str:
        """
        Export project report content.

        Args:
            project_data: dict with 'title', 'content', 'references', 'codes', etc.

        Returns:
            Formatted string content (LaTeX, Markdown, etc.)
        """
        ...

    @abstractmethod
    def export_references(self, references: List[Dict[str, Any]],
                          style: str = "apa") -> str:
        """
        Export a list of references in the target format.

        Args:
            references: List of reference dicts
            style: Citation style (apa, mla, chicago, bibtex)

        Returns:
            Formatted reference string
        """
        ...

    def get_file_extension(self) -> str:
        """Return the file extension for this export format."""
        return ".txt"

    def get_mime_type(self) -> str:
        """Return MIME type for this export format."""
        return "text/plain"
