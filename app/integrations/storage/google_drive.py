"""
Google Drive Storage Provider — Import documents from Google Drive.

Requires google-api-python-client and google-auth-oauthlib.
This is a scaffold — OAuth flow requires a client_secret.json from
Google Cloud Console with Drive API enabled.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ..base_connector import ConnectorInfo, ConnectorType, SyncResult
from .base_storage import BaseStorageProvider, StorageFile

logger = logging.getLogger(__name__)

# Lazy imports — only load Google libs when actually used
_GOOGLE_AVAILABLE = False
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import io
    _GOOGLE_AVAILABLE = True
except ImportError:
    pass


class GoogleDriveProvider(BaseStorageProvider):
    """
    Google Drive integration for importing research documents.

    Setup:
    1. Create OAuth 2.0 credentials in Google Cloud Console
    2. Enable Drive API
    3. Store client_id + client_secret as integration credentials
    4. User authenticates via OAuth flow → refresh token stored in vault

    Credentials dict: {
        "client_id": "...",
        "client_secret": "...",
        "refresh_token": "...",
        "token": "..."  (optional, auto-refreshed)
    }
    """

    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config=config)
        self._service = None
        self._credentials = None

    @property
    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="google_drive",
            display_name="Google Drive",
            connector_type=ConnectorType.STORAGE,
            description="Import documents from Google Drive",
            requires_auth=True,
            config_schema={
                "client_id": {"type": "string", "required": True},
                "client_secret": {"type": "string", "required": True, "secret": True},
                "refresh_token": {"type": "string", "required": True, "secret": True},
            },
        )

    def _do_connect(self, credentials: Dict[str, Any]) -> bool:
        if not _GOOGLE_AVAILABLE:
            raise ImportError(
                "google-api-python-client and google-auth-oauthlib required. "
                "Install: pip install google-api-python-client google-auth-oauthlib"
            )

        self._credentials = Credentials(
            token=credentials.get("token"),
            refresh_token=credentials.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=credentials.get("client_id"),
            client_secret=credentials.get("client_secret"),
            scopes=self.SCOPES,
        )
        self._service = build("drive", "v3", credentials=self._credentials)
        return True

    def _do_disconnect(self) -> None:
        self._service = None
        self._credentials = None

    def _do_test(self) -> bool:
        if not self._service:
            return False
        try:
            self._service.about().get(fields="user").execute()
            return True
        except Exception:
            return False

    def list_files(self, folder_path: str = "/",
                   page_token: Optional[str] = None,
                   limit: int = 50) -> tuple[List[StorageFile], Optional[str]]:
        """List files in a Google Drive folder."""
        if not self._service:
            return [], None

        try:
            # Build query
            query_parts = ["trashed = false"]
            if folder_path and folder_path != "/":
                query_parts.append(f"'{folder_path}' in parents")

            # Only show supported file types
            mime_types = [
                "application/pdf",
                "application/vnd.google-apps.document",
                "text/plain",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ]
            mime_filter = " or ".join(f"mimeType='{m}'" for m in mime_types)
            query_parts.append(f"({mime_filter} or mimeType='application/vnd.google-apps.folder')")

            params = {
                "q": " and ".join(query_parts),
                "pageSize": min(limit, 100),
                "fields": "nextPageToken, files(id, name, mimeType, size, modifiedTime, parents)",
                "orderBy": "modifiedTime desc",
            }
            if page_token:
                params["pageToken"] = page_token

            result = self._service.files().list(**params).execute()
            files = []
            for f in result.get("files", []):
                files.append(StorageFile(
                    id=f["id"],
                    name=f["name"],
                    mime_type=f.get("mimeType", ""),
                    size_bytes=int(f.get("size", 0)),
                    modified_at=f.get("modifiedTime"),
                    is_folder=f.get("mimeType") == "application/vnd.google-apps.folder",
                ))

            return files, result.get("nextPageToken")

        except Exception as e:
            logger.error("Google Drive list_files error: %s", e)
            return [], None

    def download_file(self, file_id: str) -> Optional[bytes]:
        """Download a file from Google Drive."""
        if not self._service:
            return None

        try:
            # Check if it's a Google Docs file → export as PDF
            file_meta = self._service.files().get(
                fileId=file_id, fields="mimeType"
            ).execute()
            mime = file_meta.get("mimeType", "")

            if mime.startswith("application/vnd.google-apps."):
                # Export Google Docs/Sheets as PDF
                request = self._service.files().export_media(
                    fileId=file_id, mimeType="application/pdf"
                )
            else:
                request = self._service.files().get_media(fileId=file_id)

            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            return buffer.getvalue()

        except Exception as e:
            logger.error("Google Drive download error: %s", e)
            return None

    def search_files(self, query: str, limit: int = 20) -> List[StorageFile]:
        """Search Google Drive for files matching query."""
        if not self._service:
            return []

        try:
            result = self._service.files().list(
                q=f"fullText contains '{query}' and trashed = false",
                pageSize=min(limit, 50),
                fields="files(id, name, mimeType, size, modifiedTime)",
            ).execute()

            return [
                StorageFile(
                    id=f["id"],
                    name=f["name"],
                    mime_type=f.get("mimeType", ""),
                    size_bytes=int(f.get("size", 0)),
                    modified_at=f.get("modifiedTime"),
                )
                for f in result.get("files", [])
            ]
        except Exception as e:
            logger.error("Google Drive search error: %s", e)
            return []
