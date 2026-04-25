"""Notification helpers for ResearchTask lifecycle events."""
from app.core.time_utils import utcnow_naive
from typing import Iterable, Optional

from app.database import db
from app.models.researcher import TaskNotification, ResearchTask
from app.services.email_service import is_configured, send_email


def emit_task_notification(task: ResearchTask, event: str, actor_id: Optional[int] = None,
                           email_addresses: Optional[Iterable[str]] = None, send_email_alert: bool = False) -> TaskNotification:
    """Create a persistent notification for a task event."""
    title = task.title or 'Task'
    message = f"{title} - {event.capitalize()}"
    notification = TaskNotification(
        task_id=task.id,
        event=event,
        message=message,
        channel='system',
        created_by_id=actor_id,
        created_at=utcnow_naive(),
    )
    db.session.add(notification)

    if send_email_alert and email_addresses and is_configured():
        subject = f"[Researcher] Task update: {title}"
        success, _ = send_email(subject, message, list(email_addresses))
        if success:
            notification.channel = 'email'
            notification.delivered_at = utcnow_naive()
    db.session.commit()
    return notification
