"""
Unit tests for Hook System

Tests cover:
- Hook creation and initialization
- Hook execution with different event types
- Hook registration and unregistration
- Priority-based ordering
- Conditional execution
- Error handling and isolation
- Built-in hooks functionality
- Statistics tracking
"""

import pytest
import time
from datetime import datetime, timezone
from app.core import (
    Hook,
    HookType,
    HookPriority,
    HookContext,
    HookRegistry,
    get_hook_registry,
    Event,
    EventType,
    DocumentUploadHook,
    ExtractionHook,
    CodeHook,
    AutoExtractionHook,
    ValidationHook,
    NotificationHook,
    AuditLoggingHook,
)


@pytest.fixture
def registry():
    """Create fresh HookRegistry instance for each test"""
    HookRegistry._instance = None
    reg = HookRegistry.get_instance()
    yield reg
    HookRegistry._instance = None


@pytest.fixture
def sample_event():
    """Create a sample event"""
    return Event(
        event_type=EventType.DOCUMENT_UPLOADED.value,
        data={"document_id": "doc123", "filename": "report.pdf"}
    )


class TestHookContext:
    """Test HookContext object"""
    
    def test_context_creation(self, sample_event):
        """Test creating hook context"""
        context = HookContext(
            hook_id="hook1",
            event=sample_event,
            operation_name="upload"
        )
        
        assert context.hook_id == "hook1"
        assert context.event == sample_event
        assert context.operation_name == "upload"
        assert context.result is None
        assert context.error is None
        assert isinstance(context.timestamp, datetime)
    
    def test_context_with_data(self, sample_event):
        """Test context with custom data"""
        context = HookContext(
            hook_id="hook1",
            event=sample_event,
            operation_name="upload",
            context_data={"user_id": "user123", "project_id": "proj456"}
        )
        
        assert context.context_data["user_id"] == "user123"
        assert context.context_data["project_id"] == "proj456"
    
    def test_context_to_dict(self, sample_event):
        """Test context serialization"""
        context = HookContext(
            hook_id="hook1",
            event=sample_event,
            operation_name="upload",
            result="success"
        )
        
        context_dict = context.to_dict()
        
        assert context_dict["hook_id"] == "hook1"
        assert context_dict["event_type"] == EventType.DOCUMENT_UPLOADED.value
        assert context_dict["operation"] == "upload"
        assert context_dict["result"] == "success"


class TestHookBase:
    """Test Hook base class"""
    
    def test_hook_creation(self):
        """Test creating a basic hook"""
        hook = DocumentUploadHook(
            name="TestHook",
            hook_type=HookType.AFTER,
            priority=HookPriority.HIGH,
            enabled=True
        )
        
        assert hook.name == "TestHook"
        assert hook.hook_type == HookType.AFTER
        assert hook.priority == HookPriority.HIGH
        assert hook.enabled is True
        assert hook.call_count == 0
        assert hook.error_count == 0
        assert hook.hook_id is not None
    
    def test_hook_default_values(self):
        """Test hook defaults"""
        hook = DocumentUploadHook("test")
        
        assert hook.hook_type == HookType.AFTER
        assert hook.priority == HookPriority.NORMAL
        assert hook.enabled is True
    
    def test_hook_priority_comparison(self):
        """Test hook priority ordering"""
        high = Hook("high", priority=HookPriority.HIGH)
        low = Hook("low", priority=HookPriority.LOW)
        normal = Hook("normal", priority=HookPriority.NORMAL)
        
        # HIGH should be < NORMAL < LOW
        assert high < normal
        assert normal < low
        assert high < low
    
    def test_hook_disabled(self, sample_event):
        """Test disabled hook doesn't execute"""
        executed = False
        
        class TestHook(DocumentUploadHook):
            def on_document_uploaded(self, context):
                nonlocal executed
                executed = True
        
        hook = TestHook("test", enabled=False)
        context = HookContext("hook1", sample_event, "upload")
        
        hook.execute(context)
        
        assert executed is False
    
    def test_hook_method_name_conversion(self):
        """Test event type to method name conversion"""
        hook = Hook("test")
        
        assert hook._get_method_name(EventType.DOCUMENT_UPLOADED.value) == "on_document_uploaded"
        assert hook._get_method_name(EventType.EXTRACTION_COMPLETED.value) == "on_extraction_completed"
        assert hook._get_method_name(EventType.CODE_CREATED.value) == "on_code_created"


class TestHookExecution:
    """Test hook execution"""
    
    def test_hook_execution(self, sample_event):
        """Test executing a hook"""
        executed = False
        context_received = None
        
        class TestHook(DocumentUploadHook):
            def on_document_uploaded(self, context):
                nonlocal executed, context_received
                executed = True
                context_received = context
        
        hook = TestHook("test")
        context = HookContext("hook1", sample_event, "upload")
        
        hook.execute(context)
        
        assert executed is True
        assert context_received == context
    
    def test_hook_call_count(self, sample_event):
        """Test hook call count tracking"""
        class TestHook(DocumentUploadHook):
            def on_document_uploaded(self, context):
                pass
        
        hook = TestHook("test")
        assert hook.call_count == 0
        
        context = HookContext("hook1", sample_event, "upload")
        hook.execute(context)
        assert hook.call_count == 1
        
        hook.execute(context)
        assert hook.call_count == 2
    
    def test_hook_last_called_tracking(self, sample_event):
        """Test last_called timestamp tracking"""
        class TestHook(DocumentUploadHook):
            def on_document_uploaded(self, context):
                pass
        
        hook = TestHook("test")
        assert hook.last_called is None
        
        context = HookContext("hook1", sample_event, "upload")
        hook.execute(context)
        
        assert hook.last_called is not None
        assert isinstance(hook.last_called, datetime)
    
    def test_hook_error_tracking(self, sample_event):
        """Test error count tracking"""
        class BadHook(DocumentUploadHook):
            def on_document_uploaded(self, context):
                raise ValueError("Hook error")
        
        hook = BadHook("bad")
        context = HookContext("hook1", sample_event, "upload")
        
        with pytest.raises(ValueError):
            hook.execute(context)
        
        assert hook.error_count == 1
    
    def test_hook_result_in_context(self, sample_event):
        """Test hook can set result in context"""
        class TestHook(DocumentUploadHook):
            def on_document_uploaded(self, context):
                context.result = "processing_started"
                context.metadata["doc_id"] = context.event.data["document_id"]
        
        hook = TestHook("test")
        context = HookContext("hook1", sample_event, "upload")
        
        hook.execute(context)
        
        assert context.result == "processing_started"
        assert context.metadata["doc_id"] == "doc123"


class TestHookRegistry:
    """Test HookRegistry"""
    
    def test_registry_singleton(self):
        """Test registry is singleton"""
        HookRegistry._instance = None
        reg1 = HookRegistry.get_instance()
        reg2 = HookRegistry.get_instance()
        
        assert reg1 is reg2
    
    def test_register_hook(self, registry):
        """Test registering a hook"""
        hook = DocumentUploadHook("test_hook")
        hook_id = registry.register(hook)
        
        assert hook_id == hook.hook_id
        assert hook in registry.get_all_hooks()
    
    def test_register_hook_auto_detection(self, registry):
        """Test auto-detection of event types"""
        hook = DocumentUploadHook("test_hook")
        registry.register(hook)
        
        hooks = registry.get_hooks_for_event(EventType.DOCUMENT_UPLOADED.value)
        assert hook in hooks
    
    def test_register_multiple_event_types(self, registry):
        """Test registering hook for multiple events"""
        hook = ExtractionHook("test_hook")
        event_types = [
            EventType.EXTRACTION_STARTED.value,
            EventType.EXTRACTION_COMPLETED.value,
        ]
        registry.register(hook, event_types)
        
        for event_type in event_types:
            hooks = registry.get_hooks_for_event(event_type)
            assert hook in hooks
    
    def test_unregister_hook(self, registry):
        """Test unregistering a hook"""
        hook = DocumentUploadHook("test_hook")
        hook_id = registry.register(hook)
        
        result = registry.unregister(hook_id)
        assert result is True
        assert hook not in registry.get_all_hooks()
    
    def test_unregister_nonexistent(self, registry):
        """Test unregistering non-existent hook"""
        result = registry.unregister("nonexistent")
        assert result is False
    
    def test_hook_priority_ordering(self, registry, sample_event):
        """Test hooks are executed in priority order"""
        execution_order = []
        
        class TrackingHook(DocumentUploadHook):
            def __init__(self, name, priority):
                super().__init__(name, priority=priority)
                self.track_name = name
            
            def on_document_uploaded(self, context):
                execution_order.append(self.track_name)
        
        # Register in reverse priority order
        registry.register(TrackingHook("low", HookPriority.LOW))
        registry.register(TrackingHook("critical", HookPriority.CRITICAL))
        registry.register(TrackingHook("normal", HookPriority.NORMAL))
        registry.register(TrackingHook("high", HookPriority.HIGH))
        
        # Execute hooks
        registry.execute_hooks(sample_event)
        
        # Should execute in priority order: CRITICAL, HIGH, NORMAL, LOW
        assert execution_order == ["critical", "high", "normal", "low"]
    
    def test_execute_hooks(self, registry, sample_event):
        """Test executing all hooks for an event"""
        hook1 = DocumentUploadHook("hook1")
        hook2 = DocumentUploadHook("hook2")
        
        registry.register(hook1)
        registry.register(hook2)
        
        results = registry.execute_hooks(sample_event)
        
        assert results["hooks_executed"] == 2
        assert results["hooks_failed"] == 0
        assert len(results["hook_results"]) == 2
    
    def test_execute_hooks_with_failure(self, registry, sample_event):
        """Test executing hooks with error"""
        class GoodHook(DocumentUploadHook):
            def on_document_uploaded(self, context):
                context.metadata["good"] = True
        
        class BadHook(DocumentUploadHook):
            def on_document_uploaded(self, context):
                raise RuntimeError("Hook failed")
        
        registry.register(GoodHook("good"))
        registry.register(BadHook("bad", priority=HookPriority.LOW))
        
        results = registry.execute_hooks(sample_event)
        
        # Both should execute (good first due to priority)
        assert results["hooks_executed"] >= 1
        assert results["hooks_failed"] >= 1


class TestBuiltInHooks:
    """Test built-in hook implementations"""
    
    def test_auto_extraction_hook(self, sample_event):
        """Test AutoExtractionHook"""
        hook = AutoExtractionHook(auto_extract=True)
        context = HookContext("hook1", sample_event, "upload")
        
        hook.on_document_uploaded(context)
        
        assert context.metadata["extraction_queued"] is True
        assert context.metadata["extraction_for"] == "doc123"
    
    def test_auto_extraction_disabled(self, sample_event):
        """Test AutoExtractionHook when disabled"""
        hook = AutoExtractionHook(auto_extract=False)
        context = HookContext("hook1", sample_event, "upload")
        
        hook.on_document_uploaded(context)
        
        assert "extraction_queued" not in context.metadata
    
    def test_validation_hook_success(self):
        """Test ValidationHook with valid fields"""
        event = Event(
            event_type=EventType.EXTRACTION_COMPLETED.value,
            data={
                "extraction_id": "ext123",
                "fields": {"title": "Paper", "abstract": "...", "authors": ["A", "B"]}
            }
        )
        
        hook = ValidationHook()
        context = HookContext("hook1", event, "validate")
        
        hook.on_extraction_completed(context)
        
        assert context.metadata["validation_passed"] is True
    
    def test_validation_hook_missing_fields(self):
        """Test ValidationHook with missing fields"""
        event = Event(
            event_type=EventType.EXTRACTION_COMPLETED.value,
            data={
                "extraction_id": "ext123",
                "fields": {"title": "Paper"}  # Missing abstract, authors
            }
        )
        
        hook = ValidationHook()
        context = HookContext("hook1", event, "validate")
        
        hook.on_extraction_completed(context)
        
        assert context.metadata["validation_passed"] is False
        assert len(context.metadata["missing_fields"]) == 2
    
    def test_notification_hook_conditional(self):
        """Test NotificationHook conditional execution"""
        hook = NotificationHook(notify_on=[EventType.EXTRACTION_COMPLETED.value])
        
        # Should execute for EXTRACTION_COMPLETED
        context1 = HookContext(
            "hook1",
            Event(EventType.EXTRACTION_COMPLETED.value, {}),
            "notify"
        )
        assert hook.should_execute(context1) is True
        
        # Should not execute for DOCUMENT_UPLOADED
        context2 = HookContext(
            "hook1",
            Event(EventType.DOCUMENT_UPLOADED.value, {}),
            "notify"
        )
        assert hook.should_execute(context2) is False
    
    def test_audit_logging_hook(self, sample_event):
        """Test AuditLoggingHook"""
        hook = AuditLoggingHook()
        context = HookContext("hook1", sample_event, "upload")
        
        hook.execute(context)
        
        assert context.metadata["audit_logged"] is True


class TestHookStatistics:
    """Test hook statistics tracking"""
    
    def test_stats_initialization(self, registry):
        """Test initial statistics"""
        stats = registry.get_stats()
        
        assert stats["total_registered"] == 0
        assert stats["total_executed"] == 0
        assert stats["total_errors"] == 0
    
    def test_stats_registration(self, registry):
        """Test tracking registered hooks"""
        registry.register(DocumentUploadHook("hook1"))
        registry.register(DocumentUploadHook("hook2"))
        
        stats = registry.get_stats()
        assert stats["total_registered"] == 2
    
    def test_stats_execution(self, registry, sample_event):
        """Test tracking hook execution"""
        registry.register(DocumentUploadHook("hook1"))
        
        registry.execute_hooks(sample_event)
        
        stats = registry.get_stats()
        assert stats["total_executed"] == 1
    
    def test_stats_reset(self, registry):
        """Test resetting statistics"""
        registry.register(DocumentUploadHook("hook1"))
        registry.execute_hooks(Event(EventType.DOCUMENT_UPLOADED.value, {}))
        
        registry.reset_stats()
        
        stats = registry.get_stats()
        assert stats["total_executed"] == 0
        assert stats["total_errors"] == 0


class TestHookEnablement:
    """Test enabling/disabling hooks"""
    
    def test_enable_hook(self, registry):
        """Test enabling a hook"""
        hook = DocumentUploadHook("test_hook")
        hook_id = registry.register(hook)
        
        hook.enabled = False
        result = registry.enable_hook(hook_id)
        
        assert result is True
        assert hook.enabled is True
    
    def test_disable_hook(self, registry):
        """Test disabling a hook"""
        hook = DocumentUploadHook("test_hook")
        hook_id = registry.register(hook)
        
        result = registry.disable_hook(hook_id)
        
        assert result is True
        assert hook.enabled is False
    
    def test_enable_nonexistent_hook(self, registry):
        """Test enabling non-existent hook"""
        result = registry.enable_hook("nonexistent")
        assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
