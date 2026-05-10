"""Admin quota management routes."""

from flask import render_template, redirect, url_for, request, flash
from flask_login import current_user, login_required

from app.config_manager import config_manager
from app.database import db
from app.models.core import User
from app.routes.route_entity_lookup import get_entity_or_404
from app.routes.admin_routes import admin_bp, admin_required


def _positive_int_or_none(field_name: str):
    value = request.form.get(field_name, type=int)
    return value if value and value > 0 else None


def _record_quota_audit(
    action: str, resource: str, resource_id: int | str | None = None
) -> None:
    """Persist a simple admin audit row for quota changes."""

    from app.models.core import AuditLog

    db.session.add(
        AuditLog(
            user_id=current_user.id,
            action=action,
            resource=resource,
            resource_id=str(resource_id) if resource_id is not None else None,
        )
    )


@admin_bp.route("/quota")
@login_required
@admin_required
def quota_management():
    """Quota management: plan tiers, per-user overrides, per-tenant overrides, usage overview."""
    from app.models.researcher.storage_quota import (
        PlanTier,
        TenantQuota,
        UserStorageStats,
    )
    from app.models.tenant import Tenant

    plan_tiers = PlanTier.query.order_by(PlanTier.name).all()
    user_stats = (
        UserStorageStats.query.order_by(UserStorageStats.used_storage_bytes.desc())
        .limit(100)
        .all()
    )
    tenant_quotas = TenantQuota.query.all()
    tenants = Tenant.query.order_by(Tenant.name).all()
    users = User.query.order_by(User.username).all()

    annotated = []
    for stat in user_stats:
        u = db.session.get(User, stat.user_id)
        annotated.append(
            {
                "username": u.username if u else f"#{stat.user_id}",
                "user_id": stat.user_id,
                "storage_used_bytes": stat.used_storage_bytes,
                "document_count": stat.document_count,
                "storage_quota_bytes": getattr(u, "storage_quota_bytes", None)
                if u
                else None,
                "document_quota": getattr(u, "document_quota", None) if u else None,
                "plan_tier_id": getattr(u, "plan_tier_id", None) if u else None,
            }
        )

    return render_template(
        "admin/quota_management.html",
        plan_tiers=plan_tiers,
        user_stats=annotated,
        tenant_quotas=tenant_quotas,
        tenants=tenants,
        users=users,
        global_storage=config_manager.get("quota_default_storage_bytes") or 1073741824,
        global_docs=config_manager.get("quota_default_document_count") or 500,
    )


@admin_bp.route("/quota/tier/add", methods=["POST"])
@login_required
@admin_required
def quota_plan_tier_add():
    """Add a new plan tier."""
    from app.models.researcher.storage_quota import PlanTier

    name = request.form.get("name", "").strip()
    if not name:
        flash("Tier name is required.", "danger")
        return redirect(url_for("admin.quota_management"))

    storage = _positive_int_or_none("storage_quota_bytes")
    doc_q = _positive_int_or_none("document_quota")
    project_q = _positive_int_or_none("project_quota")
    api_calls = _positive_int_or_none("api_calls_per_day")
    upload = _positive_int_or_none("max_upload_size_bytes")

    existing = PlanTier.query.filter_by(name=name).first()
    if existing:
        flash(f'Plan tier "{name}" already exists.', "warning")
        return redirect(url_for("admin.quota_management"))

    tier = PlanTier(
        name=name,
        storage_quota_bytes=storage,
        document_quota=doc_q,
        project_quota=project_q,
        api_calls_per_day=api_calls,
        max_upload_size_bytes=upload,
        price_display=request.form.get("price_display", "").strip() or None,
        description=request.form.get("description", "").strip() or None,
        is_active="is_active" in request.form,
    )
    db.session.add(tier)
    _record_quota_audit("admin.quota.tier.create", name)
    db.session.commit()
    flash(f'Plan tier "{name}" created.', "success")
    return redirect(url_for("admin.quota_management"))


@admin_bp.route("/quota/tier/<int:tier_id>/delete", methods=["POST"])
@login_required
@admin_required
def quota_plan_tier_delete(tier_id):
    """Delete a plan tier."""
    from app.models.researcher.storage_quota import PlanTier

    tier = get_entity_or_404(PlanTier, tier_id)
    name = tier.name
    _record_quota_audit("admin.quota.tier.delete", name, tier.id)
    db.session.delete(tier)
    db.session.commit()
    flash(f'Plan tier "{name}" deleted.', "success")
    return redirect(url_for("admin.quota_management"))


@admin_bp.route("/quota/tier/<int:tier_id>/update", methods=["POST"])
@login_required
@admin_required
def quota_plan_tier_update(tier_id):
    """Update an existing plan tier."""

    from app.models.researcher.storage_quota import PlanTier

    tier = get_entity_or_404(PlanTier, tier_id)
    name = request.form.get("name", "").strip()
    if not name:
        flash("Tier name is required.", "danger")
        return redirect(url_for("admin.quota_management") + "#qt-tiers")

    duplicate = PlanTier.query.filter(
        PlanTier.name == name, PlanTier.id != tier.id
    ).first()
    if duplicate:
        flash(f'Plan tier "{name}" already exists.', "warning")
        return redirect(url_for("admin.quota_management") + "#qt-tiers")

    tier.name = name
    tier.storage_quota_bytes = _positive_int_or_none("storage_quota_bytes")
    tier.document_quota = _positive_int_or_none("document_quota")
    tier.max_upload_size_bytes = _positive_int_or_none("max_upload_size_bytes")
    tier.project_quota = _positive_int_or_none("project_quota")
    tier.api_calls_per_day = _positive_int_or_none("api_calls_per_day")
    tier.price_display = request.form.get("price_display", "").strip() or None
    tier.description = request.form.get("description", "").strip() or None
    tier.is_active = "is_active" in request.form
    _record_quota_audit("admin.quota.tier.update", tier.name, tier.id)
    db.session.commit()
    flash(f'Plan tier "{tier.name}" updated.', "success")
    return redirect(url_for("admin.quota_management") + "#qt-tiers")


@admin_bp.route("/quota/users/<int:user_id>/override", methods=["POST"])
@login_required
@admin_required
def quota_user_override_save(user_id):
    """Set or clear a user's quota override from the quota page."""

    user = get_entity_or_404(User, user_id)
    storage_quota = request.form.get("storage_quota_bytes", type=int)
    document_quota = request.form.get("document_quota", type=int)
    plan_tier_id = request.form.get("plan_tier_id", type=int) or None

    user.storage_quota_bytes = (
        storage_quota if storage_quota and storage_quota > 0 else None
    )
    user.document_quota = (
        document_quota if document_quota and document_quota > 0 else None
    )
    user.plan_tier_id = plan_tier_id
    _record_quota_audit("admin.quota.user_override.update", user.username, user.id)
    db.session.commit()
    flash(f"Quota override updated for {user.username}.", "success")
    return redirect(url_for("admin.quota_management"))


@admin_bp.route("/quota/tenants/<int:tenant_id>/save", methods=["POST"])
@login_required
@admin_required
def quota_tenant_save(tenant_id):
    """Create or update a tenant quota record."""

    from app.models.tenant import Tenant
    from app.models.researcher.storage_quota import TenantQuota

    tenant = get_entity_or_404(Tenant, tenant_id)
    quota = TenantQuota.query.filter_by(tenant_id=tenant.id).first()
    if quota is None:
        quota = TenantQuota(tenant_id=tenant.id)
        db.session.add(quota)

    quota.plan_tier_id = request.form.get("plan_tier_id", type=int) or None
    storage_quota = request.form.get("storage_quota_bytes", type=int)
    document_quota = request.form.get("document_quota", type=int)
    max_upload = request.form.get("max_upload_size_bytes", type=int)
    quota.storage_quota_bytes = (
        storage_quota if storage_quota and storage_quota > 0 else None
    )
    quota.document_quota = (
        document_quota if document_quota and document_quota > 0 else None
    )
    quota.max_upload_size_bytes = max_upload if max_upload and max_upload > 0 else None
    _record_quota_audit("admin.quota.tenant.update", tenant.name, tenant.id)
    db.session.commit()
    flash(f"Tenant quota updated for {tenant.name}.", "success")
    return redirect(url_for("admin.quota_management") + "#qt-tenant")


@admin_bp.route("/quota/tenants/<int:tenant_id>/delete", methods=["POST"])
@login_required
@admin_required
def quota_tenant_delete(tenant_id):
    """Delete a tenant quota override."""

    from app.models.tenant import Tenant
    from app.models.researcher.storage_quota import TenantQuota

    tenant = get_entity_or_404(Tenant, tenant_id)
    quota = TenantQuota.query.filter_by(tenant_id=tenant.id).first()
    if quota:
        _record_quota_audit("admin.quota.tenant.delete", tenant.name, tenant.id)
        db.session.delete(quota)
        db.session.commit()
        flash(f"Tenant quota override deleted for {tenant.name}.", "success")
    else:
        flash(f"Tenant {tenant.name} has no quota override.", "warning")
    return redirect(url_for("admin.quota_management") + "#qt-tenant")


@admin_bp.route("/quota/users/<int:user_id>/recalculate", methods=["POST"])
@login_required
@admin_required
def quota_user_recalculate(user_id):
    """Recalculate one user's document quota counters from source document rows."""

    from app.services.quota_service import quota_service

    user = get_entity_or_404(User, user_id)
    stats = quota_service.recalculate_user(user.id)
    flash(
        f"Quota recalculated for {user.username}: {stats.document_count} documents, "
        f"{stats.used_storage_bytes:,} bytes.",
        "success",
    )
    return redirect(url_for("admin.quota_management"))


@admin_bp.route("/quota/recalculate-all", methods=["POST"])
@login_required
@admin_required
def quota_recalculate_all():
    """Recalculate quota counters for all users."""

    from app.services.quota_service import quota_service

    users = User.query.order_by(User.id).all()
    updated = 0
    failed = 0
    for user in users:
        try:
            quota_service.recalculate_user(user.id)
            updated += 1
        except Exception:
            db.session.rollback()
            failed += 1

    category = "success" if failed == 0 else "warning"
    flash(
        f"Quota recalculation complete: {updated} updated, {failed} failed.", category
    )
    return redirect(url_for("admin.quota_management"))


@admin_bp.route("/quota/tenants/<int:tenant_id>/recalculate", methods=["POST"])
@login_required
@admin_required
def quota_tenant_recalculate(tenant_id):
    """Recalculate one tenant pool quota from project document rows."""

    from app.models.tenant import Tenant
    from app.services.quota_service import quota_service

    tenant = get_entity_or_404(Tenant, tenant_id)
    quota = quota_service.recalculate_tenant(tenant.id)
    flash(
        f"Tenant quota recalculated for {tenant.name}: {quota.document_count} documents, "
        f"{quota.used_storage_bytes:,} bytes.",
        "success",
    )
    return redirect(url_for("admin.quota_management") + "#qt-tenant")
