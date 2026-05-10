"""Phase B.4 — Observability / Monitoring Routes (project-scoped).

Provides per-project ingestion health, cache hit/miss stats, and an
admin-only job-queue stats endpoint protected by the shared session guard.
"""

from datetime import timedelta
from flask import Blueprint, request, jsonify
from flask_login import login_required
from sqlalchemy import func

from app.core.job_queue import get_job_queue
from app.core.time_utils import utcnow_naive
from app.database import db
from app.models.researcher import ResearchProject, ResearcherDocument
from app.models.researcher.search_cache import SearchCache
from app.routes.project_api_guard import (
    guard_project_blueprint,
    get_guarded_project_or_404 as get_project_or_404,
)

observability_bp = Blueprint("observability", __name__)


# ─────────────────────────────────────────────────────────────
#  Per-project ingestion health
# ─────────────────────────────────────────────────────────────


@observability_bp.route("/<int:project_id>/health", methods=["GET"])
@login_required
def project_health(project_id):
    """Return ingestion health indicators for a project.

    Query params:
      hours  — lookback window (default 24)
    """
    project = get_project_or_404(project_id)
    hours = request.args.get("hours", 24, type=int)
    since = utcnow_naive() - timedelta(hours=hours)

    total_docs = ResearcherDocument.query.filter_by(project_id=project.id).count()

    recent_docs = ResearcherDocument.query.filter(
        ResearcherDocument.project_id == project.id,
        ResearcherDocument.created_at >= since,
    ).count()

    # Count documents by status if the column exists
    status_breakdown = {}
    try:
        rows = (
            db.session.query(
                ResearcherDocument.status, func.count(ResearcherDocument.id)
            )
            .filter(ResearcherDocument.project_id == project.id)
            .group_by(ResearcherDocument.status)
            .all()
        )
        status_breakdown = {status or "unknown": cnt for status, cnt in rows}
    except Exception:
        pass

    # Cache stats for this project
    cache_entries = SearchCache.query.filter_by(project_id=project.id).count()
    expired_cache = SearchCache.query.filter(
        SearchCache.project_id == project.id,
        SearchCache.expires_at < utcnow_naive(),
    ).count()

    return jsonify(
        {
            "project_id": project_id,
            "project_name": project.name,
            "window_hours": hours,
            "total_documents": total_docs,
            "documents_ingested_in_window": recent_docs,
            "document_status_breakdown": status_breakdown,
            "cache_entries_total": cache_entries,
            "cache_entries_expired": expired_cache,
            "checked_at": utcnow_naive().isoformat(),
        }
    )


# ─────────────────────────────────────────────────────────────
#  Cache hit/miss stats
# ─────────────────────────────────────────────────────────────


@observability_bp.route("/<int:project_id>/cache-stats", methods=["GET"])
@login_required
def project_cache_stats(project_id):
    """Return SearchCache hit/miss statistics for a project.

    Query params:
      provider — filter by specific provider (optional)
    """
    project = get_project_or_404(project_id)
    provider_filter = request.args.get("provider")

    q = SearchCache.query.filter_by(project_id=project.id)
    if provider_filter:
        q = q.filter_by(provider=provider_filter)

    entries = q.all()

    total_entries = len(entries)
    total_hits = sum(e.hit_count or 0 for e in entries)
    valid_entries = [
        e for e in entries if e.expires_at and e.expires_at > utcnow_naive()
    ]
    expired_entries = total_entries - len(valid_entries)

    # Per-provider breakdown
    by_provider: dict = {}
    for e in entries:
        prov = e.provider or "unknown"
        if prov not in by_provider:
            by_provider[prov] = {"entries": 0, "total_hits": 0, "result_count": 0}
        by_provider[prov]["entries"] += 1
        by_provider[prov]["total_hits"] += e.hit_count or 0
        by_provider[prov]["result_count"] += e.result_count or 0

    return jsonify(
        {
            "project_id": project_id,
            "total_cache_entries": total_entries,
            "active_entries": len(valid_entries),
            "expired_entries": expired_entries,
            "total_cache_hits": total_hits,
            "by_provider": by_provider,
            "checked_at": utcnow_naive().isoformat(),
        }
    )


# ─────────────────────────────────────────────────────────────
#  Admin: job-queue stats  /admin/job-queue-stats
# ─────────────────────────────────────────────────────────────


@observability_bp.route("/job-queue-stats", methods=["GET"])
@login_required
def job_queue_stats():
    """Admin endpoint: return queue depth and task state counts.

    Pulls from the SQLite-backed job queue runtime used by background tasks.
    """
    try:
        queue = get_job_queue()
        history = queue.get_job_history(limit=1000)
        by_status = {}
        for job in history:
            by_status[job.status] = by_status.get(job.status, 0) + 1
        stats = queue.get_stats()

        return jsonify(
            {
                "queue_depth": stats.get("jobs_pending", 0),
                "total_tasks": len(history),
                "by_status": by_status,
                "jobs_running": stats.get("jobs_running", 0),
                "workers_available": stats.get("workers_available", 0),
                "checked_at": utcnow_naive().isoformat(),
            }
        )
    except Exception as exc:
        return jsonify(
            {
                "queue_depth": 0,
                "total_tasks": 0,
                "by_status": {},
                "warning": f"task table not available: {exc}",
                "checked_at": utcnow_naive().isoformat(),
            }
        )


guard_project_blueprint(observability_bp, admin_endpoints={"job_queue_stats"})
