"""S3StorageBackend — AWS S3 or any S3-compatible object store (MinIO, etc.).

Requires ``boto3``:  pip install boto3

Config keys consumed (Admin → Settings → Storage):
  storage_s3_endpoint_url  (blank = AWS; set for MinIO/on-prem)
  storage_s3_access_key
  storage_s3_secret_key
  storage_s3_bucket_name
  storage_s3_region
  storage_s3_prefix        (e.g. 'researcher/')
"""
from __future__ import annotations

import io
import logging
from typing import IO, Optional

from app.services.storage.base import BaseStorageBackend, StorageError

logger = logging.getLogger(__name__)


class S3StorageBackend(BaseStorageBackend):
    """Store files in an S3-compatible object store."""

    def __init__(self,
                 endpoint_url: Optional[str] = None,
                 access_key: Optional[str] = None,
                 secret_key: Optional[str] = None,
                 bucket_name: Optional[str] = None,
                 region: Optional[str] = None,
                 prefix: Optional[str] = None):
        from app.config_manager import config_manager as cm
        self._endpoint_url = endpoint_url or cm.get('storage_s3_endpoint_url') or None
        self._access_key   = access_key   or cm.get('storage_s3_access_key', '')
        self._secret_key   = secret_key   or cm.get('storage_s3_secret_key', '')
        self._bucket       = bucket_name  or cm.get('storage_s3_bucket_name', '')
        self._region       = region       or cm.get('storage_s3_region', 'us-east-1')
        self._prefix       = prefix       if prefix is not None \
                             else cm.get('storage_s3_prefix', 'researcher/')
        self._client = None   # Lazy init

    @property
    def backend_name(self) -> str:
        return 's3'

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import boto3
            kwargs: dict = dict(
                region_name=self._region,
                aws_access_key_id=self._access_key or None,
                aws_secret_access_key=self._secret_key or None,
            )
            if self._endpoint_url:
                kwargs['endpoint_url'] = self._endpoint_url
            self._client = boto3.client('s3', **kwargs)
            return self._client
        except ImportError:
            raise StorageError("S3 backend requires 'boto3': pip install boto3")
        except Exception as exc:
            raise StorageError(f'S3 client init failed: {exc}') from exc

    def _s3_key(self, key: str) -> str:
        return f'{self._prefix}{key}' if self._prefix else key

    # ── Core operations ───────────────────────────────────────────────────────

    def save(self, stream: IO[bytes], key: str) -> str:
        try:
            client = self._get_client()
            s3_key = self._s3_key(key)
            client.upload_fileobj(stream, self._bucket, s3_key)
            logger.debug('S3: uploaded %s → %s/%s', key, self._bucket, s3_key)
            return key
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f'S3 save failed for {key!r}: {exc}') from exc

    def load(self, key: str) -> bytes:
        try:
            client = self._get_client()
            s3_key = self._s3_key(key)
            buf = io.BytesIO()
            client.download_fileobj(self._bucket, s3_key, buf)
            return buf.getvalue()
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f'S3 load failed for {key!r}: {exc}') from exc

    def delete(self, key: str) -> None:
        try:
            client = self._get_client()
            s3_key = self._s3_key(key)
            client.delete_object(Bucket=self._bucket, Key=s3_key)
            logger.debug('S3: deleted %s/%s', self._bucket, s3_key)
        except StorageError:
            raise
        except Exception as exc:
            logger.warning('S3 delete failed for %r: %s', key, exc)

    def exists(self, key: str) -> bool:
        try:
            client = self._get_client()
            s3_key = self._s3_key(key)
            client.head_object(Bucket=self._bucket, Key=s3_key)
            return True
        except Exception:
            return False

    def file_size(self, key: str) -> int:
        try:
            client = self._get_client()
            s3_key = self._s3_key(key)
            resp = client.head_object(Bucket=self._bucket, Key=s3_key)
            return resp.get('ContentLength', 0)
        except Exception:
            return 0

    def send_file_response(self, key: str, filename: str,
                            mimetype: Optional[str] = None):
        """Generate a 15-minute pre-signed URL and redirect the client."""
        try:
            client = self._get_client()
            s3_key = self._s3_key(key)
            url = client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self._bucket, 'Key': s3_key},
                ExpiresIn=900,
            )
            from flask import redirect
            return redirect(url)
        except Exception as exc:
            raise StorageError(f'S3 presigned URL failed for {key!r}: {exc}') from exc
