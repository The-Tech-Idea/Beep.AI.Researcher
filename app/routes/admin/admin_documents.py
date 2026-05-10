"""Admin document management routes."""
from flask import jsonify, redirect, render_template, request, url_for, flash
from flask_login import current_user, login_required

from app.database import db
from app.models.core import User
from app.models.researcher import ResearcherDocument
from app.routes.admin_routes import admin_bp, admin_required
from app.routes.route_entity_lookup import get_entity_or_404
from app.services.document_manager_service import document_manager_service
from app.services.storage import StorageError, get_storage_backend


@admin_bp.route('/documents')
@login_required
@admin_required
def document_management():
    """Admin: browse all documents across all users / projects."""
    from app.models.researcher import ResearchProject

    page = request.args.get('page', 1, type=int)
    per_page = 50
    user_filter = request.args.get('user_id', type=int)
    tenant_filter = request.args.get('tenant_id', type=int)
    project_filter = request.args.get('project_id', type=int)
    search = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    file_type = request.args.get('file_type', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    sort = request.args.get('sort', 'created_desc').strip() or 'created_desc'

    result = document_manager_service.search_documents(
        page=page,
        per_page=per_page,
        user_id=user_filter,
        tenant_id=tenant_filter,
        project_id=project_filter,
        search=search,
        status=status_filter,
        file_type=file_type,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
    )

    all_users = User.query.order_by(User.username).all()
    all_projects = ResearchProject.query.order_by(ResearchProject.name).all()
    from app.models.tenant import Tenant
    all_tenants = Tenant.query.order_by(Tenant.name).all()

    return render_template(
        'admin/document_management.html',
        docs=result.pagination.items,
        pagination=result.pagination,
        total_count=result.total_count,
        total_storage=result.total_storage,
        all_users=all_users,
        all_tenants=all_tenants,
        all_projects=all_projects,
        user_filter=user_filter,
        tenant_filter=tenant_filter,
        project_filter=project_filter,
        search=search,
        status_filter=status_filter,
        file_type=file_type,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
    )


@admin_bp.route('/documents/<int:doc_id>/details')
@login_required
@admin_required
def admin_document_details(doc_id):
    """Admin document detail JSON for table row expansion."""

    return jsonify(document_manager_service.get_document_details(doc_id))


@admin_bp.route('/documents/<int:doc_id>/download')
@login_required
@admin_required
def admin_document_download(doc_id):
    """Admin download of a managed document through the active storage backend."""

    doc = get_entity_or_404(ResearcherDocument, doc_id)
    try:
        return get_storage_backend().send_file_response(
            doc.file_path,
            doc.filename,
            doc.mime_type,
        )
    except StorageError as exc:
        flash(f'Could not download document: {exc}', 'danger')
        return redirect(request.referrer or url_for('admin.document_management'))


@admin_bp.route('/documents/<int:doc_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_document_delete(doc_id):
    """Admin force-delete a document."""

    try:
        filename = document_manager_service.delete_document(doc_id, actor_user_id=current_user.id)
        flash(f'Document "{filename}" deleted.', 'success')
    except Exception as exc:
        db.session.rollback()
        flash(f'Could not delete document: {exc}', 'danger')

    return redirect(request.referrer or url_for('admin.document_management'))


@admin_bp.route('/documents/<int:doc_id>/archive', methods=['POST'])
@login_required
@admin_required
def admin_document_archive(doc_id):
    """Admin archive a document without deleting the stored object."""

    try:
        filename = document_manager_service.archive_document(doc_id, actor_user_id=current_user.id)
        flash(f'Document "{filename}" archived.', 'success')
    except Exception as exc:
        db.session.rollback()
        flash(f'Could not archive document: {exc}', 'danger')

    return redirect(request.referrer or url_for('admin.document_management'))


@admin_bp.route('/documents/<int:doc_id>/restore', methods=['POST'])
@login_required
@admin_required
def admin_document_restore(doc_id):
    """Admin restore an archived document."""

    try:
        filename = document_manager_service.restore_document(doc_id, actor_user_id=current_user.id)
        flash(f'Document "{filename}" restored.', 'success')
    except Exception as exc:
        db.session.rollback()
        flash(f'Could not restore document: {exc}', 'danger')

    return redirect(request.referrer or url_for('admin.document_management'))


@admin_bp.route('/documents/bulk-action', methods=['POST'])
@login_required
@admin_required
def admin_document_bulk_action():
    """Admin bulk actions for selected documents."""

    raw_ids = request.form.get('document_ids', '')
    action = request.form.get('action', '').strip().lower()
    doc_ids = []
    for value in raw_ids.split(','):
        try:
            doc_id = int(value.strip())
        except ValueError:
            continue
        if doc_id > 0:
            doc_ids.append(doc_id)

    if not doc_ids:
        flash('Select at least one document.', 'warning')
        return redirect(request.referrer or url_for('admin.document_management'))

    if action not in {'repair', 'delete', 'archive', 'restore'}:
        flash('Choose a supported bulk action.', 'danger')
        return redirect(request.referrer or url_for('admin.document_management'))

    result = document_manager_service.bulk_action(
        doc_ids=doc_ids,
        action=action,
        actor_user_id=current_user.id,
    )
    document_manager_service.record_admin_job(
        user_id=current_user.id,
        name=f"Bulk document {action}",
        action=action,
        doc_ids=doc_ids,
        result=result,
    )
    category = 'success' if result['failed'] == 0 else 'warning'
    flash(
        f"Bulk {action}: {result['succeeded']} succeeded, {result['failed']} failed.",
        category,
    )
    return redirect(request.referrer or url_for('admin.document_management'))


@admin_bp.route('/documents/<int:doc_id>/recalculate', methods=['POST'])
@login_required
@admin_required
def admin_document_recalculate(doc_id):
    """Admin repair: reload storage object, rerun extraction, and retry AI Server sync."""

    try:
        result = document_manager_service.repair_document(
            doc_id,
            sync_to_rag=True,
            actor_user_id=current_user.id,
        )
        doc = result["document"]
        rag_sync = result["rag_sync"]
        document_manager_service.record_admin_job(
            user_id=current_user.id,
            name=f"Repair document {doc.filename}",
            action="repair",
            doc_ids=[doc.id],
            result={
                "requested": 1,
                "succeeded": 1 if not result["rag_sync"].get("attempted") or result["rag_sync"].get("synced") else 0,
                "failed": 0 if not result["rag_sync"].get("attempted") or result["rag_sync"].get("synced") else 1,
                "errors": [] if not result["rag_sync"].get("attempted") or result["rag_sync"].get("synced") else [
                    {"document_id": doc.id, "error": result["rag_sync"].get("message") or "AI Server sync failed"}
                ],
            },
        )
        if rag_sync.get("synced"):
            flash(f'Document "{doc.filename}" repaired and indexed for AI search.', 'success')
        else:
            flash(f'Document "{doc.filename}" repaired. {rag_sync.get("message")}', 'warning')
    except Exception as exc:
        db.session.rollback()
        flash(f'Could not repair document: {exc}', 'danger')

    return redirect(request.referrer or url_for('admin.document_management'))


@admin_bp.route('/document-manager/jobs')
@login_required
@admin_required
def admin_document_manager_jobs():
    """Admin document manager jobs page."""

    page = request.args.get('page', 1, type=int)
    pagination = document_manager_service.list_admin_jobs(page=page, per_page=50)
    return render_template(
        'admin/document_manager_jobs.html',
        jobs=pagination.items,
        pagination=pagination,
    )
