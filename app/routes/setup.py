"""Setup wizard — Admin, DB, Auth, Initialize. All config via config_manager."""

import os
from flask import (
    Blueprint,
    request,
    jsonify,
    render_template,
    redirect,
    url_for,
    current_app,
)
from sqlalchemy import text
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from app.config_manager import config_manager
from app.database import db, get_db_uri

setup_bp = Blueprint("setup", __name__, url_prefix="/setup")


@setup_bp.route("/")
def index():
    """Show setup wizard -- always accessible, but redirect to login if already configured."""
    if config_manager.is_configured:
        from flask import flash

        flash("App is already configured. Use Admin > Settings to modify.", "info")
        return redirect(url_for("auth.login"))
    return render_template("setup.html", defaults=_wizard_defaults())


@setup_bp.route("/reset", methods=["POST"])
def reset():
    """Reset configuration so the setup wizard can be run again. Admin only."""
    from flask import flash
    from flask_login import current_user
    from app.models.core import User, Role

    if not current_user.is_authenticated:
        flash("Authentication required.", "danger")
        return redirect(url_for("auth.login"))

    admin_role = Role.query.filter_by(name="Admin").first()
    if not admin_role or current_user.role_id != admin_role.id:
        flash("Admin access required.", "danger")
        return redirect(url_for("researcher.index"))

    # Reset configuration flag only (keeps existing data)
    config_manager.set("is_configured", False)
    config_manager.save()

    flash("Setup has been reset. You can now re-run the setup wizard.", "success")
    return redirect(url_for("setup.index"))


def _wizard_defaults():
    """Default values from config_manager for wizard UI."""
    rel_db = f"data/researcher.db"
    return {
        "db_path": str(config_manager.db_path),
        "db_path_relative": rel_db,
        "server_host": config_manager.get_setting(
            "server_host", default="127.0.0.1", env_var="HOST"
        ),
        "server_port": config_manager.get_setting(
            "server_port", default=5005, env_var="PORT"
        ),
    }


@setup_bp.route("/api/defaults")
def api_defaults():
    """Get wizard defaults from config_manager."""
    return jsonify(_wizard_defaults())


@setup_bp.route("/api/validate-db", methods=["POST"])
def validate_db():
    """Validate DB connection. Uses config_manager paths for SQLite."""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"success": False, "message": "No JSON data received"}), 400
        provider = data.get("provider", "sqlite")
        db_params = {k: v for k, v in data.items() if k != "provider"}
        if provider == "sqlite" and not db_params.get("path"):
            db_params["path"] = str(config_manager.db_path)
        uri = get_db_uri(provider, **db_params)
        if not uri:
            return jsonify(
                {"success": False, "message": "Invalid database parameters"}
            ), 400
        engine = create_engine(uri)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return jsonify(
            {"success": True, "message": "Connection successful!", "uri": uri}
        )
    except Exception as e:
        return jsonify({"success": False, "message": f"Server Error: {str(e)}"}), 500


@setup_bp.route("/api/initialize", methods=["POST"])
def initialize():
    """Initialize app — DB, admin user, config (same as Beep.AI.Server)."""
    from app.models.core import User, Role
    from werkzeug.security import generate_password_hash

    data = request.get_json(silent=True) or {}
    db_uri = data.get("db_uri")
    admin_user = (data.get("username") or "").strip()
    admin_pass = data.get("password")
    auth_mode = data.get("auth_mode", "local")
    identity_cfg = data.get("identity") or {}

    if not db_uri:
        db_uri = f"sqlite:///{config_manager.db_path}"
    if not admin_user:
        return jsonify({"success": False, "message": "Username is required"}), 400
    if not admin_pass:
        return jsonify({"success": False, "message": "Admin password is required"}), 400

    try:
        config_manager.set("SQLALCHEMY_DATABASE_URI", db_uri)
        config_manager.set("auth_mode", auth_mode)
        if auth_mode == "identity":
            config_manager.set("ENABLE_IDENTITYSERVER_AUTH", True)
            config_manager.set(
                "IDENTITYSERVER_AUTHORITY", identity_cfg.get("authority")
            )
            config_manager.set(
                "IDENTITYSERVER_CLIENT_ID", identity_cfg.get("client_id")
            )
            config_manager.set(
                "IDENTITYSERVER_CLIENT_SECRET", identity_cfg.get("client_secret")
            )
            config_manager.set("IDENTITYSERVER_SCOPES", identity_cfg.get("scopes"))
            config_manager.set(
                "IDENTITYSERVER_LOGOUT_REDIRECT", identity_cfg.get("logout_redirect")
            )
        else:
            config_manager.set("ENABLE_IDENTITYSERVER_AUTH", False)

        if db_uri.startswith("sqlite:///") and not db_uri.startswith("sqlite:////"):
            rel = db_uri.replace("sqlite:///", "")
            abs_path = (
                config_manager.base_path / rel
                if rel and "/" in rel
                else config_manager.db_path
            )
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            db_uri = f"sqlite:///{str(abs_path).replace(chr(92), '/')}"
        config_manager.set("SQLALCHEMY_DATABASE_URI", db_uri)

        current_app.config["SQLALCHEMY_DATABASE_URI"] = db_uri
        new_engine = create_engine(db_uri)
        db.session.remove()
        if getattr(db, "engine", None):
            db.engine.dispose()
        db.session = scoped_session(sessionmaker(bind=new_engine))

        from app.models.core import User, Role, AuditLog
        from app.models.tenant import Tenant, TenantMember
        from app.models.researcher import (
            ResearchProject,
            ProjectMember,
            ProjectComment,
            ResearcherDocument,
            Code,
            CodedReference,
            DocumentAnnotation,
            ChatSession,
            ChatMessage,
            ResearcherDataSource,
            SavedChart,
            ScheduledReport,
            ExtractionSchema,
            ExtractionResult,
            Flashcard,
            Quiz,
            QuizQuestion,
        )

        db.Model.metadata.create_all(bind=new_engine)

        admin_role = Role.query.filter_by(name="Admin").first()
        if not admin_role:
            admin_role = Role(name="Admin")
            admin_role.set_permissions(
                [
                    "researcher:view",
                    "researcher:contribute",
                    "researcher:manage",
                    "researcher:admin",
                ]
            )
            db.session.add(admin_role)
            db.session.flush()

        if not User.query.filter_by(username=admin_user).first():
            admin_email = data.get("email") or f"{admin_user}@localhost"
            user = User(
                username=admin_user,
                email=admin_email,
                password_hash=generate_password_hash(admin_pass),
                role_id=admin_role.id,
                is_active=True,
                email_verified=True,  # Admin created by setup is pre-verified
            )
            db.session.add(user)

        config_manager.set("is_configured", True)
        config_manager.set("secret_key", os.urandom(24).hex())
        config_manager.save()
        db.session.commit()
        return jsonify({"success": True, "redirect": url_for("auth.login")})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
