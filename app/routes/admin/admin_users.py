"""Admin user management routes — list, lifecycle, impersonation."""

import csv
import io

from flask import render_template, redirect, url_for, request, flash
from flask import session as flask_session
from flask_login import login_required, current_user, login_user

from app.database import db
from app.models.core import User, Role
from app.routes.route_entity_lookup import get_entity_or_404
from app.routes.admin_routes import admin_bp, admin_required


# =============================================================================
# User List + Quick Status Actions
# =============================================================================


@admin_bp.route("/users")
@login_required
@admin_required
def users_list():
    """List users with filter and text search."""
    q = User.query
    role_filter = request.args.get("role", type=int)
    status_filter = request.args.get("status")
    search = request.args.get("q", "").strip()
    if role_filter:
        q = q.filter_by(role_id=role_filter)
    if status_filter == "active":
        q = q.filter_by(is_active=True)
    elif status_filter == "suspended":
        q = q.filter_by(is_active=False)
    if search:
        like = f"%{search}%"
        q = q.filter(db.or_(User.username.ilike(like), User.email.ilike(like)))
    users = q.order_by(User.created_at.desc()).all()
    roles = Role.query.order_by(Role.name).all()
    return render_template(
        "admin/users.html",
        users=users,
        roles=roles,
        selected_role=role_filter,
        selected_status=status_filter,
        search=search,
    )


@admin_bp.route("/users/<int:user_id>/activate", methods=["POST"])
@login_required
@admin_required
def user_activate(user_id):
    """Activate (enable) user."""
    if user_id == current_user.id:
        flash("You cannot change your own status.", "warning")
        return redirect(url_for("admin.users_list"))
    user = get_entity_or_404(User, user_id)
    user.is_active = True
    db.session.commit()
    flash(f"User {user.username} activated.", "success")
    return redirect(request.referrer or url_for("admin.users_list"))


@admin_bp.route("/users/<int:user_id>/suspend", methods=["POST"])
@login_required
@admin_required
def user_suspend(user_id):
    """Suspend (disable) user."""
    if user_id == current_user.id:
        flash("You cannot suspend yourself.", "danger")
        return redirect(url_for("admin.users_list"))
    user = get_entity_or_404(User, user_id)
    user.is_active = False
    db.session.commit()
    flash(f"User {user.username} suspended.", "success")
    return redirect(request.referrer or url_for("admin.users_list"))


@admin_bp.route("/users/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def user_change_role(user_id):
    """Change user role."""
    if user_id == current_user.id:
        flash("You cannot change your own role.", "warning")
        return redirect(url_for("admin.users_list"))
    user = get_entity_or_404(User, user_id)
    role_id = request.form.get("role_id", type=int)
    if not role_id:
        flash("Role required.", "danger")
        return redirect(request.referrer or url_for("admin.users_list"))
    role = db.session.get(Role, role_id)
    if not role:
        flash("Invalid role.", "danger")
        return redirect(request.referrer or url_for("admin.users_list"))
    user.role_id = role_id
    db.session.commit()
    flash(f"User {user.username} role set to {role.name}.", "success")
    return redirect(request.referrer or url_for("admin.users_list"))


# =============================================================================
# User Lifecycle (create / detail / edit / password / MFA / unlock / delete)
# =============================================================================


@admin_bp.route("/users/create", methods=["GET", "POST"])
@login_required
@admin_required
def user_create():
    """Admin: create a new user directly (no invite required)."""
    roles = Role.query.order_by(Role.name).all()
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip() or None
        password = request.form.get("password", "").strip()
        role_id = request.form.get("role_id", type=int)
        is_active = "is_active" in request.form
        must_change = "must_change_password" in request.form

        if not username or not password:
            flash("Username and password are required.", "danger")
            return render_template("admin/user_create.html", roles=roles)

        if len(username) < 3 or len(username) > 150:
            flash("Username must be 3-150 characters.", "danger")
            return render_template("admin/user_create.html", roles=roles)

        if not username.replace("_", "").replace(".", "").replace("-", "").isalnum():
            flash(
                "Username may only contain letters, numbers, hyphens, underscores, and dots.",
                "danger",
            )
            return render_template("admin/user_create.html", roles=roles)

        if User.query.filter_by(username=username).first():
            flash(f'Username "{username}" is already taken.', "danger")
            return render_template("admin/user_create.html", roles=roles)

        from app.services.password_policy_service import (
            validate_password,
            record_password_change,
        )

        ok, errors = validate_password(password)
        if not ok:
            for e in errors:
                flash(e, "danger")
            return render_template("admin/user_create.html", roles=roles)

        from werkzeug.security import generate_password_hash

        pw_hash = generate_password_hash(password)
        user = User(
            username=username,
            email=email,
            password_hash=pw_hash,
            role_id=role_id,
            is_active=is_active,
            email_verified=True,
            must_change_password=must_change,
        )
        db.session.add(user)
        db.session.flush()
        try:
            record_password_change(user.id, pw_hash)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            flash(f"Failed to create user: {exc}", "danger")
            return render_template("admin/user_create.html", roles=roles)
        flash(f'User "{username}" created.', "success")
        return redirect(url_for("admin.user_detail", user_id=user.id))

    return render_template("admin/user_create.html", roles=roles)


@admin_bp.route("/users/<int:user_id>")
@login_required
@admin_required
def user_detail(user_id):
    """Admin: full user detail — profile, quota, sessions, MFA status, audit."""
    user = get_entity_or_404(User, user_id)
    roles = Role.query.order_by(Role.name).all()

    from app.models.user_management import UserSession
    from app.models.core import AuditLog

    try:
        from app.models.researcher.storage_quota import PlanTier, UserStorageStats

        plan_tiers = PlanTier.query.order_by(PlanTier.name).all()
        storage_stats = UserStorageStats.query.filter_by(user_id=user_id).first()
    except Exception:
        plan_tiers = []
        storage_stats = None

    sessions = (
        UserSession.query.filter_by(user_id=user_id, is_active=True)
        .order_by(UserSession.last_seen_at.desc())
        .all()
    )
    audit = (
        AuditLog.query.filter_by(user_id=user_id)
        .order_by(AuditLog.created_at.desc())
        .limit(50)
        .all()
    )

    from app.core.time_utils import utcnow_naive

    all_users = User.query.order_by(User.username).all()
    return render_template(
        "admin/user_detail.html",
        u=user,
        roles=roles,
        plan_tiers=plan_tiers,
        storage_stats=storage_stats,
        sessions=sessions,
        audit=audit,
        all_users=all_users,
        now=utcnow_naive(),
    )


@admin_bp.route("/users/<int:user_id>/edit", methods=["POST"])
@login_required
@admin_required
def user_edit(user_id):
    """Admin: edit user profile, role, quota, flags."""
    user = get_entity_or_404(User, user_id)

    email = request.form.get("email", "").strip() or None
    role_id = request.form.get("role_id", type=int)
    is_active = "is_active" in request.form
    email_verified = "email_verified" in request.form
    must_change = "must_change_password" in request.form
    display_name = request.form.get("display_name", "").strip() or None

    user.email = email
    user.is_active = is_active
    user.email_verified = email_verified
    user.must_change_password = must_change
    if display_name is not None:
        if hasattr(user, "display_name"):
            user.display_name = display_name
    if role_id and user.id != current_user.id:
        existing_role = db.session.get(Role, role_id)
        if existing_role:
            user.role_id = role_id
        else:
            flash(f"Role #{role_id} does not exist.", "danger")

    storage_quota = request.form.get("storage_quota_bytes", type=int)
    doc_quota = request.form.get("document_quota", type=int)
    plan_tier_id = request.form.get("plan_tier_id", type=int) or None

    if storage_quota is not None and hasattr(user, "storage_quota_bytes"):
        user.storage_quota_bytes = storage_quota if storage_quota > 0 else None
    if doc_quota is not None and hasattr(user, "document_quota"):
        user.document_quota = doc_quota if doc_quota > 0 else None
    if hasattr(user, "plan_tier_id"):
        user.plan_tier_id = plan_tier_id

    db.session.commit()
    flash(f'User "{user.username}" updated.', "success")
    return redirect(url_for("admin.user_detail", user_id=user_id))


@admin_bp.route("/users/<int:user_id>/set-password", methods=["POST"])
@login_required
@admin_required
def user_set_password(user_id):
    """Admin: force-set a user's password."""
    user = get_entity_or_404(User, user_id)
    new_password = request.form.get("new_password", "").strip()
    if not new_password:
        flash("Password is required.", "danger")
        return redirect(url_for("admin.user_detail", user_id=user_id))

    from app.services.password_policy_service import (
        validate_password,
        record_password_change,
    )

    ok, errors = validate_password(new_password)
    if not ok:
        for e in errors:
            flash(e, "danger")
        return redirect(url_for("admin.user_detail", user_id=user_id))

    from werkzeug.security import generate_password_hash
    from app.core.time_utils import utcnow_naive

    pw_hash = generate_password_hash(new_password)
    user.password_hash = pw_hash
    user.must_change_password = "must_change" in request.form
    user.password_changed_at = utcnow_naive()
    db.session.flush()
    record_password_change(user.id, pw_hash)
    db.session.commit()
    flash(f'Password for "{user.username}" updated.', "success")
    return redirect(url_for("admin.user_detail", user_id=user_id))


@admin_bp.route("/users/<int:user_id>/mfa-reset", methods=["POST"])
@login_required
@admin_required
def user_mfa_reset(user_id):
    """Admin: clear all MFA settings for a locked-out user."""
    user = get_entity_or_404(User, user_id)
    if hasattr(user, "mfa_enabled"):
        user.mfa_enabled = False
    if hasattr(user, "mfa_methods"):
        user.mfa_methods = ""
    if hasattr(user, "mfa_totp_secret"):
        user.mfa_totp_secret = None
    if hasattr(user, "mfa_backup_codes_hash"):
        user.mfa_backup_codes_hash = None
    if hasattr(user, "mfa_backup_codes_remaining"):
        user.mfa_backup_codes_remaining = 0
    db.session.commit()
    flash(
        f'MFA cleared for "{user.username}". They can re-enroll on next login.',
        "success",
    )
    return redirect(url_for("admin.user_detail", user_id=user_id))


@admin_bp.route("/users/<int:user_id>/unlock", methods=["POST"])
@login_required
@admin_required
def user_unlock(user_id):
    """Admin: clear account lockout."""
    user = get_entity_or_404(User, user_id)
    if hasattr(user, "locked_until"):
        user.locked_until = None
    if hasattr(user, "failed_login_attempts"):
        user.failed_login_attempts = 0
    db.session.commit()
    flash(f'Account "{user.username}" unlocked.', "success")
    return redirect(url_for("admin.user_detail", user_id=user_id))


@admin_bp.route("/users/<int:user_id>/sessions/revoke-all", methods=["POST"])
@login_required
@admin_required
def user_revoke_all_sessions(user_id):
    """Admin: force-revoke all active sessions for a user."""
    from app.services.session_service import revoke_all_sessions

    count = revoke_all_sessions(user_id, revoked_by_id=current_user.id)
    flash(f"Revoked {count} session(s) for user #{user_id}.", "success")
    return redirect(url_for("admin.user_detail", user_id=user_id))


@admin_bp.route("/users/<int:user_id>/impersonate", methods=["POST"])
@login_required
@admin_required
def user_impersonate(user_id):
    """Admin: log in as another user (impersonation for support)."""
    if user_id == current_user.id:
        flash("Cannot impersonate yourself.", "warning")
        return redirect(url_for("admin.user_detail", user_id=user_id))
    target = get_entity_or_404(User, user_id)
    flask_session["impersonating_as"] = user_id
    flask_session["impersonator_id"] = current_user.id
    login_user(target)
    flash(
        f'Now acting as "{target.username}". Return to admin to stop impersonation.',
        "warning",
    )
    return redirect(url_for("researcher.index"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def user_delete(user_id):
    """Admin: delete user account and optionally reassign their data."""
    if user_id == current_user.id:
        flash("Cannot delete your own account.", "danger")
        return redirect(url_for("admin.users_list"))
    user = get_entity_or_404(User, user_id)
    username = user.username

    reassign_to_id = request.form.get("reassign_to_id", type=int) or None
    if reassign_to_id:
        from app.models.researcher import ResearchProject

        reassigned = ResearchProject.query.filter_by(user_id=user_id).update(
            {"user_id": reassign_to_id}
        )
        if reassigned:
            flash(f"Reassigned {reassigned} project(s) to new owner.", "info")

    from app.services.session_service import revoke_all_sessions

    revoke_all_sessions(user_id, revoked_by_id=current_user.id)

    db.session.delete(user)
    db.session.commit()
    flash(f'User "{username}" permanently deleted.', "success")
    return redirect(url_for("admin.users_list"))


# =============================================================================
# Bulk User Import
# =============================================================================


@admin_bp.route("/users/import", methods=["GET", "POST"])
@login_required
@admin_required
def user_import():
    """Admin: bulk import users from CSV (username,email,role,password)."""
    roles = Role.query.order_by(Role.name).all()
    if request.method == "GET":
        return render_template("admin/user_import.html", roles=roles)

    csv_file = request.files.get("csv_file")
    if not csv_file or not csv_file.filename:
        flash("No file selected.", "danger")
        return render_template("admin/user_import.html", roles=roles)

    from werkzeug.security import generate_password_hash
    from app.services.password_policy_service import record_password_change

    content = csv_file.read().decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(content))

    MAX_IMPORT_ROWS = 10000
    row_count = sum(1 for _ in io.StringIO(content)) - 1
    if row_count > MAX_IMPORT_ROWS:
        flash(
            f"CSV has {row_count} rows. Maximum allowed is {MAX_IMPORT_ROWS}.", "danger"
        )
        return render_template("admin/user_import.html", roles=roles)

    default_role_name = request.form.get("default_role", "").strip()
    default_role = Role.query.filter_by(name=default_role_name).first()

    created = skipped = errors_count = 0
    error_rows = []

    for i, row in enumerate(reader, start=2):
        username = (row.get("username") or "").strip()
        email = (row.get("email") or "").strip() or None
        password = (row.get("password") or "").strip()
        role_name = (row.get("role") or "").strip()

        if not username or not password:
            error_rows.append(f"Row {i}: missing username or password")
            errors_count += 1
            continue

        if len(username) < 3 or len(username) > 150:
            error_rows.append(f"Row {i}: username must be 3-150 characters")
            errors_count += 1
            continue

        if not username.replace("_", "").replace(".", "").replace("-", "").isalnum():
            error_rows.append(
                f"Row {i}: username may only contain letters, numbers, hyphens, underscores, and dots"
            )
            errors_count += 1
            continue

        if User.query.filter_by(username=username).first():
            skipped += 1
            continue

        role = (
            Role.query.filter_by(name=role_name).first() if role_name else default_role
        )
        pw_hash = generate_password_hash(password)
        user = User(
            username=username,
            email=email,
            password_hash=pw_hash,
            role_id=role.id if role else None,
            is_active=True,
            email_verified=bool(email),
        )
        db.session.add(user)
        db.session.flush()
        record_password_change(user.id, pw_hash)
        created += 1

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        flash(f"Import failed during commit: {exc}", "danger")
        return redirect(url_for("admin.users_list"))

    flash(
        f"Import complete: {created} created, {skipped} skipped (duplicate), {errors_count} errors.",
        "success",
    )
    for msg in error_rows[:10]:
        flash(msg, "warning")
    return redirect(url_for("admin.users_list"))


# =============================================================================
# Impersonation — stop
# =============================================================================


@admin_bp.route("/impersonate/stop", methods=["POST"])
@login_required
@admin_required
def impersonate_stop():
    """Stop impersonating and return to admin's own account."""
    target_id = flask_session.pop("impersonating_as", None)
    original_id = flask_session.pop("impersonator_id", None)
    if original_id:
        from app.database import db as _db
        from app.models.core import User as _User

        original = _db.session.get(_User, original_id)
        if original:
            login_user(original)
            flash("Returned to your own account.", "info")
            return redirect(url_for("admin.users_list"))
    return redirect(url_for("researcher.index"))
