"""Auth routes — login, logout, register, verify, profile (Flask-Login)."""
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user

from app.config_manager import config_manager
from app.database import db
from app.models.core import User, Role
from app.routes.route_entity_lookup import get_entity, get_entity_or_404
from app.services.email_service import is_configured as smtp_configured, send_verification_email
from app.services.password_policy_service import (
    validate_password, record_password_change,
    is_password_expired, is_locked_out,
    record_failed_login, record_successful_login,
)
from app.services import mfa_service
from app.services import session_service
from app.core.time_utils import utcnow_naive
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint('auth', __name__)


def _base_template():
    """Pick partial layout for SPA AJAX requests."""
    if (request.args.get('partial') or '').strip().lower() in ('1', 'true') \
       or request.headers.get('X-Requested-With') == 'SPA':
        return 'base_embed.html'
    return 'base.html'


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('researcher.index'))
    if request.method != 'POST':
        return render_template('login.html', next=request.args.get('next'))

    username = (request.form.get('username') or '').strip()
    password = request.form.get('password') or ''
    if not username or not password:
        flash('Username and password required.', 'danger')
        return render_template('login.html', next=request.args.get('next'))

    user = User.query.filter_by(username=username).first()

    # Check lockout before testing password (prevents timing oracle)
    if user and is_locked_out(user):
        db.session.commit()
        flash('Account is temporarily locked due to too many failed attempts. Please try again later.', 'danger')
        return render_template('login.html', next=request.args.get('next'))

    if not user or not user.password_hash or not check_password_hash(user.password_hash, password):
        if user:
            record_failed_login(user)
            db.session.commit()
            remaining = max(0, (config_manager.get('password_max_failed_attempts') or 5) - (user.failed_login_attempts or 0))
            if remaining > 0:
                flash(f'Invalid username or password. {remaining} attempt(s) remaining before lockout.', 'danger')
            else:
                flash('Account locked due to too many failed attempts.', 'danger')
        else:
            flash('Invalid username or password.', 'danger')
        return render_template('login.html', next=request.args.get('next'))

    if not user.is_active:
        flash('Account is disabled.', 'danger')
        return render_template('login.html', next=request.args.get('next'))

    if not getattr(user, 'email_verified', True):
        flash('Please verify your email before logging in. Check your inbox or resend verification.', 'warning')
        return redirect(url_for('auth.verify_pending', email=user.email or ''))

    # Successful login — reset lockout counters
    record_successful_login(user)
    db.session.commit()

    # ── MFA check ───────────────────────────────────────────────────────────
    if mfa_service.is_mfa_required(user) or user.mfa_enabled:
        mfa_service.set_pending_user(user.id)
        # Pre-send email OTP if that's the only/default method
        methods = mfa_service.get_active_methods(user)
        if 'email' in methods or (not methods and config_manager.get('mfa_email_otp_enabled')):
            mfa_service.send_email_otp(user)
        next_url = request.form.get('next') or request.args.get('next') or ''
        return redirect(url_for('auth.mfa_challenge', next=next_url))

    login_user(user, remember=bool(request.form.get('remember')))
    session.permanent = True  # Use PERMANENT_SESSION_LIFETIME from config
    session_service.create_session(user)
    db.session.commit()

    # Redirect to password change if expired or admin-flagged
    if is_password_expired(user) or getattr(user, 'must_change_password', False):
        flash('Your password has expired. Please choose a new password.', 'warning')
        return redirect(url_for('auth.change_password'))

    next_url = request.form.get('next') or request.args.get('next') or url_for('researcher.index')
    return redirect(next_url)


@auth_bp.route('/logout')
@login_required
def logout():
    session_service.terminate_current_session()
    logout_user()
    return redirect(url_for('landing'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('researcher.index'))

    # ── Registration mode gate ─────────────────────────────────────────────
    reg_mode = (config_manager.get('registration_mode') or 'open').strip().lower()
    invite_token = (request.args.get('invite') or request.form.get('invite') or '').strip()
    invite_obj = None

    if reg_mode == 'disabled':
        flash('New account registration is currently disabled. Please contact an administrator.', 'danger')
        return redirect(url_for('auth.login'))

    if reg_mode == 'invite':
        if not invite_token:
            flash('Registration requires an invitation link.', 'danger')
            return redirect(url_for('auth.login'))
        from app.models.user_management import UserInvite
        invite_obj = UserInvite.query.filter_by(token=invite_token).first()
        if not invite_obj or not invite_obj.is_valid:
            flash('This invitation link is invalid or has expired.', 'danger')
            return redirect(url_for('auth.login'))

    if request.method != 'POST':
        return render_template('register.html', invite_token=invite_token, reg_mode=reg_mode)

    username = (request.form.get('username') or '').strip()
    email = (request.form.get('email') or '').strip().lower()
    password = request.form.get('password') or ''
    confirm = request.form.get('confirm_password') or ''

    if not username or len(username) < 2:
        flash('Username must be at least 2 characters.', 'danger')
        return render_template('register.html', invite_token=invite_token, reg_mode=reg_mode)
    if not email or '@' not in email:
        flash('Valid email is required.', 'danger')
        return render_template('register.html', invite_token=invite_token, reg_mode=reg_mode)

    # Domain allowlist check
    if reg_mode == 'domain':
        allowed_raw = config_manager.get('registration_allowed_domains') or ''
        allowed = {d.strip().lower() for d in allowed_raw.split(',') if d.strip()}
        if allowed:
            email_domain = email.split('@', 1)[-1].lower()
            if email_domain not in allowed:
                flash(f'Registration is restricted. Your email domain is not permitted.', 'danger')
                return render_template('register.html', invite_token=invite_token, reg_mode=reg_mode)

    # Validate invite email restriction
    if invite_obj and invite_obj.email and invite_obj.email.lower() != email:
        flash('This invitation is for a different email address.', 'danger')
        return render_template('register.html', invite_token=invite_token, reg_mode=reg_mode)

    if password != confirm:
        flash('Passwords do not match.', 'danger')
        return render_template('register.html', invite_token=invite_token, reg_mode=reg_mode)

    ok, pw_errors = validate_password(password)
    if not ok:
        for err in pw_errors:
            flash(err, 'danger')
        return render_template('register.html', invite_token=invite_token, reg_mode=reg_mode)

    if User.query.filter_by(username=username).first():
        flash('Username already taken.', 'danger')
        return render_template('register.html', invite_token=invite_token, reg_mode=reg_mode)
    if User.query.filter(User.email == email).first():
        flash('Email already registered.', 'danger')
        return render_template('register.html', invite_token=invite_token, reg_mode=reg_mode)

    # Determine role to assign
    auto_role_name = (
        (invite_obj.role_name if invite_obj and invite_obj.role_name else None)
        or config_manager.get('registration_auto_assign_role')
        or 'User'
    )
    user_role = Role.query.filter_by(name=auto_role_name).first()
    if not user_role:
        user_role = Role(name='User')
        user_role.set_permissions(['researcher:view', 'researcher:contribute'])
        db.session.add(user_role)
        db.session.flush()

    # Approval mode — account starts inactive until admin approves
    starts_active = reg_mode != 'approval'

    pw_hash = generate_password_hash(password)
    user = User(
        username=username,
        email=email,
        password_hash=pw_hash,
        role_id=user_role.id,
        is_active=starts_active,
        email_verified=False,
        password_changed_at=utcnow_naive(),
        invite_id=invite_obj.id if invite_obj else None,
    )
    user.generate_verification_token(expires_hours=24)
    db.session.add(user)
    db.session.flush()  # get user.id for history record
    record_password_change(user.id, pw_hash)

    # Consume invite token
    if invite_obj:
        invite_obj.use_count = (invite_obj.use_count or 0) + 1
        invite_obj.used_at = utcnow_naive()
        invite_obj.used_by_id = user.id

    db.session.commit()

    app_url = config_manager.get_setting('app_url', default='http://127.0.0.1:5005', env_var='APP_URL')
    verify_url = f"{app_url.rstrip('/')}/auth/verify?token={user.verification_token}"

    if reg_mode == 'approval':
        flash('Your account is pending admin approval. You will be notified when it is activated.', 'info')
        return redirect(url_for('auth.login'))

    ok, err = send_verification_email(user, verify_url)
    if ok:
        flash('Account created. Please check your email to verify your account.', 'success')
        return redirect(url_for('auth.verify_pending', email=email))
    flash('Account created. Email could not be sent. Use the link below to verify.', 'warning')
    return render_template('verify_pending.html', verify_url=verify_url, email=email)


@auth_bp.route('/auth/verify')
def verify_email():
    token = request.args.get('token', '').strip()
    if not token:
        flash('Invalid verification link.', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(verification_token=token).first()
    if not user:
        flash('Invalid or expired verification link.', 'danger')
        return redirect(url_for('auth.login'))
    if user.verification_token_expires and user.verification_token_expires < utcnow_naive():
        flash('Verification link has expired. Please request a new one.', 'warning')
        return redirect(url_for('auth.resend_verification'))

    user.email_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    db.session.commit()
    flash('Email verified. You can now log in.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/auth/verify-pending')
def verify_pending():
    email = request.args.get('email', '')
    return render_template('verify_pending.html', verify_url=None, email=email)


@auth_bp.route('/auth/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        if not email:
            flash('Email required.', 'danger')
            return render_template('resend_verification.html')
        user = User.query.filter(User.email == email).first()
        if not user:
            flash('No account with that email.', 'danger')
            return render_template('resend_verification.html')
        if getattr(user, 'email_verified', False):
            flash('Account already verified. Please log in.', 'success')
            return redirect(url_for('auth.login'))

        user.generate_verification_token(expires_hours=24)
        db.session.commit()
        app_url = config_manager.get_setting('app_url', default='http://127.0.0.1:5005', env_var='APP_URL')
        verify_url = f"{app_url.rstrip('/')}/auth/verify?token={user.verification_token}"
        ok, err = send_verification_email(user, verify_url)
        if ok:
            flash('Verification email sent. Check your inbox.', 'success')
        else:
            flash(f'Could not send email. Use this link to verify: {verify_url}', 'warning')
        return redirect(url_for('auth.verify_pending', email=email))
    return render_template('resend_verification.html')


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = current_user
    if request.method != 'POST':
        return render_template('profile.html', user=user, base_template=_base_template())

    display_name = (request.form.get('display_name') or '').strip()
    email = (request.form.get('email') or '').strip().lower()
    phone_number = (request.form.get('phone_number') or '').strip()
    new_password = request.form.get('new_password') or ''
    confirm = request.form.get('confirm_password') or ''

    if display_name:
        user.display_name = display_name
    if phone_number != (user.phone_number or ''):
        user.phone_number = phone_number or None
    if email and email != user.email:
        existing = User.query.filter(User.email == email, User.id != user.id).first()
        if existing:
            flash('Email already in use.', 'danger')
            return render_template('profile.html', user=user, base_template=_base_template())
        user.email = email
        user.email_verified = False
        user.verification_token = None
        user.verification_token_expires = None
        if email:
            user.generate_verification_token(expires_hours=24)
            app_url = config_manager.get_setting('app_url', default='http://127.0.0.1:5005', env_var='APP_URL')
            verify_url = f"{app_url.rstrip('/')}/auth/verify?token={user.verification_token}"
            ok, _ = send_verification_email(user, verify_url)
            if ok:
                flash('Email updated. A verification link was sent to your new email.', 'success')
            else:
                flash('Email updated. Verification email could not be sent.', 'warning')

    if new_password:
        if new_password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('profile.html', user=user, base_template=_base_template())
        pw_ok, pw_errors = validate_password(new_password, user=user)
        if not pw_ok:
            for err in pw_errors:
                flash(err, 'danger')
            return render_template('profile.html', user=user, base_template=_base_template())
        pw_hash = generate_password_hash(new_password)
        user.password_hash = pw_hash
        user.password_changed_at = utcnow_naive()
        user.must_change_password = False
        record_password_change(user.id, pw_hash)
        flash('Password updated.', 'success')

    db.session.commit()
    return redirect(url_for('auth.profile'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Force-change password — used on expiry or must_change_password flag."""
    user = current_user
    if request.method != 'POST':
        return render_template('change_password.html', base_template=_base_template())

    new_password = request.form.get('new_password') or ''
    confirm = request.form.get('confirm_password') or ''

    if not new_password:
        flash('New password is required.', 'danger')
        return render_template('change_password.html', base_template=_base_template())
    if new_password != confirm:
        flash('Passwords do not match.', 'danger')
        return render_template('change_password.html', base_template=_base_template())

    pw_ok, pw_errors = validate_password(new_password, user=user)
    if not pw_ok:
        for err in pw_errors:
            flash(err, 'danger')
        return render_template('change_password.html', base_template=_base_template())

    pw_hash = generate_password_hash(new_password)
    user.password_hash = pw_hash
    user.password_changed_at = utcnow_naive()
    user.must_change_password = False
    record_password_change(user.id, pw_hash)
    db.session.commit()

    flash('Password changed successfully.', 'success')
    return redirect(url_for('researcher.index'))


# ══ MFA routes ══════════════════════════════════════════════════════════════════

@auth_bp.route('/auth/mfa', methods=['GET', 'POST'])
def mfa_challenge():
    """Step 2 of the two-step login: verify the MFA factor."""
    user_id = mfa_service.get_pending_user_id()
    if not user_id:
        return redirect(url_for('auth.login'))

    user = get_entity(User, user_id)
    if not user:
        mfa_service.clear_pending_user()
        return redirect(url_for('auth.login'))

    methods = mfa_service.get_active_methods(user)
    if not methods:
        # Fallback: if no methods enrolled but MFA is required, use email OTP
        methods = ['email']

    if request.method != 'POST':
        return render_template('mfa_challenge.html', methods=methods,
                               base_template=_base_template())

    method = (request.form.get('method') or '').strip()
    code = (request.form.get('code') or '').strip()

    verified = False
    if method == 'totp' and 'totp' in methods:
        verified = mfa_service.verify_totp(user, code)
    elif method == 'email':
        verified = mfa_service.verify_email_otp(code)
    elif method == 'sms':
        verified = mfa_service.verify_sms_otp(code)
    elif method == 'backup':
        verified = mfa_service.verify_backup_code(user, code)
        if verified:
            db.session.commit()

    if not verified:
        flash('Invalid or expired code. Please try again.', 'danger')
        return render_template('mfa_challenge.html', methods=methods,
                               base_template=_base_template())

    # MFA passed — complete login
    mfa_service.clear_pending_user()
    user.mfa_last_used_at = utcnow_naive()
    login_user(user, remember=False)
    session.permanent = True
    session_service.create_session(user)
    record_successful_login(user)
    db.session.commit()

    if is_password_expired(user) or getattr(user, 'must_change_password', False):
        flash('Your password has expired. Please choose a new password.', 'warning')
        return redirect(url_for('auth.change_password'))

    next_url = request.args.get('next') or url_for('researcher.index')
    return redirect(next_url)


@auth_bp.route('/auth/mfa/resend-otp', methods=['POST'])
def mfa_resend_otp():
    """Resend the email or SMS OTP for the pending MFA challenge."""
    user_id = mfa_service.get_pending_user_id()
    if not user_id:
        return redirect(url_for('auth.login'))
    user = get_entity(User, user_id)
    if not user:
        return redirect(url_for('auth.login'))

    method = request.form.get('method', 'email')
    if method == 'sms':
        ok, err = mfa_service.send_sms_otp(user)
        if ok:
            flash('A new code has been sent to your phone.', 'success')
        else:
            flash(f'Failed to send SMS code: {err}', 'danger')
    else:
        ok, _ = mfa_service.send_email_otp(user)
        if ok:
            flash('A new code has been sent to your email.', 'success')
        else:
            flash('Failed to send email code. Please try TOTP or a backup code.', 'danger')
    return redirect(url_for('auth.mfa_challenge'))


@auth_bp.route('/auth/mfa/setup', methods=['GET', 'POST'])
@login_required
def mfa_setup():
    """Enroll the current user in TOTP MFA."""
    user = current_user

    if request.method == 'GET':
        # Generate a new secret (not yet committed — show QR first)
        tmp_secret = mfa_service.generate_totp_secret()
        session['mfa_setup_secret'] = tmp_secret
        # Build provisioning URI with temp secret
        user.mfa_totp_secret = tmp_secret  # temp for URI generation
        uri = mfa_service.get_totp_provisioning_uri(user)
        user.mfa_totp_secret = current_user.mfa_totp_secret  # restore (not yet committed)
        qr_b64 = mfa_service.build_qr_b64(uri)
        return render_template('mfa_setup.html', secret=tmp_secret, qr_b64=qr_b64,
                               uri=uri, base_template=_base_template())

    # POST: verify the code before activating
    code = (request.form.get('code') or '').strip()
    tmp_secret = session.get('mfa_setup_secret', '')
    if not tmp_secret:
        flash('Setup session expired. Please start again.', 'danger')
        return redirect(url_for('auth.mfa_setup'))

    # Temporarily set secret for verification
    old_secret = user.mfa_totp_secret
    user.mfa_totp_secret = tmp_secret
    if not mfa_service.verify_totp(user, code):
        user.mfa_totp_secret = old_secret
        flash('Code did not match. Please scan the QR code again and retry.', 'danger')
        return redirect(url_for('auth.mfa_setup'))

    # Commit TOTP enrollment
    session.pop('mfa_setup_secret', None)
    mfa_service.set_active_methods(user, list(set(mfa_service.get_active_methods(user) + ['totp'])))
    db.session.commit()
    flash('Authenticator app enrolled successfully.', 'success')
    return redirect(url_for('auth.mfa_backup_codes'))


@auth_bp.route('/auth/mfa/setup/sms', methods=['GET', 'POST'])
@login_required
def mfa_setup_sms():
    """Enroll the current user in SMS OTP MFA."""
    user = current_user
    sent = False

    if request.method == 'GET':
        return render_template('mfa_setup_sms.html', sent=False,
                               phone=user.phone_number or '',
                               base_template=_base_template())

    action = (request.form.get('action') or 'send').strip()

    if action == 'send':
        phone = (request.form.get('phone_number') or '').strip()
        if not phone:
            flash('Phone number is required.', 'danger')
            return render_template('mfa_setup_sms.html', sent=False,
                                   phone='', base_template=_base_template())
        # Persist phone number immediately so send_sms_otp can read it
        user.phone_number = phone
        db.session.commit()
        ok, err = mfa_service.send_sms_otp(user)
        if ok:
            flash('Verification code sent. Enter it below to confirm SMS OTP.', 'success')
            sent = True
        else:
            flash(f'Failed to send SMS: {err}', 'danger')
        return render_template('mfa_setup_sms.html', sent=sent,
                               phone=phone, base_template=_base_template())

    if action == 'verify':
        code = (request.form.get('code') or '').strip()
        phone = (request.form.get('phone_number') or user.phone_number or '').strip()
        if mfa_service.verify_sms_otp(code):
            mfa_service.set_active_methods(user, list(set(mfa_service.get_active_methods(user) + ['sms'])))
            if not user.mfa_enabled:
                user.mfa_enabled = True
            db.session.commit()
            flash('SMS OTP enrolled successfully. Your phone number has been verified.', 'success')
            return redirect(url_for('auth.profile'))
        flash('Invalid or expired code. Please request a new one.', 'danger')
        return render_template('mfa_setup_sms.html', sent=True,
                               phone=phone, base_template=_base_template())

    # Unknown action — fall back to GET view
    return redirect(url_for('auth.mfa_setup_sms'))


@auth_bp.route('/auth/mfa/backup-codes', methods=['GET', 'POST'])
@login_required
def mfa_backup_codes():
    """Generate (or re-generate) backup codes for the current user."""
    user = current_user
    new_codes: list[str] = []

    if request.method == 'POST':
        new_codes = mfa_service.generate_backup_codes(user)
        db.session.commit()
        flash(f'{len(new_codes)} backup codes generated. Save them somewhere safe — you will not see them again.', 'success')

    remaining = getattr(user, 'mfa_backup_codes_remaining', 0) or 0
    return render_template('mfa_backup_codes.html', new_codes=new_codes,
                           remaining=remaining, base_template=_base_template())


@auth_bp.route('/auth/mfa/disable', methods=['POST'])
@login_required
def mfa_disable():
    """Remove all MFA methods for the current user (self-service)."""
    user = current_user
    user.mfa_enabled = False
    user.mfa_methods = ''
    user.mfa_totp_secret = None
    user.mfa_backup_codes_hash = None
    user.mfa_backup_codes_remaining = 0
    db.session.commit()
    flash('Multi-factor authentication has been disabled.', 'warning')
    return redirect(url_for('auth.profile'))


# ══ Session management (user self-service) ══════════════════════════════════════

@auth_bp.route('/auth/sessions')
@login_required
def my_sessions():
    """List the current user's active sessions."""
    from app.models.user_management import UserSession
    sessions = (
        UserSession.query
        .filter_by(user_id=current_user.id, is_active=True)
        .order_by(UserSession.last_seen_at.desc())
        .all()
    )
    return render_template('my_sessions.html', sessions=sessions,
                           base_template=_base_template())


@auth_bp.route('/auth/sessions/<int:session_id>/revoke', methods=['POST'])
@login_required
def revoke_session(session_id):
    """Revoke one of the current user's own sessions."""
    from app.models.user_management import UserSession
    user_session = get_entity_or_404(UserSession, session_id)
    if user_session.user_id != current_user.id:
        flash('Not authorised.', 'danger')
        return redirect(url_for('auth.my_sessions'))
    session_service.revoke_session(session_id, revoked_by_id=current_user.id)
    flash('Session revoked.', 'success')
    return redirect(url_for('auth.my_sessions'))
