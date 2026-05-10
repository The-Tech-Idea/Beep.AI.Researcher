"""Admin invite management routes."""

import datetime

from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from app.config_manager import config_manager
from app.database import db
from app.models.core import Role
from app.routes.route_entity_lookup import get_entity_or_404
from app.routes.admin_routes import admin_bp, admin_required


@admin_bp.route("/invites")
@login_required
@admin_required
def invites_list():
    """Admin: list and create invite tokens."""
    from app.models.user_management import UserInvite

    try:
        from app.models.researcher.storage_quota import PlanTier

        plan_tiers = PlanTier.query.order_by(PlanTier.name).all()
    except Exception:
        plan_tiers = []
    roles = Role.query.order_by(Role.name).all()
    invites = UserInvite.query.order_by(UserInvite.created_at.desc()).all()
    reg_mode = config_manager.get("registration_mode") or "open"
    base_url = request.host_url.rstrip("/")
    return render_template(
        "admin/invites.html",
        invites=invites,
        roles=roles,
        plan_tiers=plan_tiers,
        reg_mode=reg_mode,
        base_url=base_url,
    )


@admin_bp.route("/invites/create", methods=["POST"])
@login_required
@admin_required
def invite_create():
    """Create a new invite token."""
    import secrets as _secrets
    from app.models.user_management import UserInvite
    from app.core.time_utils import utcnow_naive

    email = request.form.get("email", "").strip() or None
    role_name = request.form.get("role_name", "").strip() or None
    max_uses_raw = request.form.get("max_uses", "1").strip()
    max_uses = int(max_uses_raw) if max_uses_raw.isdigit() else 1
    max_uses = min(max(max_uses, 1), 10000)
    expires_days = request.form.get("expires_days", type=int)
    expires_at = None
    if expires_days and expires_days > 0:
        expires_at = utcnow_naive() + datetime.timedelta(days=expires_days)

    token = _secrets.token_urlsafe(32)
    invite = UserInvite(
        token=token,
        email=email,
        role_name=role_name,
        max_uses=max_uses,
        expires_at=expires_at,
        created_by_id=current_user.id,
    )
    db.session.add(invite)
    db.session.commit()
    flash(f"Invite created. Token: {token}", "success")
    return redirect(url_for("admin.invites_list"))


@admin_bp.route("/invites/<int:invite_id>/revoke", methods=["POST"])
@login_required
@admin_required
def invite_revoke(invite_id):
    """Revoke an invite token."""
    from app.models.user_management import UserInvite
    from app.core.time_utils import utcnow_naive

    invite = get_entity_or_404(UserInvite, invite_id)
    invite.revoked_at = utcnow_naive()
    invite.revoked_by_id = current_user.id
    db.session.commit()
    flash("Invite revoked.", "success")
    return redirect(url_for("admin.invites_list"))
