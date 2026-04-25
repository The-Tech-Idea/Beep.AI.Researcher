"""Background job handler for PDF downloads and document update."""
import os
import traceback
from pathlib import Path
from urllib.parse import urlparse
from tempfile import NamedTemporaryFile
from datetime import datetime
from app.core.time_utils import utcnow_naive

try:
    import requests
except Exception:
    requests = None

from app.database import db
from app.models.researcher.researcher_documents import ResearcherDocument
from app.models.researcher.library_sources import SourceImportLog
from app.routes.integration import publish_event


def handle_pdf_download(job):
    """Job handler that downloads a PDF and updates the corresponding Document record.

    Expects job.input_data to contain: document_id, pdf_url, project_id
    """
    data = getattr(job, 'input_data', {}) or {}
    document_id = data.get('document_id')
    pdf_url = data.get('pdf_url')
    project_id = data.get('project_id')

    if not document_id or not pdf_url:
        return {'success': False, 'error': 'Missing document_id or pdf_url'}

    if requests is None:
        return {'success': False, 'error': 'requests library not available'}

    try:
        import_log_id = data.get('import_log_id')
        doc = ResearcherDocument.query.get(int(document_id))
        if not doc:
            error_msg = 'Document not found'
            # Update import log if tracking
            if import_log_id:
                try:
                    log = SourceImportLog.query.get(int(import_log_id))
                    if log:
                        log.status = 'failed'
                        log.error_message = error_msg
                        db.session.add(log)
                        db.session.commit()
                except Exception:
                    db.session.rollback()
            publish_event('import.failed', {'document_id': document_id, 'error': error_msg}, source='pdf_download_handler')
            return {'success': False, 'error': error_msg}

        # Prepare storage path
        storage_root = Path('data') / 'projects' / str(project_id) / 'documents'
        storage_root.mkdir(parents=True, exist_ok=True)

        # Download PDF to a temp file
        with requests.get(pdf_url, stream=True, timeout=30) as r:
            r.raise_for_status()
            # Derive filename
            parsed = urlparse(pdf_url)
            name = Path(parsed.path).name or f"doc_{document_id}.pdf"
            target_path = storage_root / name
            with open(target_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        # Update document metadata
        doc.file_path = str(target_path)
        try:
            doc.file_size = target_path.stat().st_size
        except Exception:
            doc.file_size = 0
        doc.mime_type = 'application/pdf'
        db.session.add(doc)
        db.session.commit()

        # Update SourceImportLog (by ID or most recent pending)
        try:
            log = SourceImportLog.query.get(int(import_log_id)) if import_log_id else None
            if not log:
                log = SourceImportLog.query.filter_by(status='pending').order_by(SourceImportLog.imported_at.desc()).first()
            if log:
                log.documents_imported = (log.documents_imported or 0) + 1
                log.status = 'completed'
                log.completed_at = utcnow_naive()
                db.session.add(log)
                db.session.commit()
        except Exception:
            db.session.rollback()

        # Publish import.completed event
        publish_event(
            'import.completed',
            {'document_id': document_id, 'project_id': project_id, 'file_path': doc.file_path},
            source='pdf_download_handler'
        )
        return {'success': True, 'file_path': doc.file_path, 'file_size': doc.file_size}

    except Exception as e:
        traceback.print_exc()
        # Publish import.failed event and update log
        publish_event('import.failed', {'document_id': document_id, 'error': str(e)}, source='pdf_download_handler')
        try:
            import_log_id = data.get('import_log_id')
            log = SourceImportLog.query.get(int(import_log_id)) if import_log_id else None
            if not log:
                log = SourceImportLog.query.filter_by(status='pending').order_by(SourceImportLog.imported_at.desc()).first()
            if log:
                log.status = 'failed'
                log.error_message = str(e)
                log.completed_at = utcnow_naive()
                db.session.add(log)
                db.session.commit()
        except Exception:
            db.session.rollback()
        return {'success': False, 'error': str(e)}
