"""BaseStorageBackend — abstract interface implemented by every storage backend.

Every backend must support the four core operations:
  - save(stream, key) → str  (the storage key / relative path to record in DB)
  - load(key) → bytes
  - delete(key) → None
  - exists(key) → bool

Additionally, backends that support streaming responses expose:
  - send_file_response(key, filename, mimetype) → Flask Response

All methods raise ``StorageError`` on failure so callers have a uniform
exception to catch.
"""
from __future__ import annotations

import abc
from typing import IO, Optional


class StorageError(Exception):
    """Base exception for all storage backend failures."""


class BaseStorageBackend(abc.ABC):
    """Abstract interface for file-storage backends."""

    # ── Core operations ───────────────────────────────────────────────────────

    @abc.abstractmethod
    def save(self, stream: IO[bytes], key: str) -> str:
        """Persist ``stream`` under ``key``.

        Args:
            stream: File-like object opened in binary read mode.
            key: Storage key / relative path.  The backend may adjust this
                 (e.g. prefix with a bucket sub-folder).

        Returns:
            The canonical storage key to record in the database.  This is
            what you later pass to ``load`` / ``delete`` / ``exists``.
        """

    @abc.abstractmethod
    def load(self, key: str) -> bytes:
        """Return the raw bytes stored under ``key``."""

    @abc.abstractmethod
    def delete(self, key: str) -> None:
        """Remove the object stored under ``key``.  Silently ignored if absent."""

    @abc.abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if an object stored under ``key`` exists."""

    # ── Streaming response (optional — falls back to load()) ─────────────────

    def send_file_response(self, key: str, filename: str,
                            mimetype: Optional[str] = None):
        """Return a Flask response that streams the stored file to the browser.

        The default implementation reads the entire file into memory and wraps
        it in a ``flask.send_file`` call.  Backends that support efficient
        streaming (e.g. range requests, pre-signed redirect URLs) should
        override this.

        Args:
            key: Storage key returned by ``save()``.
            filename: Download filename hint.
            mimetype: MIME type; guessed if None.

        Returns:
            Flask ``Response`` object.
        """
        import io
        from flask import send_file
        data = self.load(key)
        return send_file(
            io.BytesIO(data),
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype or 'application/octet-stream',
        )

    # ── Metadata helpers ──────────────────────────────────────────────────────

    def file_size(self, key: str) -> int:
        """Return the size in bytes for ``key``.

        Default implementation loads the full object — backends that can
        cheaply query size (HEAD request, stat call) should override this.
        """
        return len(self.load(key))

    @property
    @abc.abstractmethod
    def backend_name(self) -> str:
        """Human-readable backend identifier (e.g. 'local', 's3')."""
