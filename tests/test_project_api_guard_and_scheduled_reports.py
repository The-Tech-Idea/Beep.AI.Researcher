from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
import uuid

from flask import g
from flask_login import login_user

from app.database import db
from app.models.core import Role, User
from app.models.rbac import Permission, RBACRole, UserRole
from app.models.researcher import ProjectMember, ResearchProject, ScheduledReport
from app.routes.observability import job_queue_stats
from app.routes.project_api_guard import (
    current_user_can_access_project,
    ensure_admin_session,
    ensure_project_session_access,
)
from app.services import scheduled_report_service


def _create_core_role(name: str) -> Role:
    role = Role.query.filter_by(name=name).first()
    if role is None:
        role = Role(name=name)
        db.session.add(role)
        db.session.flush()
    return role


def _create_user(*, role_name: str = "Member") -> User:
    role = _create_core_role(role_name) if role_name else None
    token = uuid.uuid4().hex[:8]
    user = User(
        username=f"guard_user_{token}",
        email=f"guard_user_{token}@example.com",
        role_id=role.id if role else None,
        is_active=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


def _assign_project_member(project_id: int, user_id: int, role: str) -> None:
    db.session.add(ProjectMember(project_id=project_id, user_id=user_id, role=role))
    db.session.commit()


def _assign_project_permission(user_id: int, project_id: int, permission: str) -> None:
    role = RBACRole(
        name=f"guard_role_{uuid.uuid4().hex[:8]}",
        permissions=[permission],
        is_builtin=False,
    )
    db.session.add(role)
    db.session.flush()
    db.session.add(
        UserRole(
            user_id=str(user_id),
            role_id=role.id,
            scope="project",
            scope_id=str(project_id),
        )
    )
    db.session.commit()


class TestProjectApiGuard:
    def test_project_guard_requires_authenticated_session(self, app_context, test_project):
        with app_context.test_request_context(f"/projects/{test_project.id}/reports/scheduled", method="GET"):
            response = ensure_project_session_access(test_project.id)

        assert response[1] == 401
        assert response[0].get_json()["message"] == "Authentication required"

    def test_project_guard_denies_non_member_without_permission(self, app_context, test_project):
        user = _create_user()
        with app_context.test_request_context(f"/projects/{test_project.id}/reports/scheduled", method="GET"):
            login_user(user)
            response = ensure_project_session_access(test_project.id)

        assert response[1] == 403
        assert response[0].get_json()["message"] == "Project access denied"

    def test_project_guard_allows_viewer_member_read_access(self, app_context, test_project):
        user = _create_user()
        project = db.session.get(ResearchProject, test_project.id)
        _assign_project_member(test_project.id, user.id, "viewer")

        with app_context.test_request_context(f"/projects/{test_project.id}/reports/scheduled", method="GET"):
            login_user(user)
            assert current_user_can_access_project(project, write=False) is True
            response = ensure_project_session_access(test_project.id)
            assert response is None
            assert g.current_project.id == test_project.id
            assert g.current_project_write_access is False

    def test_project_guard_denies_viewer_member_write_access(self, app_context, test_project):
        user = _create_user()
        project = db.session.get(ResearchProject, test_project.id)
        _assign_project_member(test_project.id, user.id, "viewer")

        with app_context.test_request_context(f"/projects/{test_project.id}/reports/schedule", method="POST"):
            login_user(user)
            assert current_user_can_access_project(project, write=True) is False
            response = ensure_project_session_access(test_project.id)

        assert response[1] == 403
        assert response[0].get_json()["message"] == "Project access denied"

    def test_project_guard_allows_contributor_member_write_access(self, app_context, test_project):
        user = _create_user()
        project = db.session.get(ResearchProject, test_project.id)
        _assign_project_member(test_project.id, user.id, "contributor")

        with app_context.test_request_context(f"/projects/{test_project.id}/reports/schedule", method="POST"):
            login_user(user)
            assert current_user_can_access_project(project, write=True) is True
            response = ensure_project_session_access(test_project.id)
            assert response is None
            payload, status_code = scheduled_report_service.create_scheduled_report(
                project,
                {
                    "name": "Weekly digest",
                    "schedule_cron": "0 9 * * 1",
                    "recipients": ["team@example.com"],
                },
            )

        assert status_code == 201
        assert payload["name"] == "Weekly digest"
        assert payload["recipients"] == ["team@example.com"]
        assert ScheduledReport.query.filter_by(project_id=test_project.id, name="Weekly digest").count() == 1

    def test_project_guard_allows_project_scoped_write_permission(self, app_context, test_project):
        user = _create_user()
        project = db.session.get(ResearchProject, test_project.id)
        _assign_project_permission(user.id, test_project.id, Permission.PROJECT_WRITE)

        with app_context.test_request_context(f"/projects/{test_project.id}/reports/schedule", method="POST"):
            login_user(user)
            assert current_user_can_access_project(project, write=True) is True
            response = ensure_project_session_access(test_project.id)
            assert response is None
            payload, status_code = scheduled_report_service.create_scheduled_report(
                project,
                {"name": "Scoped write", "schedule_cron": "0 9 * * 1"},
            )

        assert status_code == 201
        assert payload["name"] == "Scoped write"

    def test_admin_guard_denies_non_admin_session(self, app_context):
        user = _create_user(role_name="Member")
        with app_context.test_request_context("/projects/job-queue-stats", method="GET"):
            login_user(user)
            response = ensure_admin_session()

        assert response[1] == 403
        assert response[0].get_json()["message"] == "Administrator access required"

    def test_admin_guard_allows_admin_session_and_queue_route(self, app_context):
        user = _create_user(role_name="Admin")
        fake_queue = SimpleNamespace(
            get_job_history=lambda limit=1000: [
                SimpleNamespace(status="pending"),
                SimpleNamespace(status="completed"),
                SimpleNamespace(status="completed"),
            ],
            get_stats=lambda: {"jobs_pending": 1, "jobs_running": 2, "workers_available": 3},
        )

        with app_context.test_request_context("/projects/job-queue-stats", method="GET"):
            login_user(user)
            assert ensure_admin_session() is None
            with patch("app.routes.observability.get_job_queue", return_value=fake_queue):
                response = job_queue_stats()

        payload = response.get_json()
        assert payload["queue_depth"] == 1
        assert payload["jobs_running"] == 2
        assert payload["workers_available"] == 3
        assert payload["by_status"] == {"pending": 1, "completed": 2}


class TestScheduledReportDispatch:
    def test_dispatch_due_reports_queues_matching_cron_reports(self, app_context, test_project):
        report = ScheduledReport(
            project_id=test_project.id,
            name="Due report",
            schedule_cron="0 9 * * *",
            recipients_json='["team@example.com"]',
            is_active=True,
        )
        skipped = ScheduledReport(
            project_id=test_project.id,
            name="Skipped report",
            schedule_cron="15 9 * * *",
            recipients_json='["team@example.com"]',
            is_active=True,
        )
        already_run = ScheduledReport(
            project_id=test_project.id,
            name="Already run",
            schedule_cron="0 9 * * *",
            recipients_json='["team@example.com"]',
            is_active=True,
            last_run_at=datetime(2026, 4, 13, 9, 0, 0),
        )
        db.session.add_all([report, skipped, already_run])
        db.session.commit()

        queued_jobs = []

        class FakeQueue:
            def create_job(self, job_type, input_data, priority=None, metadata=None):
                queued_jobs.append(
                    {
                        "job_type": job_type,
                        "input_data": input_data,
                        "priority": priority,
                        "metadata": metadata,
                    }
                )
                return SimpleNamespace(job_id=f"job-{len(queued_jobs)}")

        with patch("app.services.scheduled_report_service.get_job_queue", return_value=FakeQueue()):
            job_ids = scheduled_report_service.dispatch_due_reports(datetime(2026, 4, 13, 9, 0, 30))

        db.session.refresh(report)
        db.session.refresh(skipped)
        db.session.refresh(already_run)

        assert job_ids == ["job-1"]
        assert len(queued_jobs) == 1
        assert queued_jobs[0]["job_type"] == "generate_report"
        assert queued_jobs[0]["input_data"]["scheduled_report_id"] == report.id
        assert queued_jobs[0]["metadata"]["trigger_source"] == "cron"
        assert report.last_run_at == datetime(2026, 4, 13, 9, 0, 0)
        assert skipped.last_run_at is None
        assert already_run.last_run_at == datetime(2026, 4, 13, 9, 0, 0)

    def test_dispatch_event_driven_reports_only_queues_on_upload_reports(self, app_context, test_project):
        on_upload = ScheduledReport(
            project_id=test_project.id,
            name="On upload report",
            schedule_cron="on_upload",
            recipients_json='["team@example.com"]',
            is_active=True,
        )
        cron_report = ScheduledReport(
            project_id=test_project.id,
            name="Cron report",
            schedule_cron="0 9 * * *",
            recipients_json='["team@example.com"]',
            is_active=True,
        )
        inactive = ScheduledReport(
            project_id=test_project.id,
            name="Inactive on upload",
            schedule_cron="on_upload",
            recipients_json='["team@example.com"]',
            is_active=False,
        )
        db.session.add_all([on_upload, cron_report, inactive])
        db.session.commit()

        queued_jobs = []

        class FakeQueue:
            def create_job(self, job_type, input_data, priority=None, metadata=None):
                queued_jobs.append(
                    {
                        "job_type": job_type,
                        "input_data": input_data,
                        "priority": priority,
                        "metadata": metadata,
                    }
                )
                return SimpleNamespace(job_id=f"event-job-{len(queued_jobs)}")

        with patch("app.services.scheduled_report_service.get_job_queue", return_value=FakeQueue()):
            job_ids = scheduled_report_service.dispatch_event_driven_reports(test_project.id, trigger_source="document.uploaded")

        db.session.refresh(on_upload)
        db.session.refresh(cron_report)
        db.session.refresh(inactive)

        assert job_ids == ["event-job-1"]
        assert len(queued_jobs) == 1
        assert queued_jobs[0]["job_type"] == "generate_report"
        assert queued_jobs[0]["input_data"]["scheduled_report_id"] == on_upload.id
        assert queued_jobs[0]["metadata"]["trigger_source"] == "document.uploaded"
        assert on_upload.last_run_at is not None
        assert cron_report.last_run_at is None
        assert inactive.last_run_at is None