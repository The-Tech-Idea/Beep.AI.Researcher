"""
Core module: Event Bus, Hooks, and Job Queue infrastructure.

This module provides the foundation for event-driven architecture and async processing.
"""

from .event_bus import (
    EventBus,
    Event,
    EventType,
    EventPriority,
    EventSubscription,
    get_event_bus,
    event_handler,
)

from .hooks import (
    Hook,
    HookType,
    HookPriority,
    HookContext,
    HookRegistry,
    DocumentUploadHook,
    ExtractionHook,
    CodeHook,
    ChatHook,
    TaskHook,
    ProjectHook,
    AutoExtractionHook,
    ValidationHook,
    NotificationHook,
    AuditLoggingHook,
    get_hook_registry,
    hook_decorator,
)

from .job_queue import (
    JobQueue,
    Job,
    JobStatus,
    JobType,
    JobPriority,
    JobResult,
    JobRegistry,
    get_job_queue,
    get_job_registry,
)

__all__ = [
    # EventBus
    "EventBus",
    "Event",
    "EventType",
    "EventPriority",
    "EventSubscription",
    "get_event_bus",
    "event_handler",
    # Hooks
    "Hook",
    "HookType",
    "HookPriority",
    "HookContext",
    "HookRegistry",
    "DocumentUploadHook",
    "ExtractionHook",
    "CodeHook",
    "ChatHook",
    "TaskHook",
    "ProjectHook",
    "AutoExtractionHook",
    "ValidationHook",
    "NotificationHook",
    "AuditLoggingHook",
    "get_hook_registry",
    "hook_decorator",
    # Job Queue
    "JobQueue",
    "Job",
    "JobStatus",
    "JobType",
    "JobPriority",
    "JobResult",
    "JobRegistry",
    "get_job_queue",
    "get_job_registry",
]
