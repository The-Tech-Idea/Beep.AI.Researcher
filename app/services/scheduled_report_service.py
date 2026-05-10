from __future__ import annotations

import json
import logging
import re
import threading
from datetime import timedelta
from typing import Any

from app.core.event_bus import EventType, get_event_bus
from app.core.job_queue import JobPriority, JobType, get_job_queue, get_job_registry
from app.core.time_utils import utcnow_naive
from app.database import db
from app.models.core import User
from app.models.researcher import ResearchProject, ResearchReportDraft, ScheduledReport
from app.services.email_service import is_configured as email_is_configured
from app.services.email_service import send_email

logger = logging.getLogger(__name__)

_DISPATCH_INTERVAL_SECONDS = 60
_RUNTIME_LOCK = threading.Lock()
_RUNTIME_APP = None
_DISPATCHER_THREAD = None
_STOP_EVENT = threading.Event()
_EVENT_HANDLERS_REGISTERED = False


def serialize_scheduled_report(report: ScheduledReport) -> dict[str, Any]:
    try:
        recipients = json.loads(report.recipients_json or "[]")
    except (TypeError, json.JSONDecodeError):
        recipients = []

    payload = report.to_dict()
    payload["last_sent_at"] = payload.get("last_run_at")
    payload["recipients"] = recipients
    payload["report_config_json"] = report.report_config_json or "{}"
    return payload


def _normalize_recipients(raw_recipients) -> list[str]:
    if isinstance(raw_recipients, str):
        parts = raw_recipients.split(",")
    elif isinstance(raw_recipients, list):
        parts = raw_recipients
    else:
        parts = []

    recipients = []
    for part in parts:
        email = str(part or "").strip()
        if email and email not in recipients:
            recipients.append(email)
    return recipients


def _validate_cron_expression(schedule_cron: str) -> tuple[bool, str | None]:
    if schedule_cron == "on_upload":
        return True, None

    parts = (schedule_cron or "").split()
    if len(parts) != 5:
        return False, "schedule_cron must use five cron fields or 'on_upload'"

    ranges = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 7))
    for expression, bounds in zip(parts, ranges):
        try:
            _validate_cron_field(expression, *bounds)
        except ValueError as exc:
            return False, str(exc)
    return True, None


def _validate_cron_field(expression: str, minimum: int, maximum: int) -> None:
    for part in expression.split(","):
        part = part.strip()
        if not part:
            raise ValueError("Invalid empty cron field")
        base, _, step_str = part.partition("/")
        if step_str:
            step = int(step_str)
            if step <= 0:
                raise ValueError(f"Invalid cron step: {part}")
        if base == "*":
            continue
        if "-" in base:
            start_str, end_str = base.split("-", 1)
            start = int(start_str)
            end = int(end_str)
            if start < minimum or end > maximum or start > end:
                raise ValueError(f"Cron range out of bounds: {part}")
            continue
        value = int(base)
        if value < minimum or value > maximum:
            raise ValueError(f"Cron value out of bounds: {part}")


def _cron_weekday(current_time: datetime) -> int:
    return (current_time.weekday() + 1) % 7


def _field_matches(expression: str, value: int, minimum: int, maximum: int) -> bool:
    for part in expression.split(","):
        base, _, step_str = part.partition("/")
        step = int(step_str) if step_str else 1
        if base == "*":
            return (value - minimum) % step == 0
        if "-" in base:
            start_str, end_str = base.split("-", 1)
            start = int(start_str)
            end = int(end_str)
            if start <= value <= end and (value - start) % step == 0:
                return True
            continue
        number = int(base)
        if number == value:
            return True
        if step_str and number <= value <= maximum and (value - number) % step == 0:
            return True
    return False


def _schedule_matches(report: ScheduledReport, current_time: datetime) -> bool:
    if report.schedule_cron == "on_upload":
        return False

    minute, hour, day_of_month, month, day_of_week = report.schedule_cron.split()
    return all(
        (
            _field_matches(minute, current_time.minute, 0, 59),
            _field_matches(hour, current_time.hour, 0, 23),
            _field_matches(day_of_month, current_time.day, 1, 31),
            _field_matches(month, current_time.month, 1, 12),
            _field_matches(day_of_week, _cron_weekday(current_time), 0, 7),
        )
    )


def _minute_floor(current_time: datetime) -> datetime:
    return current_time.replace(second=0, microsecond=0)


def _is_due(report: ScheduledReport, current_time: datetime) -> bool:
    if not report.is_active or not _schedule_matches(report, current_time):
        return False

    current_slot = _minute_floor(current_time)
    last_run_at = _minute_floor(report.last_run_at) if report.last_run_at else None
    return last_run_at is None or last_run_at < current_slot


def create_scheduled_report(project, data: dict[str, Any]):
    name = (data.get("name") or "").strip()
    schedule_cron = (data.get("schedule_cron") or "0 9 * * 1").strip()
    recipients = _normalize_recipients(data.get("recipients", []))

    if not name:
        return {"error": "name required"}, 400

    is_valid, error_message = _validate_cron_expression(schedule_cron)
    if not is_valid:
        return {"error": error_message}, 400

    report_config = data.get("report_config_json", "{}")
    if isinstance(report_config, dict):
        report_config = json.dumps(report_config)

    report = ScheduledReport(
        project_id=project.id,
        name=name,
        schedule_cron=schedule_cron,
        recipients_json=json.dumps(recipients),
        report_config_json=report_config,
        is_active=bool(data.get("is_active", True)),
    )
    db.session.add(report)
    db.session.commit()
    return serialize_scheduled_report(report), 201


def list_scheduled_reports(project):
    reports = (
        ScheduledReport.query.filter_by(project_id=project.id)
        .order_by(ScheduledReport.created_at.desc())
        .all()
    )
    return {"reports": [serialize_scheduled_report(report) for report in reports]}, 200


def queue_scheduled_report(
    report: ScheduledReport, *, trigger_source: str
) -> str | None:
    queue = get_job_queue()
    job = queue.create_job(
        JobType.GENERATE_REPORT.value,
        {
            "scheduled_report_id": report.id,
            "project_id": report.project_id,
            "trigger_source": trigger_source,
        },
        priority=JobPriority.HIGH,
        metadata={
            "project_id": report.project_id,
            "scheduled_report_id": report.id,
            "trigger_source": trigger_source,
        },
    )
    return job.job_id


def dispatch_due_reports(now: datetime | None = None) -> list[str]:
    current_time = now or utcnow_naive()
    queued_job_ids = []
    dirty = False
    for report in ScheduledReport.query.filter_by(is_active=True).all():
        if not _is_due(report, current_time):
            continue
        job_id = queue_scheduled_report(report, trigger_source="cron")
        if job_id:
            queued_job_ids.append(job_id)
            report.last_run_at = _minute_floor(current_time)
            dirty = True
    if dirty:
        db.session.commit()
    return queued_job_ids


def dispatch_event_driven_reports(project_id: int, *, trigger_source: str) -> list[str]:
    queued_job_ids = []
    current_time = utcnow_naive()
    reports = ScheduledReport.query.filter_by(
        project_id=project_id, is_active=True, schedule_cron="on_upload"
    ).all()
    for report in reports:
        job_id = queue_scheduled_report(report, trigger_source=trigger_source)
        if job_id:
            queued_job_ids.append(job_id)
            report.last_run_at = _minute_floor(current_time)
    if queued_job_ids:
        db.session.commit()
    return queued_job_ids


def _project_content_event_handler(event) -> None:
    data = getattr(event, "data", {}) or {}
    project_id = data.get("project_id")
    if not project_id:
        return
    try:
        dispatch_event_driven_reports(
            int(project_id), trigger_source=getattr(event, "event_type", "event")
        )
    except Exception:
        logger.exception(
            "Failed to dispatch event-driven scheduled reports for project %s",
            project_id,
        )


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    text = re.sub(r"<\s*br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _render_report_body(project: ResearchProject, report_name: str) -> tuple[str, str]:
    draft = ResearchReportDraft.query.filter_by(project_id=project.id).first()
    if draft and draft.html_content:
        html_body = draft.html_content
        plain_body = _html_to_text(draft.html_content)
    else:
        html_body = (
            f"<h1>{project.name}</h1>"
            f"<p>{project.description or 'Scheduled project report generated by Beep.AI.Researcher.'}</p>"
        )
        plain_body = f"{project.name}\n\n{project.description or 'Scheduled project report generated by Beep.AI.Researcher.'}"

    header = f"{report_name}\nGenerated at {utcnow_naive().isoformat()}"
    plain_message = f"{header}\n\n{plain_body}".strip()
    html_message = f"<p><strong>{report_name}</strong><br>Generated at {utcnow_naive().isoformat()}</p>{html_body}"
    return plain_message, html_message


def handle_generate_report_job(input_data: dict[str, Any]):
    if _RUNTIME_APP is None:
        raise RuntimeError("Scheduled report runtime has not been initialized")

    with _RUNTIME_APP.app_context():
        scheduled_report_id = input_data.get("scheduled_report_id")
        project_id = input_data.get("project_id")
        report_name = input_data.get("report_type") or "Scheduled report"
        recipients = []

        scheduled_report = None
        if scheduled_report_id:
            scheduled_report = db.session.get(ScheduledReport, int(scheduled_report_id))
            if scheduled_report is None:
                return {"delivered": False, "reason": "scheduled_report_missing"}
            project_id = scheduled_report.project_id
            report_name = scheduled_report.name
            recipients = _normalize_recipients(scheduled_report.recipients_json)

        if not project_id:
            raise ValueError("project_id is required for generate_report jobs")

        project = db.session.get(ResearchProject, int(project_id))
        if project is None:
            return {"delivered": False, "reason": "project_missing"}

        if not recipients:
            return {
                "delivered": False,
                "reason": "no_recipients",
                "project_id": project.id,
            }

        subject = f"{project.name}: {report_name}"
        plain_body, html_body = _render_report_body(project, report_name)

        if not email_is_configured():
            return {
                "delivered": False,
                "reason": "email_unconfigured",
                "project_id": project.id,
            }

        success, error = send_email(
            subject, plain_body, recipients, html_body=html_body
        )
        if success and scheduled_report is not None:
            scheduled_report.last_run_at = utcnow_naive()
            db.session.commit()

        return {
            "delivered": success,
            "error": error,
            "project_id": project.id,
            "scheduled_report_id": scheduled_report.id if scheduled_report else None,
            "recipient_count": len(recipients),
        }


def _dispatcher_loop(app) -> None:
    consecutive_errors = 0
    max_backoff = 300  # 5 minutes
    while not _STOP_EVENT.wait(_DISPATCH_INTERVAL_SECONDS):
        try:
            with app.app_context():
                dispatch_due_reports()
                consecutive_errors = 0
        except Exception:
            consecutive_errors += 1
            if consecutive_errors <= 3:
                logger.warning(
                    "Scheduled report dispatcher failed (attempt %d)",
                    consecutive_errors,
                )
            elif consecutive_errors % 10 == 1:
                logger.error(
                    "Scheduled report dispatcher still failing after %d attempts",
                    consecutive_errors,
                )
            # Exponential backoff: 1m, 2m, 4m, ... up to max_backoff
            backoff = min(
                _DISPATCH_INTERVAL_SECONDS * (2 ** (consecutive_errors - 1)),
                max_backoff,
            )
            _STOP_EVENT.wait(backoff)


def initialize_scheduled_report_runtime(app, *, start_dispatcher: bool = True) -> None:
    global _RUNTIME_APP
    global _DISPATCHER_THREAD
    global _EVENT_HANDLERS_REGISTERED

    with _RUNTIME_LOCK:
        _RUNTIME_APP = app
        registry = get_job_registry()
        if not registry.has_handler(JobType.GENERATE_REPORT.value):
            registry.register(JobType.GENERATE_REPORT.value, handle_generate_report_job)

        if not _EVENT_HANDLERS_REGISTERED:
            try:
                event_bus = get_event_bus()
                event_bus.subscribe(
                    EventType.DOCUMENT_UPLOADED.value, _project_content_event_handler
                )
                event_bus.subscribe("import.completed", _project_content_event_handler)
                _EVENT_HANDLERS_REGISTERED = True
            except Exception:
                logger.exception("Failed to register scheduled report event handlers")

        should_start = (
            start_dispatcher
            and _DISPATCHER_THREAD is None
            and not app.config.get("TESTING", False)
        )
        if should_start:
            _STOP_EVENT.clear()
            _DISPATCHER_THREAD = threading.Thread(
                target=_dispatcher_loop,
                args=(app,),
                daemon=True,
                name="scheduled-report-dispatcher",
            )
            _DISPATCHER_THREAD.start()
