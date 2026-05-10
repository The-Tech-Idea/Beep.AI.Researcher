"""Admin storage management routes."""
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.routes.admin_routes import admin_bp, admin_required
from app.services.document_manager_service import document_manager_service
from app.services.storage.storage_manager_service import storage_manager_service


@admin_bp.route('/storage')
@login_required
@admin_required
def storage_management():
    """Storage backend health, capacity, and consistency overview."""

    health = storage_manager_service.health()
    usage = storage_manager_service.usage_summary()
    consistency_issues = storage_manager_service.consistency_scan(limit=250)
    return render_template(
        'admin/storage_management.html',
        health=health,
        usage=usage,
        consistency_issues=consistency_issues,
    )


@admin_bp.route('/storage/documents/<int:doc_id>/repair-size', methods=['POST'])
@login_required
@admin_required
def storage_repair_document_size(doc_id):
    """Repair DB size metadata for one stored document."""

    try:
        actual_size = storage_manager_service.repair_document_size(
            doc_id,
            actor_user_id=current_user.id,
        )
        flash(f'Document size metadata repaired: {actual_size:,} bytes.', 'success')
    except Exception as exc:
        flash(f'Could not repair document size metadata: {exc}', 'danger')
    return redirect(request.referrer or url_for('admin.storage_management'))


@admin_bp.route('/storage/documents/<int:doc_id>/delete-broken', methods=['POST'])
@login_required
@admin_required
def storage_delete_broken_document(doc_id):
    """Delete a broken document record from the storage consistency page."""

    try:
        filename = document_manager_service.delete_document(doc_id, actor_user_id=current_user.id)
        flash(f'Broken document "{filename}" deleted.', 'success')
    except Exception as exc:
        flash(f'Could not delete broken document: {exc}', 'danger')
    return redirect(request.referrer or url_for('admin.storage_management'))
