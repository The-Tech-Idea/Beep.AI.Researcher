"""
Base Connector — Abstract interface for all external integrations.

All integration connectors (storage, citation, export, etc.) extend this base.
Provides:
 - connect / disconnect / test_connection lifecycle
 - Retry with exponential backoff
 - Circuit breaker pattern
 - Health status tracking
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────

class ConnectorType(Enum):
    """Categories of integration connectors."""
    SEARCH = "search"
    STORAGE = "storage"
    CITATION = "citation"
    EXPORT = "export"
    WEBHOOK = "webhook"
    CUSTOM = "custom"


class ConnectorStatus(Enum):
    """Health status of a connector."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    CIRCUIT_OPEN = "circuit_open"


# ── Data Classes ─────────────────────────────────────────────────────────

@dataclass
class ConnectorInfo:
    """Metadata describing a connector."""
    name: str                                  # unique machine name
    display_name: str                          # human-readable
    connector_type: ConnectorType = ConnectorType.CUSTOM
    description: str = ""
    version: str = "1.0.0"
    docs_url: str = ""
    requires_auth: bool = False
    config_schema: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["connector_type"] = self.connector_type.value
        return d


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    items_synced: int = 0
    items_failed: int = 0
    errors: List[str] = field(default_factory=list)
    synced_at: datetime = field(default_factory=datetime.utcnow)
    next_cursor: Optional[str] = None         # for pagination / incremental

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["synced_at"] = self.synced_at.isoformat()
        return d


# ── Circuit Breaker ──────────────────────────────────────────────────────

class CircuitBreaker:
    """
    Simple circuit breaker.

    States:
      CLOSED   — requests flow normally
      OPEN     — all requests short-circuited (fail fast)
      HALF_OPEN — one trial request allowed; success resets, failure re-opens
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout   # seconds
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None

    def record_success(self):
        self.failure_count = 0
        self.state = self.CLOSED

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = self.OPEN
            logger.warning("Circuit breaker OPEN after %d failures", self.failure_count)

    def allow_request(self) -> bool:
        if self.state == self.CLOSED:
            return True
        if self.state == self.OPEN:
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.recovery_timeout:
                self.state = self.HALF_OPEN
                return True  # allow one trial
            return False
        # HALF_OPEN — allow one request
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_sec": self.recovery_timeout,
        }


# ── Abstract Base Connector ─────────────────────────────────────────────

class BaseConnector(ABC):
    """
    Abstract base class for all external integrations.

    Subclasses MUST implement:
      - info               (property)  → ConnectorInfo
      - _do_connect        (method)    → bool
      - _do_disconnect     (method)    → None
      - _do_test           (method)    → bool

    Optionally override:
      - _do_sync(since)    (method)    → SyncResult
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 max_retries: int = 3, retry_base_delay: float = 1.0,
                 circuit_failure_threshold: int = 5,
                 circuit_recovery_timeout: int = 60):
        self.config = config or {}
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self._status = ConnectorStatus.DISCONNECTED
        self._circuit = CircuitBreaker(circuit_failure_threshold, circuit_recovery_timeout)
        self._connected_at: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._request_count = 0
        self._error_count = 0

    # ── Abstract (must implement) ────────────────────────────────────

    @property
    @abstractmethod
    def info(self) -> ConnectorInfo:
        """Return metadata about this connector."""
        ...

    @abstractmethod
    def _do_connect(self, credentials: Dict[str, Any]) -> bool:
        """Establish connection using provided credentials. Return True on success."""
        ...

    @abstractmethod
    def _do_disconnect(self) -> None:
        """Clean up connection resources."""
        ...

    @abstractmethod
    def _do_test(self) -> bool:
        """Verify the connection is working (e.g., ping API). Return True if OK."""
        ...

    # ── Optional override ────────────────────────────────────────────

    def _do_sync(self, since: Optional[datetime] = None) -> SyncResult:
        """Override in subclasses that support incremental sync."""
        return SyncResult(success=False, errors=["Sync not supported by this connector."])

    # ── Public API ───────────────────────────────────────────────────

    def connect(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """Connect to the external service with retry + circuit breaker."""
        creds = credentials or {}
        self._status = ConnectorStatus.CONNECTING
        try:
            result = self._retry(lambda: self._do_connect(creds))
            if result:
                self._status = ConnectorStatus.CONNECTED
                self._connected_at = datetime.utcnow()
                self._circuit.record_success()
                logger.info("Connected: %s", self.info.name)
            else:
                self._status = ConnectorStatus.ERROR
                self._circuit.record_failure()
            return result
        except Exception as e:
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            self._circuit.record_failure()
            logger.error("Connect failed for %s: %s", self.info.name, e)
            return False

    def disconnect(self) -> None:
        """Disconnect from the external service."""
        try:
            self._do_disconnect()
        except Exception as e:
            logger.warning("Disconnect warning for %s: %s", self.info.name, e)
        finally:
            self._status = ConnectorStatus.DISCONNECTED
            self._connected_at = None

    def test_connection(self) -> bool:
        """Verify the current connection is healthy."""
        if not self._circuit.allow_request():
            self._status = ConnectorStatus.CIRCUIT_OPEN
            return False
        try:
            ok = self._do_test()
            if ok:
                self._circuit.record_success()
                self._status = ConnectorStatus.CONNECTED
            else:
                self._circuit.record_failure()
                self._status = ConnectorStatus.ERROR
            return ok
        except Exception as e:
            self._circuit.record_failure()
            self._status = ConnectorStatus.ERROR
            self._last_error = str(e)
            return False

    def sync(self, since: Optional[datetime] = None) -> SyncResult:
        """Run incremental sync with retry + circuit breaker."""
        if not self._circuit.allow_request():
            return SyncResult(success=False, errors=["Circuit breaker is open — too many failures."])
        try:
            result = self._retry(lambda: self._do_sync(since))
            if result.success:
                self._circuit.record_success()
            else:
                self._circuit.record_failure()
            return result
        except Exception as e:
            self._circuit.record_failure()
            self._last_error = str(e)
            return SyncResult(success=False, errors=[str(e)])

    def get_status(self) -> Dict[str, Any]:
        """Return current health status."""
        return {
            "name": self.info.name,
            "display_name": self.info.display_name,
            "type": self.info.connector_type.value,
            "status": self._status.value,
            "connected_at": self._connected_at.isoformat() if self._connected_at else None,
            "last_error": self._last_error,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "circuit_breaker": self._circuit.to_dict(),
        }

    # ── Retry logic ──────────────────────────────────────────────────

    def _retry(self, fn, retries: Optional[int] = None):
        """Execute fn with exponential backoff retries."""
        max_r = retries if retries is not None else self.max_retries
        last_err = None
        for attempt in range(max_r + 1):
            try:
                self._request_count += 1
                return fn()
            except Exception as e:
                last_err = e
                self._error_count += 1
                if attempt < max_r:
                    delay = self.retry_base_delay * (2 ** attempt)
                    logger.warning("Retry %d/%d for %s after %.1fs: %s",
                                   attempt + 1, max_r, self.info.name, delay, e)
                    time.sleep(delay)
        raise last_err  # type: ignore
