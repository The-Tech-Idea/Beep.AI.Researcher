"""
Hook System for Beep.AI.Researcher

Provides extensible plugin framework for customizing application behavior.
Hooks allow custom code to run at specific points without modifying core code.

Built on top of EventBus for event-driven hook execution.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4
from functools import wraps

from app.core.event_bus import Event, EventType, get_event_bus


logger = logging.getLogger(__name__)


class HookType(Enum):
    """Hook execution type"""
    
    BEFORE = "before"  # Runs before operation
    AFTER = "after"    # Runs after operation
    AROUND = "around"  # Wraps entire operation


class HookPriority(Enum):
    """Hook execution priority (lower number = earlier execution)"""
    
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    
    def __lt__(self, other):
        if not isinstance(other, HookPriority):
            return NotImplemented
        return self.value < other.value


@dataclass
class HookContext:
    """Context passed to hooks with event data"""
    
    hook_id: str
    event: Event
    operation_name: str
    context_data: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[Exception] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary"""
        return {
            "hook_id": self.hook_id,
            "event_type": self.event.event_type,
            "operation": self.operation_name,
            "context_data": self.context_data,
            "result": str(self.result) if self.result else None,
            "error": str(self.error) if self.error else None,
            "timestamp": self.timestamp.isoformat(),
        }


class Hook(ABC):
    """
    Base class for all hooks.
    
    Subclass to create custom hooks for specific events.
    
    Example:
        class MyDocumentHook(Hook):
            def on_document_uploaded(self, context: HookContext):
                logger.info(f"Document uploaded: {context.event.data}")
    """
    
    def __init__(
        self,
        name: str,
        hook_type: HookType = HookType.AFTER,
        priority: HookPriority = HookPriority.NORMAL,
        enabled: bool = True
    ):
        """
        Initialize hook.
        
        Args:
            name: Human-readable hook name
            hook_type: When hook runs (before/after/around)
            priority: Execution order relative to other hooks
            enabled: Whether hook is active
        """
        
        self.hook_id = str(uuid4())
        self.name = name
        self.hook_type = hook_type
        self.priority = priority
        self.enabled = enabled
        self.call_count = 0
        self.last_called = None
        self.error_count = 0
        
        logger.debug(f"Hook initialized: {self.name} ({self.hook_id})")
    
    def execute(self, context: HookContext) -> Any:
        """
        Execute the appropriate hook method for this context.
        
        Args:
            context: Hook context with event and operation data
        
        Returns:
            Result from hook execution (may modify context)
        """
        
        if not self.enabled:
            return
        
        try:
            # Find and call appropriate method based on event type
            method_name = self._get_method_name(context.event.event_type)
            
            if hasattr(self, method_name):
                method = getattr(self, method_name)
                
                # Update stats
                self.call_count += 1
                self.last_called = datetime.now(timezone.utc)
                
                logger.debug(
                    f"Executing hook method: {self.name}.{method_name}"
                )
                
                return method(context)
        
        except Exception as e:
            self.error_count += 1
            context.error = e
            logger.error(
                f"Error in hook {self.name}: {e}",
                exc_info=True
            )
            raise
    
    def should_execute(self, context: HookContext) -> bool:
        """
        Override to implement conditional hook execution.
        
        Args:
            context: Hook context
        
        Returns:
            True if hook should execute, False otherwise
        """
        return True
    
    def _get_method_name(self, event_type: str) -> str:
        """Convert event type to hook method name"""
        
        # Map event types to method names
        event_to_method = {
            EventType.DOCUMENT_UPLOADED.value: "on_document_uploaded",
            EventType.DOCUMENT_DELETED.value: "on_document_deleted",
            EventType.DOCUMENT_PROCESSED.value: "on_document_processed",
            EventType.EXTRACTION_STARTED.value: "on_extraction_started",
            EventType.EXTRACTION_COMPLETED.value: "on_extraction_completed",
            EventType.EXTRACTION_FAILED.value: "on_extraction_failed",
            EventType.CODE_CREATED.value: "on_code_created",
            EventType.CODE_UPDATED.value: "on_code_updated",
            EventType.CODE_DELETED.value: "on_code_deleted",
            EventType.CODE_MERGED.value: "on_code_merged",
            EventType.CHAT_MESSAGE_SENT.value: "on_chat_message_sent",
            EventType.CHAT_MESSAGE_RECEIVED.value: "on_chat_message_received",
            EventType.TASK_CREATED.value: "on_task_created",
            EventType.TASK_STATUS_CHANGED.value: "on_task_status_changed",
            EventType.TASK_COMPLETED.value: "on_task_completed",
            EventType.PROJECT_CREATED.value: "on_project_created",
            EventType.PROJECT_UPDATED.value: "on_project_updated",
            EventType.PROJECT_DELETED.value: "on_project_deleted",
        }
        
        return event_to_method.get(event_type, "on_unknown_event")
    
    def __lt__(self, other) -> bool:
        """Enable priority-based sorting"""
        if not isinstance(other, Hook):
            return NotImplemented
        return self.priority < other.priority
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name} (priority={self.priority.name})>"


class DocumentUploadHook(Hook):
    """Hook for document upload events"""
    
    def on_document_uploaded(self, context: HookContext):
        """Called after document is uploaded"""
        pass


class ExtractionHook(Hook):
    """Hook for extraction events"""
    
    def on_extraction_started(self, context: HookContext):
        """Called when extraction starts"""
        pass
    
    def on_extraction_completed(self, context: HookContext):
        """Called when extraction completes"""
        pass
    
    def on_extraction_failed(self, context: HookContext):
        """Called when extraction fails"""
        pass


class CodeHook(Hook):
    """Hook for code snippet events"""
    
    def on_code_created(self, context: HookContext):
        """Called when code is created"""
        pass
    
    def on_code_updated(self, context: HookContext):
        """Called when code is updated"""
        pass
    
    def on_code_deleted(self, context: HookContext):
        """Called when code is deleted"""
        pass
    
    def on_code_merged(self, context: HookContext):
        """Called when codes are merged"""
        pass


class ChatHook(Hook):
    """Hook for chat events"""
    
    def on_chat_message_sent(self, context: HookContext):
        """Called when user sends message"""
        pass
    
    def on_chat_message_received(self, context: HookContext):
        """Called when bot sends message"""
        pass


class TaskHook(Hook):
    """Hook for task events"""
    
    def on_task_created(self, context: HookContext):
        """Called when task created"""
        pass
    
    def on_task_status_changed(self, context: HookContext):
        """Called when task status changes"""
        pass
    
    def on_task_completed(self, context: HookContext):
        """Called when task completes"""
        pass


class ProjectHook(Hook):
    """Hook for project events"""
    
    def on_project_created(self, context: HookContext):
        """Called when project created"""
        pass
    
    def on_project_updated(self, context: HookContext):
        """Called when project updated"""
        pass
    
    def on_project_deleted(self, context: HookContext):
        """Called when project deleted"""
        pass


# ============================================================================
# BUILT-IN HOOKS
# ============================================================================

class AutoExtractionHook(DocumentUploadHook):
    """Automatically trigger extraction on document upload"""
    
    def __init__(self, enabled: bool = True, auto_extract: bool = True):
        super().__init__(
            name="AutoExtractionHook",
            hook_type=HookType.AFTER,
            priority=HookPriority.HIGH,
            enabled=enabled
        )
        self.auto_extract = auto_extract
    
    def on_document_uploaded(self, context: HookContext):
        """Trigger extraction on document upload"""
        
        if not self.auto_extract:
            return
        
        doc_id = context.event.data.get("document_id")
        project_id = context.event.data.get("project_id")
        
        logger.info(f"AutoExtractionHook: Queuing extraction for {doc_id}")
        
        # This would be replaced with actual extraction service call
        # extraction_service.queue_extraction(doc_id)
        
        context.metadata["extraction_queued"] = True
        context.metadata["extraction_for"] = doc_id


class ValidationHook(ExtractionHook):
    """Validate extracted fields match expected schema"""
    
    def __init__(self, enabled: bool = True):
        super().__init__(
            name="ValidationHook",
            hook_type=HookType.AFTER,
            priority=HookPriority.NORMAL,
            enabled=enabled
        )
    
    def on_extraction_completed(self, context: HookContext):
        """Validate extraction result"""
        
        extraction_id = context.event.data.get("extraction_id")
        fields = context.event.data.get("fields", {})
        
        # Validate required fields
        required_fields = {"title", "abstract", "authors"}
        missing = required_fields - set(fields.keys())
        
        if missing:
            logger.warning(
                f"ValidationHook: Missing fields in {extraction_id}: {missing}"
            )
            context.metadata["validation_passed"] = False
            context.metadata["missing_fields"] = list(missing)
        else:
            logger.info(f"ValidationHook: All required fields present in {extraction_id}")
            context.metadata["validation_passed"] = True


class NotificationHook(Hook):
    """Send notifications for important events"""
    
    def __init__(self, enabled: bool = True, notify_on: Optional[List[str]] = None):
        super().__init__(
            name="NotificationHook",
            hook_type=HookType.AFTER,
            priority=HookPriority.LOW,
            enabled=enabled
        )
        # Events to notify on
        self.notify_on = notify_on or [
            EventType.EXTRACTION_COMPLETED.value,
            EventType.TASK_COMPLETED.value,
            EventType.SYSTEM_ERROR.value,
        ]
    
    def should_execute(self, context: HookContext) -> bool:
        """Only notify for configured events"""
        return context.event.event_type in self.notify_on
    
    def execute(self, context: HookContext) -> Any:
        """Send notification"""
        
        if not self.should_execute(context):
            return
        
        event_type = context.event.event_type
        logger.info(
            f"NotificationHook: Would send notification for event: {event_type}"
        )
        
        # This would integrate with actual notification service
        # notification_service.send_notification({
        #     "title": f"Event: {event_type}",
        #     "message": json.dumps(context.event.data),
        #     "priority": "high"
        # })
        
        context.metadata["notification_sent"] = True


class AuditLoggingHook(Hook):
    """Log all operations for compliance and auditing"""
    
    def __init__(self, enabled: bool = True, log_file: Optional[str] = None):
        super().__init__(
            name="AuditLoggingHook",
            hook_type=HookType.AFTER,
            priority=HookPriority.NORMAL,
            enabled=enabled
        )
        self.log_file = log_file
    
    def execute(self, context: HookContext) -> Any:
        """Log operation to audit trail"""
        
        audit_entry = {
            "timestamp": context.timestamp.isoformat(),
            "event_type": context.event.event_type,
            "source": context.event.source,
            "data": context.event.data,
            "success": context.error is None,
        }
        
        logger.info(f"AuditLoggingHook: {audit_entry}")
        
        # This would integrate with audit logging service
        # audit_service.log(audit_entry)
        
        context.metadata["audit_logged"] = True


# ============================================================================
# HOOK REGISTRY
# ============================================================================

class HookRegistry:
    """
    Central registry for managing all hooks in the application.
    
    Provides hook registration, discovery, and execution.
    """
    
    _instance = None
    _lock = __import__('threading').Lock()
    
    def __init__(self):
        """Initialize hook registry"""
        
        self._hooks: Dict[str, List[Hook]] = {}
        self._all_hooks: List[Hook] = []
        self._hook_stats = {
            "total_registered": 0,
            "total_executed": 0,
            "total_errors": 0,
        }
        
        logger.info("HookRegistry initialized")
    
    @classmethod
    def get_instance(cls) -> "HookRegistry":
        """Get singleton instance"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def register(self, hook: Hook, event_types: Optional[List[str]] = None) -> str:
        """
        Register a hook for one or more event types.
        
        Args:
            hook: Hook instance to register
            event_types: List of event types to trigger on (auto-detect if None)
        
        Returns:
            Hook ID
        """
        
        if event_types is None:
            # Auto-detect which events this hook handles
            event_types = self._detect_event_types(hook)
        
        for event_type in event_types:
            if event_type not in self._hooks:
                self._hooks[event_type] = []
            
            # Keep hooks sorted by priority
            self._hooks[event_type].append(hook)
            self._hooks[event_type].sort()
        
        self._all_hooks.append(hook)
        self._hook_stats["total_registered"] += 1
        
        logger.info(
            f"Registered hook {hook.name} for events: {event_types}"
        )
        
        return hook.hook_id
    
    def unregister(self, hook_id: str) -> bool:
        """
        Unregister a hook by ID.
        
        Args:
            hook_id: Hook ID to unregister
        
        Returns:
            True if unregistered, False if not found
        """
        
        # Find hook
        hook = None
        for h in self._all_hooks:
            if h.hook_id == hook_id:
                hook = h
                break
        
        if hook is None:
            return False
        
        # Remove from all event types
        for event_type in list(self._hooks.keys()):
            self._hooks[event_type] = [
                h for h in self._hooks[event_type] if h.hook_id != hook_id
            ]
            
            # Clean up empty lists
            if not self._hooks[event_type]:
                del self._hooks[event_type]
        
        self._all_hooks.remove(hook)
        
        logger.info(f"Unregistered hook: {hook.name}")
        
        return True
    
    def execute_hooks(
        self,
        event: Event,
        operation_name: str = "default",
        context_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute all hooks for an event.
        
        Args:
            event: Event to process
            operation_name: Name of operation being performed
            context_data: Additional context for hooks
        
        Returns:
            Dict with hook execution results
        """
        
        hooks = self._hooks.get(event.event_type, [])
        
        if not hooks:
            return {"hooks_executed": 0, "hooks_failed": 0}
        
        results = {
            "hooks_executed": 0,
            "hooks_failed": 0,
            "hook_results": [],
            "event_type": event.event_type,
        }
        
        # Create hook context
        context = HookContext(
            hook_id="registry",
            event=event,
            operation_name=operation_name,
            context_data=context_data or {}
        )
        
        # Execute hooks in priority order
        for hook in hooks:
            try:
                if not hook.should_execute(context):
                    logger.debug(
                        f"Hook {hook.name} skipped due to conditional check"
                    )
                    continue
                
                hook.execute(context)
                results["hooks_executed"] += 1
                results["hook_results"].append({
                    "hook": hook.name,
                    "success": True,
                    "metadata": context.metadata
                })
                
                self._hook_stats["total_executed"] += 1
                
            except Exception as e:
                results["hooks_failed"] += 1
                results["hook_results"].append({
                    "hook": hook.name,
                    "success": False,
                    "error": str(e)
                })
                
                self._hook_stats["total_errors"] += 1
                logger.error(f"Hook {hook.name} execution failed: {e}")
        
        return results
    
    def get_hooks_for_event(self, event_type: str) -> List[Hook]:
        """Get all hooks registered for an event type"""
        return self._hooks.get(event_type, []).copy()
    
    def get_all_hooks(self) -> List[Hook]:
        """Get all registered hooks"""
        return self._all_hooks.copy()
    
    def enable_hook(self, hook_id: str) -> bool:
        """Enable a hook"""
        for hook in self._all_hooks:
            if hook.hook_id == hook_id:
                hook.enabled = True
                logger.info(f"Enabled hook: {hook.name}")
                return True
        return False
    
    def disable_hook(self, hook_id: str) -> bool:
        """Disable a hook"""
        for hook in self._all_hooks:
            if hook.hook_id == hook_id:
                hook.enabled = False
                logger.info(f"Disabled hook: {hook.name}")
                return True
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        return self._hook_stats.copy()
    
    def reset_stats(self) -> None:
        """Reset statistics"""
        for key in self._hook_stats:
            self._hook_stats[key] = 0
        logger.info("Hook statistics reset")
    
    def _detect_event_types(self, hook: Hook) -> List[str]:
        """Auto-detect which event types a hook handles"""
        
        event_types = []
        
        # Check for hook methods
        for event_type in EventType:
            method_name = hook._get_method_name(event_type.value)
            if hasattr(hook, method_name):
                event_types.append(event_type.value)
        
        return event_types if event_types else [EventType.DOCUMENT_UPLOADED.value]


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_hook_registry() -> HookRegistry:
    """Get global hook registry instance"""
    return HookRegistry.get_instance()


def hook_decorator(
    hook_id: str,
    event_types: Optional[List[str]] = None,
    priority: HookPriority = HookPriority.NORMAL
):
    """
    Decorator to register function as hook.
    
    Usage:
        @hook_decorator("my_hook", [EventType.DOCUMENT_UPLOADED.value])
        def my_hook_function(context: HookContext):
            print(f"Document uploaded: {context.event.data}")
    """
    
    def decorator(func: Callable) -> Callable:
        
        # Create hook from function
        class DynamicHook(Hook):
            def __init__(self):
                super().__init__(
                    name=hook_id,
                    priority=priority
                )
            
            def on_document_uploaded(self, context: HookContext):
                return func(context)
            
            def on_extraction_completed(self, context: HookContext):
                return func(context)
            
            # Add other methods as needed...
        
        # Register hook
        registry = get_hook_registry()
        hook = DynamicHook()
        registry.register(hook, event_types)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return wrapper
    
    return decorator
