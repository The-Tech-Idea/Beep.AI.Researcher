"""
Event Bus System for Beep.AI.Researcher

Provides publish/subscribe pattern for internal event communication.
Supports both synchronous and asynchronous event handlers without external dependencies.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4
from dataclasses import dataclass, field, asdict
from functools import wraps
import threading
from queue import Queue, PriorityQueue
import time


logger = logging.getLogger(__name__)


class EventType(Enum):
    """Standard event types in Beep.AI.Researcher"""
    
    # Document events
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_DELETED = "document.deleted"
    DOCUMENT_PROCESSED = "document.processed"
    
    # Extraction events
    EXTRACTION_STARTED = "extraction.started"
    EXTRACTION_COMPLETED = "extraction.completed"
    EXTRACTION_FAILED = "extraction.failed"
    
    # Code events
    CODE_CREATED = "code.created"
    CODE_UPDATED = "code.updated"
    CODE_DELETED = "code.deleted"
    CODE_MERGED = "code.merged"
    
    # Chat events
    CHAT_MESSAGE_SENT = "chat.message_sent"
    CHAT_MESSAGE_RECEIVED = "chat.message_received"
    
    # Task events
    TASK_CREATED = "task.created"
    TASK_STATUS_CHANGED = "task.status_changed"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    
    # Project events
    PROJECT_CREATED = "project.created"
    PROJECT_UPDATED = "project.updated"
    PROJECT_DELETED = "project.deleted"
    
    # System events
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"
    
    def __str__(self) -> str:
        return self.value


class EventPriority(Enum):
    """Event priority levels for queue processing"""
    
    LOW = 3
    NORMAL = 2
    HIGH = 1
    CRITICAL = 0
    
    def __lt__(self, other):
        """Enable priority queue comparison"""
        if not isinstance(other, EventPriority):
            return NotImplemented
        return self.value < other.value


@dataclass
class Event:
    """Immutable event object"""
    
    event_type: str
    data: Dict[str, Any]
    source: str = "system"
    priority: EventPriority = EventPriority.NORMAL
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_id: str = field(default_factory=lambda: str(uuid4()))
    retries: int = 0
    max_retries: int = 3
    
    def __lt__(self, other) -> bool:
        """Enable comparison for priority queue (use event_id for tie-breaking)"""
        if not isinstance(other, Event):
            return NotImplemented
        # Compare by priority first, then by event_id for tie-breaking
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        return self.event_id < other.event_id
    
    def __eq__(self, other) -> bool:
        """Check equality by event_id"""
        if not isinstance(other, Event):
            return NotImplemented
        return self.event_id == other.event_id
    
    def __hash__(self) -> int:
        """Enable hashing for set/dict operations"""
        return hash(self.event_id)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "data": self.data,
            "source": self.source,
            "priority": self.priority.name,
            "timestamp": self.timestamp.isoformat(),
            "retries": self.retries,
        }
    
    def to_json(self) -> str:
        """Serialize event to JSON"""
        event_dict = self.to_dict()
        # Fix priority enum serialization
        event_dict["priority"] = self.priority.name
        return json.dumps(event_dict, default=str)


@dataclass
class EventSubscription:
    """Represents an event subscription"""
    
    subscriber_id: str
    event_type: str
    handler: Callable
    async_handler: bool = False
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    call_count: int = 0
    last_called: Optional[datetime] = None
    
    def __hash__(self):
        return hash(self.subscriber_id)


class EventBus:
    """
    Global event bus for publish/subscribe communication.
    
    Thread-safe implementation using asyncio queues and locks.
    Supports both sync and async event handlers.
    
    Usage:
        bus = EventBus()
        
        # Subscribe to events
        bus.subscribe(EventType.DOCUMENT_UPLOADED.value, handle_document_upload)
        
        # Publish event
        event = Event(
            event_type=EventType.DOCUMENT_UPLOADED.value,
            data={"document_id": "123", "name": "report.pdf"},
            source="document_route"
        )
        bus.publish(event)
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self):
        """Initialize EventBus with in-memory storage"""
        
        # Event storage and subscriptions
        self._subscribers: Dict[str, List[EventSubscription]] = {}
        self._event_history: List[Event] = []
        self._max_history: int = 10000
        
        # Queue for async processing
        self._event_queue: PriorityQueue = PriorityQueue()
        self._processing_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        
        # Stats
        self._stats = {
            "total_events": 0,
            "successful_events": 0,
            "failed_events": 0,
            "total_subscribers": 0,
        }
        
        logger.info("EventBus initialized")
    
    @classmethod
    def get_instance(cls) -> "EventBus":
        """Get singleton instance of EventBus (thread-safe)"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    cls._instance._start_processing_thread()
        return cls._instance
    
    def _start_processing_thread(self) -> None:
        """Start background thread for async event processing"""
        if self._processing_thread is None or not self._processing_thread.is_alive():
            self._processing_thread = threading.Thread(
                target=self._process_queue,
                daemon=True,
                name="EventBusProcessor"
            )
            self._processing_thread.start()
            logger.info("Event processing thread started")
    
    def _process_queue(self) -> None:
        """Background worker that processes queued events"""
        while not self._shutdown_event.is_set():
            try:
                # Wait for event with timeout
                try:
                    priority, event = self._event_queue.get(timeout=1)
                except:
                    continue
                
                # Process event with its subscribers
                self._deliver_event(event, async_handlers_only=True)
                
            except Exception as e:
                logger.error(f"Error in event processing thread: {e}", exc_info=True)
    
    def subscribe(
        self,
        event_type: str,
        handler: Callable,
        subscriber_id: Optional[str] = None,
        async_handler: bool = False
    ) -> str:
        """
        Subscribe to an event type.
        
        Args:
            event_type: Event type to subscribe to (EventType.X.value)
            handler: Callable to handle the event
            subscriber_id: Optional custom subscriber ID (auto-generated if not provided)
            async_handler: If True, handler is awaited as async
        
        Returns:
            subscriber_id: ID of the subscription (can be used to unsubscribe)
        """
        
        if subscriber_id is None:
            subscriber_id = str(uuid4())
        
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        
        subscription = EventSubscription(
            subscriber_id=subscriber_id,
            event_type=event_type,
            handler=handler,
            async_handler=async_handler,
        )
        
        self._subscribers[event_type].append(subscription)
        self._stats["total_subscribers"] += 1
        
        logger.info(
            f"Subscribed {subscriber_id} to {event_type} "
            f"(async={async_handler})"
        )
        
        return subscriber_id
    
    def unsubscribe(self, event_type: str, subscriber_id: str) -> bool:
        """
        Unsubscribe from an event type.
        
        Args:
            event_type: Event type to unsubscribe from
            subscriber_id: Subscription ID to remove
        
        Returns:
            True if unsubscribed, False if subscription not found
        """
        
        if event_type not in self._subscribers:
            return False
        
        original_count = len(self._subscribers[event_type])
        self._subscribers[event_type] = [
            s for s in self._subscribers[event_type]
            if s.subscriber_id != subscriber_id
        ]
        
        if len(self._subscribers[event_type]) < original_count:
            self._stats["total_subscribers"] -= 1
            logger.info(f"Unsubscribed {subscriber_id} from {event_type}")
            return True
        
        return False
    
    def publish(self, event: Event) -> str:
        """
        Publish an event to all subscribers (synchronously).
        
        Args:
            event: Event to publish
        
        Returns:
            event.event_id: The published event's ID
        """
        
        self._stats["total_events"] += 1
        
        # Store in history (with cleanup if too large)
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        logger.info(
            f"Event published: {event.event_type} "
            f"(id={event.event_id}, source={event.source})"
        )
        
        # Queue for async processing
        self._event_queue.put((event.priority.value, event))
        
        # Deliver synchronously to sync handlers
        self._deliver_event(event, async_handlers_only=False)
        
        return event.event_id
    
    def _deliver_event(self, event: Event, async_handlers_only: bool = False) -> None:
        """
        Deliver event to all matching subscribers.
        
        Args:
            event: Event to deliver
            async_handlers_only: If True, only call async handlers; if False, only sync
        """
        
        subscribers = self._subscribers.get(event.event_type, [])
        
        for subscription in subscribers:
            if not subscription.is_active:
                continue
            
            # Skip based on handler type filter
            if async_handlers_only and not subscription.async_handler:
                continue
            if not async_handlers_only and subscription.async_handler:
                continue
            
            try:
                # Call handler
                self._execute_handler(subscription, event)
                
                # Update subscription stats
                subscription.call_count += 1
                subscription.last_called = datetime.now(timezone.utc)
                self._stats["successful_events"] += 1
                
            except Exception as e:
                self._stats["failed_events"] += 1
                logger.error(
                    f"Error in event handler {subscription.subscriber_id}: {e}",
                    exc_info=True
                )
                
                # Retry logic
                if event.retries < event.max_retries:
                    event.retries += 1
                    logger.info(
                        f"Retrying event {event.event_id} "
                        f"(attempt {event.retries}/{event.max_retries})"
                    )
                    # Re-queue with delay
                    self._event_queue.put((event.priority.value, event))
    
    def _execute_handler(self, subscription: EventSubscription, event: Event) -> None:
        """
        Execute a handler with proper error handling.
        
        Args:
            subscription: The subscription with the handler
            event: The event to pass to handler
        """
        
        handler = subscription.handler
        
        # Check if async handler
        if asyncio.iscoroutinefunction(handler):
            # Try to run in existing event loop, otherwise create new one
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Schedule as task if loop is running
                    asyncio.create_task(handler(event))
                else:
                    # Run in current loop
                    loop.run_until_complete(handler(event))
            except RuntimeError:
                # No event loop, create new one
                asyncio.run(handler(event))
        else:
            # Sync handler
            handler(event)
    
    def get_event_history(
        self,
        event_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Event]:
        """
        Retrieve event history.
        
        Args:
            event_type: Optional filter by event type
            limit: Maximum number of events to return
            offset: Starting position in history
        
        Returns:
            List of events matching criteria
        """
        
        filtered = self._event_history
        
        if event_type:
            filtered = [e for e in filtered if e.event_type == event_type]
        
        return filtered[offset:offset + limit]
    
    def get_subscriptions(self, event_type: Optional[str] = None) -> Dict[str, List[EventSubscription]]:
        """
        Get subscriptions, optionally filtered by event type.
        
        Args:
            event_type: Optional filter by event type
        
        Returns:
            Dictionary of event types to subscriptions
        """
        
        if event_type:
            return {event_type: self._subscribers.get(event_type, [])}
        
        return self._subscribers.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics"""
        return self._stats.copy()
    
    def clear_history(self) -> int:
        """Clear event history and return count cleared"""
        count = len(self._event_history)
        self._event_history = []
        logger.info(f"Cleared {count} events from history")
        return count
    
    def reset_stats(self) -> None:
        """Reset all statistics (preserves subscriber count)"""
        # Count current subscribers to preserve accurate count
        current_subscribers = sum(
            len(subs) for subs in self._subscribers.values()
        )
        
        self._stats["total_events"] = 0
        self._stats["successful_events"] = 0
        self._stats["failed_events"] = 0
        self._stats["total_subscribers"] = current_subscribers
        logger.info("Statistics reset")
    
    def shutdown(self) -> None:
        """Shutdown the event bus gracefully"""
        logger.info("Shutting down EventBus")
        self._shutdown_event.set()
        if self._processing_thread and self._processing_thread.is_alive():
            self._processing_thread.join(timeout=5)
        logger.info("EventBus shutdown complete")


def event_handler(event_type: str, subscriber_id: Optional[str] = None, async_handler: bool = False):
    """
    Decorator to easily register event handlers.
    
    Usage:
        @event_handler(EventType.DOCUMENT_UPLOADED.value)
        def handle_document_upload(event: Event):
            logger.info(f"Document uploaded: {event.data}")
    
    Args:
        event_type: Event type to handle
        subscriber_id: Optional custom subscriber ID
        async_handler: If True, handler is treated as async
    """
    
    def decorator(func: Callable) -> Callable:
        EventBus.get_instance().subscribe(
            event_type,
            func,
            subscriber_id=subscriber_id,
            async_handler=async_handler
        )
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator


# Create singleton instance
def get_event_bus() -> EventBus:
    """Get the global event bus instance"""
    return EventBus.get_instance()
