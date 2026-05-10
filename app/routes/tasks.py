"""Task routes - lightweight ResearchTask endpoints."""

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.database import db
from app.models.researcher import ResearchProject, ResearchTask, TaskNotification
from app.routes.route_entity_lookup import get_entity_or_404, get_project_or_404
from app.services.task_notifications import emit_task_notification

tasks_bp = Blueprint("tasks", __name__)


def _task_to_dict(task):
    return {
        "id": task.id,
        "project_id": task.project_id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "document_id": task.document_id,
        "code_id": task.code_id,
        "created_by_id": task.created_by_id,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


def _clean_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


@tasks_bp.route("/<int:project_id>/tasks", methods=["GET"])
@login_required
def list_tasks(project_id):
    project = get_project_or_404(project_id)
    q = ResearchTask.query.filter_by(project_id=project.id)
    document_id = request.args.get("document_id", type=int)
    code_id = request.args.get("code_id", type=int)
    if document_id:
        q = q.filter_by(document_id=document_id)
    if code_id:
        q = q.filter_by(code_id=code_id)
    tasks = q.order_by(ResearchTask.created_at.desc()).all()
    return jsonify({"tasks": [_task_to_dict(t) for t in tasks]})


@tasks_bp.route("/<int:project_id>/tasks", methods=["POST"])
@login_required
def create_task(project_id):
    project = get_project_or_404(project_id)
    data = request.get_json() or {}
    title = _clean_text(data.get("title"))
    if not title:
        return jsonify({"error": "title required"}), 400
    task = ResearchTask(
        project_id=project.id,
        title=title,
        description=_clean_text(data.get("description")),
        status=_clean_text(data.get("status")) or "todo",
        priority=_clean_text(data.get("priority")) or "normal",
        document_id=data.get("document_id"),
        code_id=data.get("code_id"),
        created_by_id=current_user.id if current_user.is_authenticated else None,
    )
    db.session.add(task)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to create task"}), 500
    emit_task_notification(
        task,
        "created",
        actor_id=current_user.id if current_user.is_authenticated else None,
    )
    return jsonify(_task_to_dict(task)), 201


@tasks_bp.route("/<int:project_id>/tasks/<int:task_id>", methods=["PUT"])
@login_required
def update_task(project_id, task_id):
    project = get_project_or_404(project_id)
    task = ResearchTask.query.filter_by(
        project_id=project.id, id=task_id
    ).first_or_404()
    data = request.get_json() or {}
    old_status = task.status
    if "title" in data:
        title = _clean_text(data.get("title"))
        if title:
            task.title = title
    if "description" in data:
        task.description = _clean_text(data.get("description"))
    if "status" in data:
        status = _clean_text(data.get("status"))
        if status:
            task.status = status
    if "priority" in data:
        priority = _clean_text(data.get("priority"))
        if priority:
            task.priority = priority
    if "document_id" in data:
        task.document_id = data.get("document_id")
    if "code_id" in data:
        task.code_id = data.get("code_id")
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to update task"}), 500
    if old_status != task.status:
        emit_task_notification(
            task,
            f"status moved to {task.status}",
            actor_id=current_user.id if current_user.is_authenticated else None,
        )
    return jsonify(_task_to_dict(task))


@tasks_bp.route("/<int:project_id>/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def delete_task(project_id, task_id):
    project = get_project_or_404(project_id)
    task = ResearchTask.query.filter_by(
        project_id=project.id, id=task_id
    ).first_or_404()
    db.session.delete(task)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to delete task"}), 500
    return jsonify({"ok": True}), 204


@tasks_bp.route("/<int:project_id>/notifications", methods=["GET"])
@login_required
def list_task_notifications(project_id):
    project = get_project_or_404(project_id)
    notifications = (
        TaskNotification.query.join(ResearchTask)
        .filter(ResearchTask.project_id == project.id)
        .order_by(TaskNotification.created_at.desc())
        .limit(20)
        .all()
    )
    return jsonify({"notifications": [_notification_to_dict(n) for n in notifications]})


def _notification_to_dict(notification):
    return {
        "id": notification.id,
        "task_id": notification.task_id,
        "message": notification.message,
        "event": notification.event,
        "created_at": notification.created_at.isoformat()
        if notification.created_at
        else None,
        "channel": notification.channel,
    }
