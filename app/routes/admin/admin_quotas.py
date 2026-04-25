"""Admin quota management routes."""
from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required

from app.config_manager import config_manager
from app.database import db
from app.models.core import User
from app.routes.route_entity_lookup import get_entity_or_404
from app.routes.admin_routes import admin_bp, admin_required


@admin_bp.route('/quota')
@login_required
@admin_required
def quota_management():
    """Quota management: plan tiers, per-user overrides, per-tenant overrides, usage overview."""
    from app.models.researcher.storage_quota import PlanTier, TenantQuota, UserStorageStats

    plan_tiers = PlanTier.query.order_by(PlanTier.name).all()
    user_stats = (
        UserStorageStats.query
        .order_by(UserStorageStats.used_storage_bytes.desc())
        .limit(100).all()
    )
    tenant_quotas = TenantQuota.query.all()

    annotated = []
    for stat in user_stats:
        u = db.session.get(User, stat.user_id)
        annotated.append({
            'username': u.username if u else f'#{stat.user_id}',
            'user_id': stat.user_id,
            'storage_used_bytes': stat.used_storage_bytes,
            'document_count': stat.document_count,
            'storage_quota_bytes': getattr(u, 'storage_quota_bytes', None) if u else None,
        })

    return render_template(
        'admin/quota_management.html',
        plan_tiers=plan_tiers,
        user_stats=annotated,
        tenant_quotas=tenant_quotas,
        global_storage=config_manager.get('quota_default_storage_bytes') or 1073741824,
        global_docs=config_manager.get('quota_default_document_count') or 1000,
    )


@admin_bp.route('/quota/tier/add', methods=['POST'])
@login_required
@admin_required
def quota_plan_tier_add():
    """Add a new plan tier."""
    from app.models.researcher.storage_quota import PlanTier
    name = request.form.get('name', '').strip()
    if not name:
        flash('Tier name is required.', 'danger')
        return redirect(url_for('admin.quota_management'))

    storage = request.form.get('storage_quota_bytes', type=int)
    doc_q   = request.form.get('document_quota', type=int)
    upload  = request.form.get('max_upload_size_bytes', type=int)

    existing = PlanTier.query.filter_by(name=name).first()
    if existing:
        flash(f'Plan tier "{name}" already exists.', 'warning')
        return redirect(url_for('admin.quota_management'))

    tier = PlanTier(
        name=name,
        storage_quota_bytes=storage,
        document_quota=doc_q,
        max_upload_size_bytes=upload,
    )
    db.session.add(tier)
    db.session.commit()
    flash(f'Plan tier "{name}" created.', 'success')
    return redirect(url_for('admin.quota_management'))


@admin_bp.route('/quota/tier/<int:tier_id>/delete', methods=['POST'])
@login_required
@admin_required
def quota_plan_tier_delete(tier_id):
    """Delete a plan tier."""
    from app.models.researcher.storage_quota import PlanTier
    tier = get_entity_or_404(PlanTier, tier_id)
    name = tier.name
    db.session.delete(tier)
    db.session.commit()
    flash(f'Plan tier "{name}" deleted.', 'success')
    return redirect(url_for('admin.quota_management'))
