"""Auth routes — login, logout, register, verify, profile (Flask-Login)."""

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    session,
)
from flask_login import login_user, logout_user, login_required, current_user

from app.config_manager import config_manager
from app.database import db
from app.models.core import User, Role
from app.models.user_management import UserInvite, UserSession
from app.routes.route_entity_lookup import get_entity, get_entity_or_404, _base_template
from app.services.email_service import (
    is_configured as email_is_configured,
    send_verification_email,
)
from app.services import captcha_service
from app.services.password_policy_service import (
    validate_password,
    record_password_change,
    is_password_expired,
    is_locked_out,
    record_failed_login,
    record_successful_login,
)
from app.services import mfa_service
from app.services import session_service
from app.core.time_utils import utcnow_naive
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint("auth", __name__)


def _check_has_admin():
    """Check if there is at least one active admin user."""
    try:
        admin_role = Role.query.filter_by(name="Admin").first()
        if admin_role:
            return (
                User.query.filter_by(role_id=admin_role.id, is_active=True).count() > 0
            )
    except Exception:
        pass
    return False


def _captcha_data(config_key):
    """Generate captcha challenge if the given config key is enabled."""
    if config_manager.get(config_key, False):
        return captcha_service.generate_challenge(session)
    return None


def _login_ctx(next_url=None):
    return {
        "next": next_url,
        "captcha": _captcha_data("login_captcha_enabled"),
        "has_admin": _check_has_admin(),
    }


def _register_ctx(invite_token, reg_mode, captcha=None):
    return {
        "invite_token": invite_token,
        "reg_mode": reg_mode,
        "captcha": captcha or _captcha_data("registration_captcha_enabled"),
    }


def _mfa_challenge_ctx(user, next_url):
    return {
        "methods": mfa_service.get_active_methods(user) or ["email"],
        "next": next_url,
        "has_backup_codes": getattr(user, "mfa_backup_codes_remaining", 0) or 0,
        "base_template": _base_template(),
    }


def _change_password_ctx():
    return {"base_template": _base_template()}


def _profile_ctx(user):
    return {"user": user, "base_template": _base_template()}


def _mfa_setup_sms_ctx(sent, phone):
    return {"sent": sent, "phone": phone, "base_template": _base_template()}


def _mfa_setup_ctx(secret, qr_b64):
    return {
        "secret": secret,
        "qr_b64": qr_b64,
        "base_template": _base_template(),
    }


def _mfa_backup_codes_ctx(new_codes, remaining):
    return {
        "new_codes": new_codes,
        "remaining": remaining,
        "base_template": _base_template(),
    }


def _sessions_ctx(sessions):
    return {"sessions": sessions, "base_template": _base_template()}


def _build_verify_url(user):
    """Build the email verification URL for a user."""
    app_url = config_manager.get_setting(
        "app_url", default="http://127.0.0.1:5005", env_var="APP_URL"
    )
    return f"{app_url.rstrip('/')}/auth/verify?token={user.verification_token}"


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("researcher.index"))

    next_url = request.args.get("next") if request.method == "GET" else None
    if request.method != "POST":
        return render_template("login.html", **_login_ctx(next_url))

    next_url = request.args.get("next")
    ctx = _login_ctx(next_url)

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    if not username or not password:
        flash("Username and password required.", "danger")
        return render_template("login.html", **ctx)

    if ctx["captcha"]:
        ok, err = captcha_service.verify_response(session, request.form)
        if not ok:
            flash(err or "CAPTCHA verification failed.", "danger")
            return render_template("login.html", **ctx)

    user = User.query.filter_by(username=username).first()

    if user and is_locked_out(user):
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        flash(
            "Account is temporarily locked due to too many failed attempts. Please try again later.",
            "danger",
        )
        return render_template("login.html", **ctx)

    if (
        not user
        or not user.password_hash
        or not check_password_hash(user.password_hash, password)
    ):
        if user:
            record_failed_login(user)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            remaining = max(
                0,
                (config_manager.get("password_max_failed_attempts") or 5)
                - (user.failed_login_attempts or 0),
            )
            if remaining > 0:
                flash(
                    f"Invalid username or password. {remaining} attempt(s) remaining before lockout.",
                    "danger",
                )
            else:
                flash("Account locked due to too many failed attempts.", "danger")
        else:
            flash("Invalid username or password.", "danger")
        return render_template("login.html", **ctx)

    if not user.is_active:
        flash("Account is disabled.", "danger")
        return render_template("login.html", **ctx)

    # Email verification — only enforce if admin has explicitly required it
    require_email_verify = config_manager.get(
        "registration_require_email_verification", False
    )
    if require_email_verify and not getattr(user, "email_verified", True):
        flash(
            "Please verify your email before logging in. Check your inbox or resend verification.",
            "warning",
        )
        return redirect(url_for("auth.verify_pending", email=user.email or ""))

    # Successful login — reset lockout counters
    record_successful_login(user)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    # ── MFA check — only if admin has enabled MFA feature ─────────────────────────
    mfa_feature_enabled = config_manager.get("mfa_enabled", False)
    if mfa_feature_enabled and (mfa_service.is_mfa_required(user) or user.mfa_enabled):
        # Only challenge MFA if user has enrolled at least one method
        methods = mfa_service.get_active_methods(user)
        if methods:
            mfa_service.set_pending_user(user.id)
            if "email" in methods:
                mfa_service.send_email_otp(user)
            next_param = request.form.get("next") or request.args.get("next") or ""
            return redirect(url_for("auth.mfa_challenge", next=next_param))

    # Create session record BEFORE login_user for proper auth state
    session_service.create_session(user)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    login_user(user, remember=bool(request.form.get("remember")))
    session.permanent = True  # Use PERMANENT_SESSION_LIFETIME from config

    # Redirect to password change if expired or admin-flagged
    if is_password_expired(user) or getattr(user, "must_change_password", False):
        flash("Your password has expired. Please choose a new password.", "warning")
        return redirect(url_for("auth.change_password"))

    next_url = (
        request.form.get("next")
        or request.args.get("next")
        or url_for("researcher.index")
    )
    return redirect(next_url)


@auth_bp.route("/logout")
@login_required
def logout():
    session_service.terminate_current_session()
    logout_user()
    return redirect(url_for("landing"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("researcher.index"))

    # ── Registration mode gate ─────────────────────────────────────────────
    reg_mode = (config_manager.get("registration_mode") or "open").strip().lower()
    invite_token = (
        request.args.get("invite") or request.form.get("invite") or ""
    ).strip()
    invite_obj = None

    if reg_mode == "disabled":
        flash(
            "New account registration is currently disabled. Please contact an administrator.",
            "danger",
        )
        return redirect(url_for("auth.login"))

    if reg_mode == "invite":
        if not invite_token:
            flash("Registration requires an invitation link.", "danger")
            return redirect(url_for("auth.login"))

        invite_obj = UserInvite.query.filter_by(token=invite_token).first()
        if not invite_obj or not invite_obj.is_valid:
            flash("This invitation link is invalid or has expired.", "danger")
            return redirect(url_for("auth.login"))

    if request.method != "POST":
        return render_template("register.html", **_register_ctx(invite_token, reg_mode))

    reg_captcha = _captcha_data("registration_captcha_enabled")
    if config_manager.get("registration_captcha_enabled", False):
        ok, err = captcha_service.verify_response(session, request.form)
        if not ok:
            flash(err or "CAPTCHA verification failed.", "danger")
            return render_template(
                "register.html",
                **_register_ctx(invite_token, reg_mode, reg_captcha),
            )

    username = (request.form.get("username") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    confirm = request.form.get("confirm_password") or ""

    if not username or len(username) < 2:
        flash("Username must be at least 2 characters.", "danger")
        return render_template("register.html", **_register_ctx(invite_token, reg_mode))
    if not email or "@" not in email:
        flash("Valid email is required.", "danger")
        return render_template("register.html", **_register_ctx(invite_token, reg_mode))

    if reg_mode == "domain":
        allowed_raw = config_manager.get("registration_allowed_domains") or ""
        allowed = {d.strip().lower() for d in allowed_raw.split(",") if d.strip()}
        if allowed:
            email_domain = email.split("@", 1)[-1].lower()
            if email_domain not in allowed:
                flash(
                    "Registration is restricted. Your email domain is not permitted.",
                    "danger",
                )
                return render_template(
                    "register.html", **_register_ctx(invite_token, reg_mode)
                )

    if invite_obj and invite_obj.email and invite_obj.email.lower() != email:
        flash("This invitation is for a different email address.", "danger")
        return render_template("register.html", **_register_ctx(invite_token, reg_mode))

    if password != confirm:
        flash("Passwords do not match.", "danger")
        return render_template("register.html", **_register_ctx(invite_token, reg_mode))

    ok, pw_errors = validate_password(password)
    if not ok:
        for err in pw_errors:
            flash(err, "danger")
        return render_template("register.html", **_register_ctx(invite_token, reg_mode))

    if User.query.filter_by(username=username).first():
        flash("Username already taken.", "danger")
        return render_template("register.html", **_register_ctx(invite_token, reg_mode))
    if User.query.filter(User.email == email).first():
        flash("Email already registered.", "danger")
        return render_template("register.html", **_register_ctx(invite_token, reg_mode))

    # Determine role to assign
    auto_role_name = (
        (invite_obj.role_name if invite_obj and invite_obj.role_name else None)
        or config_manager.get("registration_auto_assign_role")
        or "User"
    )
    user_role = Role.query.filter_by(name=auto_role_name).first()
    if not user_role:
        user_role = Role(name=auto_role_name)
        user_role.set_permissions(["researcher:view", "researcher:contribute"])
        try:
            db.session.add(user_role)
            db.session.flush()
        except Exception:
            db.session.rollback()
            # Role was created by another request - fetch it
            user_role = Role.query.filter_by(name=auto_role_name).first()
            if not user_role:
                flash("Could not assign role to new user.", "danger")
                return render_template(
                    "register.html", **_register_ctx(invite_token, reg_mode)
                )

    # Approval mode — account starts inactive until admin approves
    starts_active = reg_mode != "approval"

    # Email verification — only required if admin has explicitly enabled it
    require_email_verify = config_manager.get(
        "registration_require_email_verification", False
    )

    pw_hash = generate_password_hash(password)
    user = User(
        username=username,
        email=email,
        password_hash=pw_hash,
        role_id=user_role.id,
        is_active=starts_active,
        email_verified=not require_email_verify,
        password_changed_at=utcnow_naive(),
        invite_id=invite_obj.id if invite_obj else None,
    )
    if require_email_verify:
        user.generate_verification_token(expires_hours=24)
    db.session.add(user)
    db.session.flush()  # get user.id for history record
    record_password_change(user.id, pw_hash)

    # Consume invite token
    if invite_obj:
        invite_obj.use_count = (invite_obj.use_count or 0) + 1
        invite_obj.used_at = utcnow_naive()
        invite_obj.used_by_id = user.id

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Registration failed. Please try again.", "danger")
        return render_template("register.html", **_register_ctx(invite_token, reg_mode))

    if reg_mode == "approval":
        flash(
            "Your account is pending admin approval. You will be notified when it is activated.",
            "info",
        )
        return redirect(url_for("auth.login"))

    # If email verification is required, show pending page or send email
    if require_email_verify:
        verify_url = _build_verify_url(user)

        if email_is_configured():
            ok, _ = send_verification_email(user, verify_url)
            if ok:
                flash(
                    "Account created. Please check your email to verify your account.",
                    "success",
                )
            else:
                flash(
                    "Account created but verification email could not be sent. Use the link below to verify.",
                    "warning",
                )
        else:
            flash(
                "Account created. Email service not configured. Use the link below to verify your account.",
                "warning",
            )
        return render_template(
            "verify_pending.html", verify_url=verify_url, email=email
        )
    else:
        # Email verification not required — user can login immediately
        flash("Account created. You can now log in.", "success")
        return redirect(url_for("auth.login"))


@auth_bp.route("/auth/verify")
def verify_email():
    token = request.args.get("token", "").strip()
    if not token:
        flash("Invalid verification link.", "danger")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(verification_token=token).first()
    if not user:
        flash("Invalid or expired verification link.", "danger")
        return redirect(url_for("auth.login"))
    if (
        user.verification_token_expires
        and user.verification_token_expires < utcnow_naive()
    ):
        flash("Verification link has expired. Please request a new one.", "warning")
        return redirect(url_for("auth.resend_verification", email=user.email or ""))

    user.email_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Email verification failed. Please try again.", "danger")
        return redirect(url_for("auth.login"))
    flash("Email verified. You can now log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/auth/verify-pending")
def verify_pending():
    email = request.args.get("email", "")
    return render_template("verify_pending.html", verify_url=None, email=email)


@auth_bp.route("/auth/resend-verification", methods=["GET", "POST"])
def resend_verification():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        if not email:
            flash("Email required.", "danger")
            return render_template("resend_verification.html", email=email)
        user = User.query.filter(User.email == email).first()
        if not user:
            flash("No account with that email.", "danger")
            return render_template("resend_verification.html", email=email)
        if getattr(user, "email_verified", False):
            flash("Account already verified. Please log in.", "success")
            return redirect(url_for("auth.login"))

        user.generate_verification_token(expires_hours=24)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Could not generate verification token.", "danger")
            return render_template("resend_verification.html", email=email)
        verify_url = _build_verify_url(user)
        ok, _ = send_verification_email(user, verify_url)
        if ok:
            flash("Verification email sent. Check your inbox.", "success")
        else:
            flash(
                f"Could not send email. Use this link to verify: {verify_url}",
                "warning",
            )
        return redirect(url_for("auth.verify_pending", email=email))
    return render_template("resend_verification.html")


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user
    if request.method != "POST":
        return render_template("profile.html", **_profile_ctx(user))

    display_name = (request.form.get("display_name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    phone_number = (request.form.get("phone_number") or "").strip()
    new_password = request.form.get("new_password") or ""
    confirm = request.form.get("confirm_password") or ""

    if display_name:
        user.display_name = display_name
    if phone_number != (user.phone_number or ""):
        user.phone_number = phone_number or None
    if email and email != user.email:
        existing = User.query.filter(User.email == email, User.id != user.id).first()
        if existing:
            flash("Email already in use.", "danger")
            return render_template("profile.html", **_profile_ctx(user))
        user.email = email
        user.email_verified = False
        user.verification_token = None
        user.verification_token_expires = None
        if email:
            user.generate_verification_token(expires_hours=24)
            verify_url = _build_verify_url(user)
            ok, _ = send_verification_email(user, verify_url)
            if ok:
                flash(
                    "Email updated. A verification link was sent to your new email.",
                    "success",
                )
            else:
                flash("Email updated. Verification email could not be sent.", "warning")

    if new_password:
        if new_password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("profile.html", **_profile_ctx(user))
        pw_ok, pw_errors = validate_password(new_password, user=user)
        if not pw_ok:
            for err in pw_errors:
                flash(err, "danger")
            return render_template("profile.html", **_profile_ctx(user))
        pw_hash = generate_password_hash(new_password)
        user.password_hash = pw_hash
        user.password_changed_at = utcnow_naive()
        user.must_change_password = False
        record_password_change(user.id, pw_hash)
        flash("Password updated.", "success")

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Failed to save profile. Please try again.", "danger")
        return render_template("profile.html", **_profile_ctx(user))
    return redirect(url_for("auth.profile"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Force-change password — used on expiry or must_change_password flag."""
    user = current_user
    if request.method != "POST":
        return render_template("change_password.html", **_change_password_ctx())

    new_password = request.form.get("new_password") or ""
    confirm = request.form.get("confirm_password") or ""

    if not new_password:
        flash("New password is required.", "danger")
        return render_template("change_password.html", **_change_password_ctx())
    if new_password != confirm:
        flash("Passwords do not match.", "danger")
        return render_template("change_password.html", **_change_password_ctx())

    pw_ok, pw_errors = validate_password(new_password, user=user)
    if not pw_ok:
        for err in pw_errors:
            flash(err, "danger")
        return render_template("change_password.html", **_change_password_ctx())

    pw_hash = generate_password_hash(new_password)
    user.password_hash = pw_hash
    user.password_changed_at = utcnow_naive()
    user.must_change_password = False
    record_password_change(user.id, pw_hash)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Failed to change password. Please try again.", "danger")
        return render_template("change_password.html", **_change_password_ctx())

    flash("Password changed successfully.", "success")
    return redirect(url_for("researcher.index"))


# ══ MFA routes ══════════════════════════════════════════════════════════════════


@auth_bp.route("/auth/mfa", methods=["GET", "POST"])
def mfa_challenge():
    """Step 2 of the two-step login: verify the MFA factor."""
    next_url = request.args.get("next") or ""
    user_id = mfa_service.get_pending_user_id()
    if not user_id:
        return redirect(url_for("auth.login"))

    user = get_entity(User, user_id)
    if not user:
        mfa_service.clear_pending_user()
        return redirect(url_for("auth.login"))

    methods = mfa_service.get_active_methods(user) or ["email"]

    if request.method != "POST":
        return render_template(
            "mfa_challenge.html", **_mfa_challenge_ctx(user, next_url)
        )

    method = (request.form.get("method") or "").strip()
    code = (request.form.get("code") or "").strip()

    verified = False
    if method == "totp" and "totp" in methods:
        verified = mfa_service.verify_totp(user, code)
    elif method == "email":
        verified = mfa_service.verify_email_otp(code)
    elif method == "sms":
        verified = mfa_service.verify_sms_otp(code)
    elif method == "backup":
        verified = mfa_service.verify_backup_code(user, code)
        if verified:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                verified = False

    if not verified:
        flash("Invalid or expired code. Please try again.", "danger")
        return render_template(
            "mfa_challenge.html", **_mfa_challenge_ctx(user, next_url)
        )

    # MFA passed — complete login
    mfa_service.clear_pending_user()
    user.mfa_last_used_at = utcnow_naive()

    # Create session record BEFORE login_user for proper auth state
    session_service.create_session(user)
    record_successful_login(user)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    login_user(user, remember=False)
    session.permanent = True

    if is_password_expired(user) or getattr(user, "must_change_password", False):
        flash("Your password has expired. Please choose a new password.", "warning")
        return redirect(url_for("auth.change_password"))

    return redirect(next_url or url_for("researcher.index"))


@auth_bp.route("/auth/mfa/resend-otp", methods=["POST"])
def mfa_resend_otp():
    """Resend the email or SMS OTP for the pending MFA challenge."""
    user_id = mfa_service.get_pending_user_id()
    if not user_id:
        return redirect(url_for("auth.login"))
    user = get_entity(User, user_id)
    if not user:
        return redirect(url_for("auth.login"))

    method = request.form.get("method", "email")
    if method == "sms":
        ok, _ = mfa_service.send_sms_otp(user)
        if ok:
            flash("A new code has been sent to your phone.", "success")
        else:
            flash("Failed to send SMS code.", "danger")
    else:
        ok, _ = mfa_service.send_email_otp(user)
        if ok:
            flash("A new code has been sent to your email.", "success")
        else:
            flash(
                "Failed to send email code. Please try TOTP or a backup code.", "danger"
            )
    next_url = request.form.get("next") or request.args.get("next") or ""
    return redirect(
        url_for("auth.mfa_challenge", next=next_url)
        if next_url
        else url_for("auth.mfa_challenge")
    )


@auth_bp.route("/auth/mfa/setup", methods=["GET", "POST"])
@login_required
def mfa_setup():
    """Enroll the current user in TOTP MFA."""
    user = current_user

    if request.method == "GET":
        tmp_secret = mfa_service.generate_totp_secret()
        session["mfa_setup_secret"] = tmp_secret
        uri = mfa_service.get_totp_provisioning_uri(user, secret=tmp_secret)
        qr_b64 = mfa_service.build_qr_b64(uri)
        return render_template("mfa_setup.html", **_mfa_setup_ctx(tmp_secret, qr_b64))

    code = (request.form.get("code") or "").strip()
    tmp_secret = session.get("mfa_setup_secret", "")
    if not tmp_secret:
        flash("Setup session expired. Please start again.", "danger")
        return redirect(url_for("auth.mfa_setup"))

    if not mfa_service.verify_totp_with_secret(tmp_secret, code):
        uri = mfa_service.get_totp_provisioning_uri(user, secret=tmp_secret)
        qr_b64 = mfa_service.build_qr_b64(uri)
        flash("Code did not match. Please try again.", "danger")
        return render_template("mfa_setup.html", **_mfa_setup_ctx(tmp_secret, qr_b64))

    # Commit TOTP enrollment
    session.pop("mfa_setup_secret", None)
    user.mfa_totp_secret = tmp_secret
    mfa_service.set_active_methods(
        user, list(set(mfa_service.get_active_methods(user) + ["totp"]))
    )
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Failed to save authenticator app enrollment.", "danger")
        return redirect(url_for("auth.mfa_setup"))
    flash("Authenticator app enrolled successfully.", "success")
    return redirect(url_for("auth.mfa_backup_codes"))


@auth_bp.route("/auth/mfa/setup/sms", methods=["GET", "POST"])
@login_required
def mfa_setup_sms():
    """Enroll the current user in SMS OTP MFA."""
    user = current_user
    sent = False

    if request.method == "GET":
        return render_template(
            "mfa_setup_sms.html", **_mfa_setup_sms_ctx(False, user.phone_number or "")
        )

    action = (request.form.get("action") or "send").strip()

    if action == "send":
        phone = (request.form.get("phone_number") or "").strip()
        if not phone:
            flash("Phone number is required.", "danger")
            return render_template(
                "mfa_setup_sms.html", **_mfa_setup_sms_ctx(False, phone)
            )
        user.phone_number = phone
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Failed to save phone number.", "danger")
            return render_template(
                "mfa_setup_sms.html", **_mfa_setup_sms_ctx(False, phone)
            )
        ok, _ = mfa_service.send_sms_otp(user)
        if ok:
            flash(
                "Verification code sent. Enter it below to confirm SMS OTP.", "success"
            )
            sent = True
        else:
            flash("Failed to send SMS.", "danger")
        return render_template("mfa_setup_sms.html", **_mfa_setup_sms_ctx(sent, phone))

    if action == "verify":
        code = (request.form.get("code") or "").strip()
        phone = (request.form.get("phone_number") or user.phone_number or "").strip()
        if not phone:
            flash("Phone number is missing. Please enter it again.", "danger")
            return redirect(url_for("auth.mfa_setup_sms"))
        if mfa_service.verify_sms_otp(code):
            mfa_service.set_active_methods(
                user, list(set(mfa_service.get_active_methods(user) + ["sms"]))
            )
            if not user.mfa_enabled:
                user.mfa_enabled = True
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                flash("Failed to save SMS OTP enrollment.", "danger")
                return render_template(
                    "mfa_setup_sms.html", **_mfa_setup_sms_ctx(True, phone)
                )
            flash(
                "SMS OTP enrolled successfully. Your phone number has been verified.",
                "success",
            )
            return redirect(url_for("auth.profile"))
        flash("Invalid or expired code. Please request a new one.", "danger")
        return render_template("mfa_setup_sms.html", **_mfa_setup_sms_ctx(True, phone))

    # Unknown action — fall back to GET view with error
    flash("Invalid action. Please try again.", "danger")
    return redirect(url_for("auth.mfa_setup_sms"))


@auth_bp.route("/auth/mfa/backup-codes", methods=["GET", "POST"])
@login_required
def mfa_backup_codes():
    """Generate (or re-generate) backup codes for the current user."""
    user = current_user
    new_codes: list[str] = []

    if request.method == "POST":
        new_codes = mfa_service.generate_backup_codes(user)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Failed to generate backup codes.", "danger")
            return redirect(url_for("auth.profile"))
        flash(
            f"{len(new_codes)} backup codes generated. Save them somewhere safe — you will not see them again.",
            "success",
        )

    remaining = getattr(user, "mfa_backup_codes_remaining", 0) or 0
    return render_template(
        "mfa_backup_codes.html", **_mfa_backup_codes_ctx(new_codes, remaining)
    )


@auth_bp.route("/auth/mfa/disable", methods=["POST"])
@login_required
def mfa_disable():
    """Remove all MFA methods for the current user (self-service)."""
    user = current_user
    user.mfa_enabled = False
    user.mfa_methods = ""
    user.mfa_totp_secret = None
    user.mfa_backup_codes_hash = None
    user.mfa_backup_codes_remaining = 0
    # Clear any pending MFA challenge in session
    mfa_service.clear_pending_user()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Failed to disable MFA.", "danger")
        return redirect(url_for("auth.profile"))
    flash("Multi-factor authentication has been disabled.", "warning")
    return redirect(url_for("auth.profile"))


# ══ Session management (user self-service) ══════════════════════════════════════


@auth_bp.route("/auth/sessions")
@login_required
def my_sessions():
    """List the current user's active sessions."""
    sessions = (
        UserSession.query.filter_by(user_id=current_user.id, is_active=True)
        .order_by(UserSession.last_seen_at.desc())
        .all()
    )
    return render_template("my_sessions.html", **_sessions_ctx(sessions))


@auth_bp.route("/auth/sessions/<int:session_id>/revoke", methods=["POST"])
@login_required
def revoke_session(session_id):
    """Revoke one of the current user's own sessions."""
    user_session = get_entity_or_404(UserSession, session_id)
    if user_session.user_id != current_user.id:
        flash("Not authorised.", "danger")
        return redirect(url_for("auth.my_sessions"))
    session_service.revoke_session(session_id, revoked_by_id=current_user.id)
    flash("Session revoked.", "success")
    return redirect(url_for("auth.my_sessions"))
