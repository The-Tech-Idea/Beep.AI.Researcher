"""Storage service package — multi-backend file storage abstraction.

Usage
-----
::

    from app.services.storage import get_storage_backend, StorageError

    backend = get_storage_backend()
    key = backend.save(file_stream, 'project_42/report.pdf')
    data = backend.load(key)
    backend.delete(key)
    exists = backend.exists(key)
    response = backend.send_file_response(key, 'report.pdf', 'application/pdf')

The active backend is determined by ``config_manager.get('storage_backend')``:

  ============  =============================================
  Value         Backend class
  ============  =============================================
  ``local``     :class:`~local_backend.LocalStorageBackend`
  ``smb``       :class:`~smb_backend.SMBStorageBackend`
  ``s3``        :class:`~s3_backend.S3StorageBackend`
  ``azure_blob``:class:`~azure_blob_backend.AzureBlobStorageBackend`
  ============  =============================================

The backend singleton is created once per process and cached.  Call
:func:`reset_backend` after changing ``storage_backend`` in settings so the
next call to :func:`get_storage_backend` picks up the new backend.
"""
from __future__ import annotations

import threading
from typing import Optional

from app.services.storage.base import BaseStorageBackend, StorageError

__all__ = [
    'BaseStorageBackend',
    'StorageError',
    'get_storage_backend',
    'reset_backend',
]

_lock: threading.Lock = threading.Lock()
_backend_instance: Optional[BaseStorageBackend] = None
_backend_name_cached: Optional[str] = None


def get_storage_backend() -> BaseStorageBackend:
    """Return the active storage backend singleton.

    Creates the backend on first call (or after :func:`reset_backend`).
    Thread-safe.
    """
    global _backend_instance, _backend_name_cached

    from app.config_manager import config_manager
    backend_name = config_manager.get('storage_backend', 'local')

    # Fast path — already initialised with the same backend
    if _backend_instance is not None and _backend_name_cached == backend_name:
        return _backend_instance

    with _lock:
        # Double-check under lock
        if _backend_instance is not None and _backend_name_cached == backend_name:
            return _backend_instance

        _backend_instance = _create_backend(backend_name)
        _backend_name_cached = backend_name
        return _backend_instance


def reset_backend() -> None:
    """Discard the cached backend singleton.

    Call this after changing ``storage_backend`` in admin settings so the
    next :func:`get_storage_backend` call creates a fresh instance.
    """
    global _backend_instance, _backend_name_cached
    with _lock:
        _backend_instance = None
        _backend_name_cached = None


def _create_backend(backend_name: str) -> BaseStorageBackend:
    """Instantiate the requested backend class."""
    name = (backend_name or 'local').lower().strip()

    if name == 'local':
        from app.services.storage.local_backend import LocalStorageBackend
        return LocalStorageBackend()

    if name == 'smb':
        from app.services.storage.smb_backend import SMBStorageBackend
        return SMBStorageBackend()

    if name == 's3':
        from app.services.storage.s3_backend import S3StorageBackend
        return S3StorageBackend()

    if name == 'azure_blob':
        from app.services.storage.azure_blob_backend import AzureBlobStorageBackend
        return AzureBlobStorageBackend()

    raise StorageError(
        f"Unknown storage backend {name!r}. "
        "Valid values: 'local', 'smb', 's3', 'azure_blob'."
    )
