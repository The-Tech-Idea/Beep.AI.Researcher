"""SMBStorageBackend — stores files on a Windows/Samba network share.

Requires the ``smbprotocol`` package (``pip install smbprotocol``).
The backend falls back gracefully with a clear error if the package is absent.

Config keys consumed (set via Admin → Settings → Storage):
  storage_smb_host, storage_smb_share, storage_smb_username,
  storage_smb_password, storage_smb_domain
"""
from __future__ import annotations

import io
import logging
from typing import IO, Optional

from app.services.storage.base import BaseStorageBackend, StorageError

logger = logging.getLogger(__name__)

_SMB_AVAILABLE = None  # Lazy import flag


def _check_smb() -> None:
    global _SMB_AVAILABLE
    if _SMB_AVAILABLE is None:
        try:
            import smbprotocol  # noqa: F401
            _SMB_AVAILABLE = True
        except ImportError:
            _SMB_AVAILABLE = False
    if not _SMB_AVAILABLE:
        raise StorageError(
            "SMB backend requires 'smbprotocol': pip install smbprotocol"
        )


class SMBStorageBackend(BaseStorageBackend):
    """Store files on a Windows / Samba share via smbprotocol."""

    def __init__(self,
                 host: Optional[str] = None,
                 share: Optional[str] = None,
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 domain: Optional[str] = None):
        from app.config_manager import config_manager as cm
        self._host     = host     or cm.get('storage_smb_host', '')
        self._share    = share    or cm.get('storage_smb_share', '')
        self._username = username or cm.get('storage_smb_username', '')
        self._password = password or cm.get('storage_smb_password', '')
        self._domain   = domain   or cm.get('storage_smb_domain', '')

    @property
    def backend_name(self) -> str:
        return 'smb'

    def _get_connection(self):
        _check_smb()
        import smbprotocol.connection
        import smbprotocol.session
        import smbprotocol.tree
        conn = smbprotocol.connection.Connection(
            uuid=__import__('uuid').uuid4(),
            server_name=self._host,
        )
        conn.connect()
        session = smbprotocol.session.Session(
            conn,
            username=f'{self._domain}\\{self._username}' if self._domain else self._username,
            password=self._password,
        )
        session.connect()
        tree = smbprotocol.tree.TreeConnect(
            session,
            f'\\\\{self._host}\\{self._share}',
        )
        tree.connect()
        return conn, session, tree

    def _smb_path(self, key: str) -> str:
        return key.replace('/', '\\')

    def save(self, stream: IO[bytes], key: str) -> str:
        _check_smb()
        try:
            from smbprotocol.open import (
                Open, CreateDisposition, CreateOptions,
                FilePipePrinterAccessMask, ImpersonationLevel,
                ShareAccess, SMB2ShareInfo,
            )
            conn, session, tree = self._get_connection()
            smb_key = self._smb_path(key)
            file_obj = Open(tree, smb_key)
            file_obj.create(
                ImpersonationLevel.Impersonation,
                FilePipePrinterAccessMask.GENERIC_WRITE,
                0,
                ShareAccess.NONE,
                CreateDisposition.FILE_OVERWRITE_IF,
                CreateOptions.FILE_NON_DIRECTORY_FILE,
            )
            data = stream.read()
            file_obj.write(data, 0)
            file_obj.close()
            conn.disconnect(True)
            return key
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f'SMB save failed for {key!r}: {exc}') from exc

    def load(self, key: str) -> bytes:
        _check_smb()
        try:
            from smbprotocol.open import (
                Open, CreateDisposition, CreateOptions,
                FilePipePrinterAccessMask, ImpersonationLevel, ShareAccess,
            )
            conn, session, tree = self._get_connection()
            smb_key = self._smb_path(key)
            file_obj = Open(tree, smb_key)
            file_obj.create(
                ImpersonationLevel.Impersonation,
                FilePipePrinterAccessMask.GENERIC_READ,
                0,
                ShareAccess.SHARE_READ,
                CreateDisposition.FILE_OPEN,
                CreateOptions.FILE_NON_DIRECTORY_FILE,
            )
            data = file_obj.read(0, file_obj.end_of_file)
            file_obj.close()
            conn.disconnect(True)
            return data
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError(f'SMB load failed for {key!r}: {exc}') from exc

    def delete(self, key: str) -> None:
        _check_smb()
        try:
            from smbprotocol.open import (
                Open, CreateDisposition, CreateOptions,
                FilePipePrinterAccessMask, ImpersonationLevel, ShareAccess,
            )
            conn, session, tree = self._get_connection()
            smb_key = self._smb_path(key)
            file_obj = Open(tree, smb_key)
            file_obj.create(
                ImpersonationLevel.Impersonation,
                FilePipePrinterAccessMask.DELETE,
                0,
                ShareAccess.NONE,
                CreateDisposition.FILE_OPEN,
                CreateOptions.FILE_NON_DIRECTORY_FILE | CreateOptions.FILE_DELETE_ON_CLOSE,
            )
            file_obj.close()
            conn.disconnect(True)
        except StorageError:
            raise
        except Exception as exc:
            logger.warning('SMB delete failed for %r (may not exist): %s', key, exc)

    def exists(self, key: str) -> bool:
        _check_smb()
        try:
            from smbprotocol.open import (
                Open, CreateDisposition, CreateOptions,
                FilePipePrinterAccessMask, ImpersonationLevel, ShareAccess,
            )
            conn, session, tree = self._get_connection()
            smb_key = self._smb_path(key)
            file_obj = Open(tree, smb_key)
            file_obj.create(
                ImpersonationLevel.Impersonation,
                FilePipePrinterAccessMask.GENERIC_READ,
                0,
                ShareAccess.SHARE_READ,
                CreateDisposition.FILE_OPEN,
                CreateOptions.FILE_NON_DIRECTORY_FILE,
            )
            file_obj.close()
            conn.disconnect(True)
            return True
        except Exception:
            return False
