"""Admin routes — user management, settings overview. Admin role only."""

from functools import wraps

from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user

from app.config_manager import config_manager
from app.config import get_config
from app.database import db
from app.models.core import User, Role
from app.routes.route_entity_lookup import get_entity_or_404

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(f):
    """Decorator: require Admin role."""

    @wraps(f)
    def inner(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not getattr(current_user, "is_admin", False):
            flash("Admin access required.", "danger")
            return redirect(url_for("researcher.index"))
        return f(*args, **kwargs)

    return inner


@admin_bp.route("/")
@login_required
@admin_required
def index():
    """Admin dashboard."""
    from sqlalchemy import func as sqlfunc

    user_count = User.query.count()
    role_count = Role.query.count()

    storage_backend = config_manager.get("storage_backend") or "local"
    quota_enforcement = bool(config_manager.get("quota_enforcement_enabled"))

    from app.services.email_service import is_configured as email_is_configured

    email_configured = email_is_configured()
    email_method = config_manager.get("mail_auth_method") or "smtp"

    mfa_enabled = bool(config_manager.get("mfa_enabled"))
    sso_enabled = bool(config_manager.get("sso_enabled"))
    sso_provider = config_manager.get("sso_provider") or "none"

    try:
        from app.models.researcher import ResearcherDocument

        doc_count = ResearcherDocument.query.count()
        total_storage = (
            db.session.query(sqlfunc.sum(ResearcherDocument.file_size)).scalar() or 0
        )
    except Exception:
        doc_count = 0
        total_storage = 0

    from app.models.core import AuditLog

    recent_audit = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(8).all()

    from app.config import get_config

    runtime_config = get_config()
    all_features = runtime_config.get_all_features()
    enabled_feature_count = sum(
        1
        for f in all_features.values()
        if (f.get("enabled", False) if isinstance(f, dict) else bool(f))
    )
    total_feature_count = len(all_features)

    return render_template(
        "admin/index.html",
        user_count=user_count,
        role_count=role_count,
        storage_backend=storage_backend,
        quota_enforcement=quota_enforcement,
        email_configured=email_configured,
        email_method=email_method,
        mfa_enabled=mfa_enabled,
        sso_enabled=sso_enabled,
        sso_provider=sso_provider,
        doc_count=doc_count,
        total_storage=total_storage,
        recent_audit=recent_audit,
        enabled_feature_count=enabled_feature_count,
        total_feature_count=total_feature_count,
    )


# ---------------------------------------------------------------------------
# Sub-domain route registration (safe deferred-import pattern).
# These imports must remain at the bottom of this module; they add routes to
# admin_bp via side-effect.  By the time Python evaluates these lines, both
# admin_bp and admin_required are already defined above, so the circular
# import resolves cleanly.
# ---------------------------------------------------------------------------
import app.routes.admin.admin_users  # noqa: F401, E402
import app.routes.admin.admin_settings  # noqa: F401, E402
import app.routes.admin.admin_quotas  # noqa: F401, E402
import app.routes.admin.admin_documents  # noqa: F401, E402
import app.routes.admin.admin_storage  # noqa: F401, E402
import app.routes.admin.admin_invites  # noqa: F401, E402
import app.routes.admin.admin_api  # noqa: F401, E402
import app.routes.admin.admin_feature_flags  # noqa: F401, E402
