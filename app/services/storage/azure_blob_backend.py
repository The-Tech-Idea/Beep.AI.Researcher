"""AzureBlobStorageBackend — store files in Azure Blob Storage.

Requires ``azure-storage-blob``:  pip install azure-storage-blob

Config keys consumed (Admin → Settings → Storage):
  storage_azure_connection_string
  storage_azure_container_name    (default: 'researcher')
  storage_azure_prefix            (default: 'uploads/')
"""
from __future__ import annotations

import io
import logging
from typing import IO, Optional

from app.services.storage.base import BaseStorageBackend, StorageError

logger = logging.getLogger(__name__)


class AzureBlobStorageBackend(BaseStorageBackend):
    """Store files in Azure Blob Storage."""

    def __init__(self,
                 connection_string: Optional[str] = None,
                 container_name: Optional[str] = None,
                 prefix: Optional[str] = None):
        from app.config_manager import config_manager as cm
        self._connection_string = (
            connection_string
            or cm.get('storage_azure_connection_string', '')
        )
        self._container = (
            container_name
            or cm.get('storage_azure_container_name', 'researcher')
        )
        self._prefix = (
            prefix if prefix is not None
            else cm.get('storage_azure_prefix', 'uploads/')
        )
        self._client = None   # Lazy init

    @property
    def backend_name(self) -> str:
        return 'azure_blob'

    def _get_service_client(self):
        if self._client is not None:
            return self._client
        try:
            from azure.storage.blob import BlobServiceClient
            if not self._connection_string:
                raise StorageError('storage_azure_connection_string is not configured')
            self._client = BlobServiceClient.from_connection_string(
                self._connection_string
            )
            # Ensure container exists
            container_client = self._client.get_container_client(self._container)
            try:
                container_client.create_container()
            except Exception:
                pass   # Container already exists
            return self._client
        except StorageError:
            raise
        except ImportError:
            raise StorageError(
                "Azure Blob backend requires 'azure-storage-blob': "
                "pip install azure-storage-blob"
            )
        except Exception as exc:
            raise StorageError(f'Azure Blob client init failed: {exc}') from exc

    def _blob_name(self, key: str) -> str:
        return f'{self._prefix}{key}' if self._prefix else key

    def _blob_client(self, key: str):
        svc = self._get_service_client()
        return svc.get_blob_client(
            container=self._container,
            blob=self._blob_name(key),
        )

    # ── Core operations ───────────────────────────────────────────────────────

    def save(self, stream: IO[bytes], key: str) -> str:
        try:
            blob_client = self._blob_client(key)
            blob_client.upload_blob(stream, overwrite=True)
            logger.debug('AzureBlob: uploaded %s → %s/%s',
                         key, self._container, self._blob_name(key))
            return key
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f'Azure Blob save failed for {key!r}: {exc}') from exc

    def load(self, key: str) -> bytes:
        try:
            blob_client = self._blob_client(key)
            downloader = blob_client.download_blob()
            return downloader.readall()
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f'Azure Blob load failed for {key!r}: {exc}') from exc

    def delete(self, key: str) -> None:
        try:
            blob_client = self._blob_client(key)
            blob_client.delete_blob(delete_snapshots='include')
            logger.debug('AzureBlob: deleted %s/%s', self._container, self._blob_name(key))
        except StorageError:
            raise
        except Exception as exc:
            logger.warning('AzureBlob delete failed for %r: %s', key, exc)

    def exists(self, key: str) -> bool:
        try:
            blob_client = self._blob_client(key)
            return blob_client.exists()
        except Exception:
            return False

    def file_size(self, key: str) -> int:
        try:
            blob_client = self._blob_client(key)
            props = blob_client.get_blob_properties()
            return props.size or 0
        except Exception:
            return 0

    def send_file_response(self, key: str, filename: str,
                            mimetype: Optional[str] = None):
        """Generate a 15-minute SAS token URL and redirect the client."""
        try:
            from datetime import datetime, timedelta, timezone
            from azure.storage.blob import (
                generate_blob_sas, BlobSasPermissions, BlobServiceClient,
            )
            svc = self._get_service_client()
            account_name = svc.account_name
            account_key = svc.credential.account_key
            blob_name = self._blob_name(key)
            expiry = datetime.now(timezone.utc) + timedelta(minutes=15)
            sas = generate_blob_sas(
                account_name=account_name,
                container_name=self._container,
                blob_name=blob_name,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                expiry=expiry,
            )
            url = (
                f'https://{account_name}.blob.core.windows.net/'
                f'{self._container}/{blob_name}?{sas}'
            )
            from flask import redirect
            return redirect(url)
        except Exception as exc:
            raise StorageError(
                f'Azure Blob SAS URL failed for {key!r}: {exc}'
            ) from exc
