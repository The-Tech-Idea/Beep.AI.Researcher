"""
Event Bridge — Routes internal app events to enabled integrations.

Connects the existing plugin hook system to the integration layer.
When events fire (document.uploaded, extraction.completed, etc.),
the bridge checks which integrations are subscribed and dispatches.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Event Types ──────────────────────────────────────────────────────────

class EventType:
    """Standard event types fired by the app."""
    DOCUMENT_CREATED = "document.created"
    DOCUMENT_DELETED = "document.deleted"
    DOCUMENT_UPDATED = "document.updated"
    CODE_CREATED = "code.created"
    CODE_DELETED = "code.deleted"
    EXTRACTION_COMPLETED = "extraction.completed"
    FLASHCARD_GENERATED = "flashcard.generated"
    QUIZ_COMPLETED = "quiz.completed"
    REPORT_SAVED = "report.saved"
    REFERENCE_ADDED = "reference.added"
    PROJECT_CREATED = "project.created"
    PROJECT_DELETED = "project.deleted"


# ── Event Bridge ─────────────────────────────────────────────────────────

class EventBridge:
    """
    Lightweight pub/sub event bridge.

    Usage:
        bridge = get_event_bridge()
        bridge.subscribe("document.created", my_handler)
        bridge.emit("document.created", {"project_id": 1, "document_id": 42})
    """

    _instance: Optional["EventBridge"] = None

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._history: List[Dict[str, Any]] = []
        self._max_history = 100

    @classmethod
    def get_instance(cls) -> "EventBridge":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def subscribe(self, event_type: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        """Subscribe a handler to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.debug("Subscribed handler to '%s'", event_type)

    def unsubscribe(self, event_type: str, handler: Callable) -> bool:
        """Remove a handler subscription."""
        handlers = self._subscribers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)
            return True
        return False

    def emit(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> int:
        """
        Fire an event to all subscribers.

        Returns: number of handlers called.
        """
        payload = {
            "event": event_type,
            "data": data or {},
        }

        # Record history
        self._history.append(payload)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        handlers = self._subscribers.get(event_type, [])
        called = 0
        for handler in handlers:
            try:
                handler(payload)
                called += 1
            except Exception as e:
                logger.error("Event handler error for '%s': %s", event_type, e)
        return called

    def get_subscribers(self, event_type: Optional[str] = None) -> Dict[str, int]:
        """Get subscriber counts per event type."""
        if event_type:
            return {event_type: len(self._subscribers.get(event_type, []))}
        return {k: len(v) for k, v in self._subscribers.items()}

    def get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent event history."""
        return self._history[-limit:]


def get_event_bridge() -> EventBridge:
    """Convenience function."""
    return EventBridge.get_instance()
