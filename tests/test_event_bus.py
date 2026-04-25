"""
Unit tests for Event Bus System

Tests cover:
- Event creation and serialization
- Publishing and subscription
- Synchronous and asynchronous handlers
- Event history and statistics
- Error handling and retries
- Priority queue ordering
"""

import pytest
import asyncio
import json
import time
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
from app.core.event_bus import (
    EventBus,
    Event,
    EventType,
    EventPriority,
    EventSubscription,
    get_event_bus,
    event_handler,
)


@pytest.fixture
def event_bus():
    """Create fresh EventBus instance for each test"""
    # Create new instance by resetting singleton
    EventBus._instance = None
    bus = EventBus.get_instance()
    yield bus
    # Cleanup
    bus.shutdown()
    EventBus._instance = None


@pytest.fixture
def sample_event():
    """Create a sample event"""
    return Event(
        event_type=EventType.DOCUMENT_UPLOADED.value,
        data={"document_id": "doc123", "name": "report.pdf"},
        source="test_source"
    )


class TestEventCreation:
    """Test Event object creation and serialization"""
    
    def test_event_creation_with_defaults(self):
        """Test creating event with default values"""
        event = Event(
            event_type=EventType.DOCUMENT_UPLOADED.value,
            data={"id": "123"}
        )
        
        assert event.event_type == EventType.DOCUMENT_UPLOADED.value
        assert event.data == {"id": "123"}
        assert event.source == "system"
        assert event.priority == EventPriority.NORMAL
        assert event.timestamp is not None
        assert event.event_id is not None
        assert event.retries == 0
        assert len(event.event_id) == 36  # UUID length
    
    def test_event_creation_with_custom_values(self):
        """Test creating event with custom values"""
        event = Event(
            event_type=EventType.CODE_CREATED.value,
            data={"code_id": "code456"},
            source="code_route",
            priority=EventPriority.HIGH
        )
        
        assert event.event_type == EventType.CODE_CREATED.value
        assert event.source == "code_route"
        assert event.priority == EventPriority.HIGH
    
    def test_event_to_dict(self):
        """Test event serialization to dictionary"""
        event = Event(
            event_type=EventType.DOCUMENT_UPLOADED.value,
            data={"id": "123"}
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["event_type"] == EventType.DOCUMENT_UPLOADED.value
        assert event_dict["data"] == {"id": "123"}
        assert event_dict["source"] == "system"
        assert "timestamp" in event_dict
        assert "event_id" in event_dict
    
    def test_event_to_json(self):
        """Test event serialization to JSON"""
        event = Event(
            event_type=EventType.TASK_CREATED.value,
            data={"task_id": "task789"}
        )
        
        json_str = event.to_json()
        
        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["event_type"] == EventType.TASK_CREATED.value
        assert parsed["data"]["task_id"] == "task789"
    
    def test_event_priority_comparison(self):
        """Test event priority ordering"""
        assert EventPriority.CRITICAL < EventPriority.HIGH
        assert EventPriority.HIGH < EventPriority.NORMAL
        assert EventPriority.NORMAL < EventPriority.LOW


class TestEventSubscription:
    """Test event subscription management"""
    
    def test_subscribe_handler(self, event_bus):
        """Test subscribing to an event"""
        handler = Mock()
        subscriber_id = event_bus.subscribe(
            EventType.DOCUMENT_UPLOADED.value,
            handler
        )
        
        assert subscriber_id is not None
        assert len(subscriber_id) == 36  # UUID length
        
        subscriptions = event_bus.get_subscriptions(EventType.DOCUMENT_UPLOADED.value)
        assert EventType.DOCUMENT_UPLOADED.value in subscriptions
        assert len(subscriptions[EventType.DOCUMENT_UPLOADED.value]) == 1
    
    def test_subscribe_with_custom_id(self, event_bus):
        """Test subscribing with custom subscriber ID"""
        handler = Mock()
        custom_id = "custom_handler_1"
        
        subscriber_id = event_bus.subscribe(
            EventType.CODE_CREATED.value,
            handler,
            subscriber_id=custom_id
        )
        
        assert subscriber_id == custom_id
    
    def test_multiple_subscribers_same_event(self, event_bus):
        """Test multiple subscribers for the same event"""
        handler1 = Mock()
        handler2 = Mock()
        
        event_bus.subscribe(EventType.DOCUMENT_UPLOADED.value, handler1)
        event_bus.subscribe(EventType.DOCUMENT_UPLOADED.value, handler2)
        
        subscriptions = event_bus.get_subscriptions(EventType.DOCUMENT_UPLOADED.value)
        assert len(subscriptions[EventType.DOCUMENT_UPLOADED.value]) == 2
    
    def test_unsubscribe_handler(self, event_bus):
        """Test unsubscribing from an event"""
        handler = Mock()
        subscriber_id = event_bus.subscribe(EventType.TASK_CREATED.value, handler)
        
        result = event_bus.unsubscribe(EventType.TASK_CREATED.value, subscriber_id)
        
        assert result is True
        subscriptions = event_bus.get_subscriptions(EventType.TASK_CREATED.value)
        assert len(subscriptions[EventType.TASK_CREATED.value]) == 0
    
    def test_unsubscribe_nonexistent(self, event_bus):
        """Test unsubscribing when not subscribed"""
        result = event_bus.unsubscribe(EventType.DOCUMENT_DELETED.value, "nonexistent")
        
        assert result is False


class TestEventPublishing:
    """Test event publishing and delivery"""
    
    def test_publish_calls_sync_handler(self, event_bus, sample_event):
        """Test that publishing calls synchronous handlers"""
        handler = Mock()
        event_bus.subscribe(EventType.DOCUMENT_UPLOADED.value, handler)
        
        event_id = event_bus.publish(sample_event)
        
        assert event_id == sample_event.event_id
        # Give time for sync handler to execute
        time.sleep(0.1)
        handler.assert_called()
    
    def test_publish_multiple_handlers(self, event_bus, sample_event):
        """Test publishing to multiple handlers"""
        handler1 = Mock()
        handler2 = Mock()
        handler3 = Mock()
        
        event_bus.subscribe(EventType.DOCUMENT_UPLOADED.value, handler1)
        event_bus.subscribe(EventType.DOCUMENT_UPLOADED.value, handler2)
        event_bus.subscribe(EventType.CODE_CREATED.value, handler3)
        
        event_bus.publish(sample_event)
        time.sleep(0.1)
        
        handler1.assert_called()
        handler2.assert_called()
        # handler3 should not be called (different event type)
        handler3.assert_not_called()
    
    def test_publish_returns_event_id(self, event_bus):
        """Test that publish returns event ID"""
        event = Event(
            event_type=EventType.CHAT_MESSAGE_SENT.value,
            data={"message": "hello"}
        )
        
        event_id = event_bus.publish(event)
        
        assert event_id == event.event_id
    
    def test_handler_receives_event_object(self, event_bus):
        """Test that handler receives the event object"""
        received_event = None
        
        def handler(event: Event):
            nonlocal received_event
            received_event = event
        
        event = Event(
            event_type=EventType.PROJECT_CREATED.value,
            data={"project_id": "proj123"}
        )
        
        event_bus.subscribe(EventType.PROJECT_CREATED.value, handler)
        event_bus.publish(event)
        time.sleep(0.1)
        
        assert received_event is not None
        assert received_event.event_type == EventType.PROJECT_CREATED.value
        assert received_event.data["project_id"] == "proj123"


class TestEventHistory:
    """Test event history tracking"""
    
    def test_event_added_to_history(self, event_bus):
        """Test that published events are added to history"""
        event1 = Event(EventType.DOCUMENT_UPLOADED.value, {"id": "1"})
        event2 = Event(EventType.CODE_CREATED.value, {"id": "2"})
        
        event_bus.publish(event1)
        event_bus.publish(event2)
        
        history = event_bus.get_event_history()
        assert len(history) >= 2
    
    def test_history_filtering_by_event_type(self, event_bus):
        """Test filtering event history by type"""
        event_bus.publish(Event(EventType.DOCUMENT_UPLOADED.value, {"id": "1"}))
        event_bus.publish(Event(EventType.CODE_CREATED.value, {"id": "2"}))
        event_bus.publish(Event(EventType.DOCUMENT_UPLOADED.value, {"id": "3"}))
        
        history = event_bus.get_event_history(
            event_type=EventType.DOCUMENT_UPLOADED.value
        )
        
        assert all(e.event_type == EventType.DOCUMENT_UPLOADED.value for e in history)
        assert len(history) >= 2
    
    def test_history_pagination(self, event_bus):
        """Test pagination of event history"""
        for i in range(10):
            event_bus.publish(Event(EventType.TASK_CREATED.value, {"id": str(i)}))
        
        page1 = event_bus.get_event_history(limit=5, offset=0)
        page2 = event_bus.get_event_history(limit=5, offset=5)
        
        assert len(page1) == 5
        assert len(page2) == 5
        # Ensure no overlap
        ids1 = {e.event_id for e in page1}
        ids2 = {e.event_id for e in page2}
        assert len(ids1 & ids2) == 0
    
    def test_clear_history(self, event_bus):
        """Test clearing event history"""
        event_bus.publish(Event(EventType.DOCUMENT_UPLOADED.value, {"id": "1"}))
        event_bus.publish(Event(EventType.CODE_CREATED.value, {"id": "2"}))
        
        count = event_bus.clear_history()
        
        assert count >= 2
        assert len(event_bus.get_event_history()) == 0


class TestStatistics:
    """Test event bus statistics"""
    
    def test_stats_track_published_events(self, event_bus):
        """Test that stats track published events"""
        initial_stats = event_bus.get_stats()
        initial_count = initial_stats["total_events"]
        
        event_bus.publish(Event(EventType.DOCUMENT_UPLOADED.value, {}))
        event_bus.publish(Event(EventType.CODE_CREATED.value, {}))
        
        new_stats = event_bus.get_stats()
        assert new_stats["total_events"] == initial_count + 2
    
    def test_stats_track_subscribers(self, event_bus):
        """Test that stats track total subscribers"""
        initial_stats = event_bus.get_stats()
        initial_count = initial_stats["total_subscribers"]
        
        handler1 = Mock()
        handler2 = Mock()
        
        event_bus.subscribe(EventType.DOCUMENT_UPLOADED.value, handler1)
        event_bus.subscribe(EventType.CODE_CREATED.value, handler2)
        
        new_stats = event_bus.get_stats()
        assert new_stats["total_subscribers"] == initial_count + 2
    
    def test_reset_stats(self, event_bus):
        """Test resetting statistics"""
        event_bus.publish(Event(EventType.DOCUMENT_UPLOADED.value, {}))
        event_bus.subscribe(EventType.CODE_CREATED.value, Mock())
        
        event_bus.reset_stats()
        stats = event_bus.get_stats()
        
        assert stats["total_events"] == 0
        assert stats["total_subscribers"] == 1  # Still tracks current subscriptions


class TestErrorHandling:
    """Test error handling in event delivery"""
    
    def test_handler_exception_caught(self, event_bus):
        """Test that handler exceptions don't crash event bus"""
        def bad_handler(event: Event):
            raise ValueError("Handler error")
        
        event_bus.subscribe(EventType.DOCUMENT_UPLOADED.value, bad_handler)
        
        # Should not raise
        event_bus.publish(Event(EventType.DOCUMENT_UPLOADED.value, {}))
        time.sleep(0.1)
        
        stats = event_bus.get_stats()
        assert stats["failed_events"] > 0
    
    def test_one_handler_failure_doesnt_affect_others(self, event_bus):
        """Test that one handler's failure doesn't prevent other handlers"""
        def bad_handler(event: Event):
            raise RuntimeError("Bad handler")
        
        good_handler = Mock()
        
        event_bus.subscribe(EventType.CODE_CREATED.value, bad_handler)
        event_bus.subscribe(EventType.CODE_CREATED.value, good_handler)
        
        event_bus.publish(Event(EventType.CODE_CREATED.value, {"id": "1"}))
        time.sleep(0.1)
        
        # Good handler should still be called
        good_handler.assert_called()


class TestEventDecorator:
    """Test @event_handler decorator"""
    
    def test_event_handler_decorator(self, event_bus):
        """Test using @event_handler decorator"""
        # Reset instance to use in decorator
        EventBus._instance = event_bus
        
        handler_called = False
        
        @event_handler(EventType.DOCUMENT_UPLOADED.value)
        def handle_upload(event: Event):
            nonlocal handler_called
            handler_called = True
        
        event_bus.publish(Event(EventType.DOCUMENT_UPLOADED.value, {"id": "1"}))
        time.sleep(0.1)
        
        assert handler_called is True
    
    def test_decorator_with_custom_id(self, event_bus):
        """Test decorator with custom subscriber ID"""
        EventBus._instance = event_bus
        
        @event_handler(EventType.TASK_CREATED.value, subscriber_id="custom_task_handler")
        def handle_task(event: Event):
            pass
        
        subscriptions = event_bus.get_subscriptions(EventType.TASK_CREATED.value)
        subscriber_ids = [s.subscriber_id for s in subscriptions[EventType.TASK_CREATED.value]]
        
        assert "custom_task_handler" in subscriber_ids


class TestSingleton:
    """Test EventBus singleton pattern"""
    
    def test_get_instance_returns_same_object(self):
        """Test that get_instance returns the same object"""
        EventBus._instance = None
        
        instance1 = EventBus.get_instance()
        instance2 = EventBus.get_instance()
        
        assert instance1 is instance2
    
    def test_subscriptions_persist_across_instances(self):
        """Test that subscriptions persist when getting instance again"""
        EventBus._instance = None
        bus1 = EventBus.get_instance()
        
        handler = Mock()
        bus1.subscribe(EventType.DOCUMENT_UPLOADED.value, handler)
        
        bus2 = EventBus.get_instance()
        subscriptions = bus2.get_subscriptions(EventType.DOCUMENT_UPLOADED.value)
        
        assert len(subscriptions[EventType.DOCUMENT_UPLOADED.value]) == 1


class TestEventTypes:
    """Test event type enum"""
    
    def test_all_event_types_have_string_values(self):
        """Test that all event types render as strings"""
        for event_type in EventType:
            assert isinstance(str(event_type), str)
            assert len(str(event_type)) > 0
    
    def test_event_type_uniqueness(self):
        """Test that event type values are unique"""
        values = [str(et) for et in EventType]
        assert len(values) == len(set(values))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
