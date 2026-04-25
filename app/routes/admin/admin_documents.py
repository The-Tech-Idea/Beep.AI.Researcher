"""Admin document management routes."""
from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required

from app.database import db
from app.models.core import User
from app.routes.route_entity_lookup import get_entity_or_404
from app.routes.admin_routes import admin_bp, admin_required


@admin_bp.route('/documents')
@login_required
@admin_required
def document_management():
    """Admin: browse all documents across all users / projects."""
    from app.models.researcher import ResearcherDocument, ResearchProject

    page           = request.args.get('page', 1, type=int)
    per_page       = 50
    user_filter    = request.args.get('user_id', type=int)
    project_filter = request.args.get('project_id', type=int)
    search         = request.args.get('q', '').strip()

    q = ResearcherDocument.query
    if user_filter:
        q = q.join(ResearchProject).filter(ResearchProject.user_id == user_filter)
    if project_filter:
        q = q.filter(ResearcherDocument.project_id == project_filter)
    if search:
        q = q.filter(ResearcherDocument.filename.ilike(f'%{search}%'))

    pagination = q.order_by(ResearcherDocument.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False,
    )

    from sqlalchemy import func as sqlfunc
    total_count   = ResearcherDocument.query.count()
    total_storage = db.session.query(sqlfunc.sum(ResearcherDocument.file_size)).scalar() or 0

    all_users    = User.query.order_by(User.username).all()
    all_projects = ResearchProject.query.order_by(ResearchProject.name).all()

    return render_template(
        'admin/document_management.html',
        docs=pagination.items,
        pagination=pagination,
        total_count=total_count,
        total_storage=total_storage,
        all_users=all_users,
        all_projects=all_projects,
        user_filter=user_filter,
        project_filter=project_filter,
        search=search,
    )


@admin_bp.route('/documents/<int:doc_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_document_delete(doc_id):
    """Admin force-delete a document."""
    from app.models.researcher import ResearcherDocument
    from app.services.storage import get_storage_backend, StorageError
    from app.services.quota_service import quota_service

    doc = get_entity_or_404(ResearcherDocument, doc_id)
    try:
        backend = get_storage_backend()
        backend.delete(doc.storage_key or doc.filename)
    except StorageError:
        pass  # already gone — still clean up DB record

    file_size = doc.file_size or 0
    db.session.delete(doc)
    db.session.commit()

    try:
        quota_service.record_delete(doc.user_id, file_size)
    except Exception:
        pass

    flash(f'Document "{doc.filename}" deleted.', 'success')
    return redirect(request.referrer or url_for('admin.document_management'))
