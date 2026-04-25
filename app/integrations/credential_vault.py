"""
Credential Vault — Encrypted storage for integration API keys and tokens.

Uses Fernet symmetric encryption from the `cryptography` library.
Falls back to base64 obfuscation if cryptography is not installed.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Try to use Fernet; fall back to base64 obfuscation
try:
    from cryptography.fernet import Fernet
    HAS_FERNET = True
except ImportError:
    HAS_FERNET = False
    logger.warning("cryptography not installed — credential vault uses base64 (NOT secure for production)")


def _get_encryption_key() -> bytes:
    """
    Derive encryption key from environment or generate a stable one.

    In production, set BEEP_VAULT_KEY as a Fernet key.
    """
    env_key = os.environ.get("BEEP_VAULT_KEY")
    if env_key:
        return env_key.encode()
    # Deterministic fallback for development (NOT secure for production)
    import hashlib
    digest = hashlib.sha256(b"beep-ai-researcher-dev-key").digest()
    return base64.urlsafe_b64encode(digest)



class CredentialVault:
    """
    Encrypt / decrypt integration credentials.

    Usage:
        vault = CredentialVault()
        encrypted = vault.encrypt({"api_key": "sk-...", "email": "user@example.com"})
        decrypted = vault.decrypt(encrypted)  # → {"api_key": "sk-...", ...}
    """

    def __init__(self, key: Optional[bytes] = None):
        self._key = key or _get_encryption_key()
        if HAS_FERNET:
            self._fernet = Fernet(self._key)
        else:
            self._fernet = None

    def encrypt(self, data: Dict[str, Any]) -> str:
        """Encrypt a credentials dict → base64 string."""
        raw = json.dumps(data).encode("utf-8")
        if self._fernet:
            return self._fernet.encrypt(raw).decode("utf-8")
        # Fallback: base64 obfuscation
        return base64.urlsafe_b64encode(raw).decode("utf-8")

    def decrypt(self, token: str) -> Dict[str, Any]:
        """Decrypt a base64 string → credentials dict."""
        try:
            if self._fernet:
                raw = self._fernet.decrypt(token.encode("utf-8"))
            else:
                raw = base64.urlsafe_b64decode(token.encode("utf-8"))
            return json.loads(raw)
        except Exception as e:
            logger.error("Failed to decrypt credential: %s", e)
            return {}

    def rotate_key(self, old_token: str, new_vault: "CredentialVault") -> str:
        """Re-encrypt data from old key to new key."""
        data = self.decrypt(old_token)
        return new_vault.encrypt(data)


# Singleton
_vault: Optional[CredentialVault] = None


def get_vault() -> CredentialVault:
    global _vault
    if _vault is None:
        _vault = CredentialVault()
    return _vault
