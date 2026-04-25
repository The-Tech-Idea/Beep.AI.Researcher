"""LocalStorageBackend — saves files to the local filesystem.

Uses ``config_manager.uploads_path`` (which resolves ``storage_local_path``
from admin config) as the root directory.
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import IO, Optional

from app.services.storage.base import BaseStorageBackend, StorageError

logger = logging.getLogger(__name__)


class LocalStorageBackend(BaseStorageBackend):
    """Store files under a local filesystem directory."""

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Args:
            base_dir: Root upload directory.  Defaults to
                      ``config_manager.uploads_path`` when None.
        """
        if base_dir is not None:
            self._base = Path(base_dir)
        else:
            from app.config_manager import config_manager
            self._base = config_manager.uploads_path
        self._base.mkdir(parents=True, exist_ok=True)

    @property
    def backend_name(self) -> str:
        return 'local'

    def _full_path(self, key: str) -> Path:
        """Resolve ``key`` to an absolute path inside ``_base``."""
        # Prevent path traversal
        resolved = (self._base / key).resolve()
        if not str(resolved).startswith(str(self._base.resolve())):
            raise StorageError(f'Path traversal attempt detected: {key}')
        return resolved

    # ── Core operations ───────────────────────────────────────────────────────

    def save(self, stream: IO[bytes], key: str) -> str:
        try:
            dest = self._full_path(key)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, 'wb') as fout:
                shutil.copyfileobj(stream, fout)
            logger.debug('LocalStorage: saved %s (%d bytes)', key, dest.stat().st_size)
            return key
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f'LocalStorage save failed for {key!r}: {exc}') from exc

    def load(self, key: str) -> bytes:
        try:
            return self._full_path(key).read_bytes()
        except FileNotFoundError:
            raise StorageError(f'LocalStorage: key not found: {key!r}')
        except Exception as exc:
            raise StorageError(f'LocalStorage load failed for {key!r}: {exc}') from exc

    def delete(self, key: str) -> None:
        try:
            p = self._full_path(key)
            if p.exists():
                p.unlink()
                logger.debug('LocalStorage: deleted %s', key)
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f'LocalStorage delete failed for {key!r}: {exc}') from exc

    def exists(self, key: str) -> bool:
        try:
            return self._full_path(key).exists()
        except StorageError:
            return False

    def file_size(self, key: str) -> int:
        try:
            return self._full_path(key).stat().st_size
        except Exception:
            return 0

    def send_file_response(self, key: str, filename: str,
                            mimetype: Optional[str] = None):
        from flask import send_file
        full = self._full_path(key)
        if not full.exists():
            raise StorageError(f'LocalStorage: key not found: {key!r}')
        return send_file(
            str(full),
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype or 'application/octet-stream',
        )
