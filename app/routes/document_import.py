"""Routes for importing search results into project documents (Phase 2.4)."""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, select

from app.database import db
from app.models.researcher import ResearchProject, ResearcherDocument
from app.models.researcher.library_sources import SourceImportLog, LibrarySource
from app.routes.integration import queue_job, JobType, JobPriority, publish_event
from app.core.event_bus import EventType
from app.core.job_queue import get_job_queue
from app.core.time_utils import utcnow_naive
from app.routes.route_entity_lookup import get_entity, get_entity_or_404

document_import_bp = Blueprint('document_import', __name__)


def _get_project_or_404(project_id):
    return get_entity_or_404(ResearchProject, project_id)


@document_import_bp.route('/<int:project_id>/web-search/<string:result_id>/import', methods=['POST'])
@login_required
def import_search_result(project_id, result_id):
    """Import a single search result into the project's documents.

    Expects JSON body with at least: filename (optional), url, pdf_url (optional), source_type.
    """
    payload = request.get_json(force=True) or {}
    url = payload.get('url')
    pdf_url = payload.get('pdf_url')
    filename = payload.get('filename') or f"import_{result_id}.pdf" if pdf_url else payload.get('title', f"import_{result_id}")
    source_type = payload.get('source_type') or payload.get('source') or 'web_search'

    # Create ResearcherDocument placeholder (file_path empty until PDF download)
    doc = ResearcherDocument(
        project_id=project_id,
        filename=filename,
        file_path=payload.get('file_path') or '',
        mime_type=payload.get('mime_type') or ('application/pdf' if pdf_url else 'text/plain'),
        file_size=0,
        text_content=payload.get('abstract') or None,
        source_type=source_type,
        source_id=result_id,
        source_url=url,
        imported_at=utcnow_naive()
    )
    db.session.add(doc)
    db.session.commit()

    # Record import log (one-off) - mark as pending until PDF download completes
    import_log = None
    source_id_cfg = payload.get('library_source_id')
    if source_id_cfg:
        try:
            source = get_entity(LibrarySource, int(source_id_cfg))
            if source is not None:
                import_log = SourceImportLog(
                    source_id=source.id,
                    query=payload.get('query') or '',
                    results_found=1,
                    documents_imported=0 if pdf_url else 1,
                    status='pending' if pdf_url else 'completed',
                    import_duration_seconds=0.0
                )
                db.session.add(import_log)
                db.session.commit()
        except Exception:
            db.session.rollback()
            import_log = None

    # Publish import.started event
    publish_event(
        'import.started',
        {'project_id': project_id, 'result_id': result_id, 'user_id': current_user.id},
        source='document_import_route'
    )
    
    # If there's a PDF URL, queue a PDF download job
    job_id = None
    if pdf_url:
        job_payload = {
            'document_id': str(doc.id),
            'pdf_url': pdf_url,
            'project_id': project_id,
            'user_id': getattr(current_user, 'id', None),
            'import_log_id': import_log.id if import_log else None,
        }
        # Queue a dedicated PDF download job
        try:
            from app.core.job_queue import JobType as CoreJobType
            job_id = queue_job(CoreJobType.PDF_DOWNLOAD.value, job_payload, priority=JobPriority.NORMAL)
        except Exception:
            # Fallback to generic extract document job if PDF job type unavailable
            job_id = queue_job(JobType.EXTRACT_DOCUMENT.value, job_payload, priority=JobPriority.NORMAL)
    else:
        # Publish import.completed if no async job
        publish_event(
            'import.completed',
            {'project_id': project_id, 'document_id': doc.id, 'result_id': result_id},
            source='document_import_route'
        )

    return jsonify({'success': True, 'document': doc.to_dict(), 'job_id': job_id}), 201


@document_import_bp.route('/<int:project_id>/web-search/batch-import', methods=['POST'])
@login_required
def batch_import(project_id):
    """Batch import multiple search results. Accepts JSON array of result objects."""
    payload = request.get_json(force=True) or {}
    items = payload.get('items') or []
    job_payload = {
        'project_id': project_id,
        'items': items,
        'user_id': getattr(current_user, 'id', None),
    }
    # Queue a batch job for processing imports
    job_id = queue_job('web_search_batch_import', job_payload, priority=JobPriority.NORMAL)
    return jsonify({'success': True, 'job_id': job_id}), 202


@document_import_bp.route('/<int:project_id>/jobs/<string:job_id>', methods=['GET'])
@login_required
def get_job_status(project_id, job_id):
    """Get status and progress of an async import job.

    Returns:
        - job_id, status (pending|running|completed|failed|cancelled)
        - progress info: retry_count, error_message
        - timing: created_at, started_at, completed_at
        - output_data when completed
    """
    _get_project_or_404(project_id)

    queue = get_job_queue()
    job = queue.get_job(job_id)
    if job is None:
        return jsonify({'error': 'Job not found', 'job_id': job_id}), 404

    # Verify the job belongs to this project (via input_data.project_id)
    job_project = job.input_data.get('project_id')
    if job_project is not None and str(job_project) != str(project_id):
        return jsonify({'error': 'Job does not belong to this project'}), 403

    return jsonify({
        'job_id': job.job_id,
        'job_type': job.job_type,
        'status': job.status,
        'priority': job.priority,
        'retry_count': job.retry_count,
        'max_retries': job.max_retries,
        'error_message': job.error_message,
        'created_at': job.created_at,
        'started_at': job.started_at,
        'completed_at': job.completed_at,
        'output_data': job.output_data if job.status == 'completed' else {},
        'logs': job.logs[-20:] if job.logs else [],  # last 20 log lines
    })


@document_import_bp.route('/<int:project_id>/import-stats', methods=['GET'])
@login_required
def import_stats(project_id):
    """Aggregate import statistics for a project.

    Returns:
        - total documents imported, broken down by source_type
        - import log summary: total, pending, completed, failed
        - top sources by import volume
    """
    _get_project_or_404(project_id)

    # Document counts by source_type
    doc_counts = db.session.query(
        ResearcherDocument.source_type,
        func.count(ResearcherDocument.id).label('count')
    ).filter_by(project_id=project_id).group_by(
        ResearcherDocument.source_type
    ).all()

    by_source_type = {row.source_type or 'unknown': row.count for row in doc_counts}
    total_documents = sum(by_source_type.values())

    # Import log stats (via LibrarySource → SourceImportLog)
    source_ids = select(LibrarySource.id).filter_by(project_id=project_id)
    log_stats = db.session.query(
        SourceImportLog.status,
        func.count(SourceImportLog.id).label('count'),
        func.sum(SourceImportLog.documents_imported).label('docs_imported'),
    ).filter(SourceImportLog.source_id.in_(source_ids)).group_by(
        SourceImportLog.status
    ).all()

    logs_by_status = {}
    total_logs_imported = 0
    for row in log_stats:
        logs_by_status[row.status] = row.count
        total_logs_imported += (row.docs_imported or 0)

    # Top sources by import volume
    top_sources = db.session.query(
        LibrarySource.name,
        LibrarySource.source_type,
        LibrarySource.import_count,
    ).filter_by(project_id=project_id).order_by(
        LibrarySource.import_count.desc()
    ).limit(5).all()

    return jsonify({
        'project_id': project_id,
        'total_documents': total_documents,
        'docs_by_source_type': [
            {'source_type': st, 'count': cnt} for st, cnt in by_source_type.items()
        ],
        'import_log_stats': [
            {'status': st, 'count': cnt} for st, cnt in logs_by_status.items()
        ],
        'top_sources': [
            {'name': s.name, 'source_type': s.source_type, 'import_count': s.import_count}
            for s in top_sources
        ],
    })
