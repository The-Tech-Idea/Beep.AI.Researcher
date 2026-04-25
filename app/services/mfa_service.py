"""MFA service — TOTP authenticator, email OTP, and backup codes.

Supports three second-factor methods controlled by config:
  mfa_totp_enabled       bool  TOTP authenticator apps (Google Auth, Authy, etc.)
  mfa_email_otp_enabled  bool  6-digit code sent to the user's email
  mfa_backup_codes_count int   number of single-use backup recovery codes

Email OTP challenge state is stored in the Flask session (signed cookie) under the
key ``mfa_otp_challenge``. This requires no extra DB columns and is safe for
single-server deployments. Add a Redis session store for multi-server setups.

Backup codes are stored as a JSON array of Werkzeug-bcrypt hashes in
``User.mfa_backup_codes_hash``.

Usage example:
    # Enroll TOTP
    secret = mfa_service.generate_totp_secret()
    user.mfa_totp_secret = secret
    uri = mfa_service.get_totp_provisioning_uri(user)
    qr_png_b64 = mfa_service.build_qr_b64(uri)

    # Verify TOTP
    ok = mfa_service.verify_totp(user, '123456')

    # Send email OTP
    mfa_service.send_email_otp(user)

    # Verify email OTP (reads / clears challenge from session)
    ok = mfa_service.verify_email_otp('123456')

    # Generate backup codes (returns plaintext list — show once)
    codes = mfa_service.generate_backup_codes(user)

    # Verify backup code
    ok = mfa_service.verify_backup_code(user, 'XXXXXXXX')
"""
from __future__ import annotations

import base64
import io
import json
import secrets
from datetime import timedelta
from typing import TYPE_CHECKING

from flask import session
from werkzeug.security import check_password_hash, generate_password_hash

from app.config_manager import config_manager
from app.core.time_utils import utcnow_naive
from app.database import db

if TYPE_CHECKING:
    from app.models.core import User

# Key used inside the Flask session for the pending OTP challenge
_SESSION_OTP_KEY = 'mfa_otp_challenge'
# Key used inside the Flask session for the pending SMS OTP challenge
_SESSION_SMS_OTP_KEY = 'mfa_sms_otp_challenge'
# Key used in session to hold user_id awaiting MFA completion
_SESSION_PENDING_USER = 'mfa_pending_user_id'


def _gi(key: str, default: int) -> int:
    v = config_manager.get(key)
    try:
        return int(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _gb(key: str, default: bool) -> bool:
    v = config_manager.get(key)
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    return str(v).lower() in ('1', 'true', 'yes')


# ── TOTP helpers ───────────────────────────────────────────────────────────────

def generate_totp_secret() -> str:
    """Return a new random base32 TOTP secret (20 bytes = 32 base32 chars)."""
    try:
        import pyotp
        return pyotp.random_base32()
    except ImportError:
        # Fallback: manually generate compatible base32 secret
        raw = secrets.token_bytes(20)
        import base64 as _b64
        alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
        bits = int.from_bytes(raw, 'big')
        chars = []
        for _ in range(32):
            chars.append(alphabet[bits & 0x1F])
            bits >>= 5
        return ''.join(reversed(chars))


def get_totp_provisioning_uri(user: "User") -> str:
    """Build the otpauth:// URI for QR code display."""
    issuer = config_manager.get('mfa_totp_issuer') or \
             config_manager.get('app_name') or 'Beep.AI.Researcher'
    secret = user.mfa_totp_secret or ''
    try:
        import pyotp
        return pyotp.TOTP(secret).provisioning_uri(
            name=user.email or user.username,
            issuer_name=issuer,
        )
    except ImportError:
        label = f"{issuer}:{user.email or user.username}"
        return (
            f"otpauth://totp/{label}"
            f"?secret={secret}&issuer={issuer}"
        )


def build_qr_b64(uri: str) -> str | None:
    """Render a QR code for *uri* and return a base64-encoded PNG data URI.

    Returns ``None`` if ``qrcode`` or ``Pillow`` is not installed.
    """
    try:
        import qrcode  # type: ignore
        img = qrcode.make(uri)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f'data:image/png;base64,{b64}'
    except ImportError:
        return None


def verify_totp(user: "User", code: str) -> bool:
    """Return True when *code* is a valid current/adjacent TOTP for *user*."""
    if not user.mfa_totp_secret:
        return False
    code = (code or '').strip().replace(' ', '')
    try:
        import pyotp
        totp = pyotp.TOTP(user.mfa_totp_secret)
        return totp.verify(code, valid_window=1)  # allow ±30 s drift
    except ImportError:
        # Manual TOTP verification (RFC 6238) as fallback
        return _manual_totp_verify(user.mfa_totp_secret, code)


def _manual_totp_verify(secret: str, code: str) -> bool:
    """Pure-stdlib TOTP verifier for environments without pyotp."""
    import base64
    import hmac
    import hashlib
    import struct
    import time

    try:
        decoded = base64.b32decode(secret.upper())
    except Exception:
        return False

    t = int(time.time()) // 30
    for delta in (-1, 0, 1):
        counter = struct.pack('>Q', t + delta)
        h = hmac.new(decoded, counter, hashlib.sha1).digest()
        offset = h[-1] & 0x0F
        otp_int = struct.unpack('>I', h[offset:offset + 4])[0] & 0x7FFFFFFF
        if str(otp_int % 1_000_000).zfill(6) == code.zfill(6):
            return True
    return False


# ── Email OTP ─────────────────────────────────────────────────────────────────

def send_email_otp(user: "User") -> tuple[bool, str]:
    """Generate a 6-digit OTP, store a hash in the session, and email it.

    Returns ``(success, error_message)``.
    """
    from app.services.email_service import send_mfa_otp_email

    code = f'{secrets.randbelow(1_000_000):06d}'
    validity = _gi('mfa_otp_validity_minutes', 10)
    expires_at = (utcnow_naive() + timedelta(minutes=validity)).isoformat()

    session[_SESSION_OTP_KEY] = {
        'hash': generate_password_hash(code),
        'expires_at': expires_at,
        'user_id': user.id,
    }

    ok, err = send_mfa_otp_email(user, code)
    if not ok:
        session.pop(_SESSION_OTP_KEY, None)
    return ok, (err or '')


def verify_email_otp(code: str) -> bool:
    """Verify *code* against the session challenge. Clears the challenge on success."""
    import datetime
    challenge = session.get(_SESSION_OTP_KEY)
    if not challenge:
        return False

    expires_at_str = challenge.get('expires_at', '')
    try:
        expires_at = datetime.datetime.fromisoformat(expires_at_str)
    except (ValueError, TypeError):
        session.pop(_SESSION_OTP_KEY, None)
        return False

    if utcnow_naive() > expires_at:
        session.pop(_SESSION_OTP_KEY, None)
        return False

    if check_password_hash(challenge['hash'], (code or '').strip()):
        session.pop(_SESSION_OTP_KEY, None)
        return True

    return False


# ── SMS OTP ───────────────────────────────────────────────────────────────────

def send_sms_otp(user: "User") -> tuple[bool, str]:
    """Generate a 6-digit OTP, store a hash in the session, and send via SMS.

    Requires ``user.phone_number`` to be set. Returns ``(success, error_message)``.
    """
    from app.services.sms_service import send_sms, mask_number

    phone = getattr(user, 'phone_number', None) or ''
    if not phone:
        return False, 'No phone number on file. Please add a phone number to your profile.'

    code = f'{secrets.randbelow(1_000_000):06d}'
    validity = _gi('mfa_otp_validity_minutes', 10)
    expires_at = (utcnow_naive() + timedelta(minutes=validity)).isoformat()

    session[_SESSION_SMS_OTP_KEY] = {
        'hash': generate_password_hash(code),
        'expires_at': expires_at,
        'user_id': user.id,
    }

    masked = mask_number(phone)
    message = f'Your Beep.AI verification code is {code}. Valid for {validity} minutes.'
    ok, err = send_sms(phone, message)
    if not ok:
        session.pop(_SESSION_SMS_OTP_KEY, None)
    return ok, (err or '')


def verify_sms_otp(code: str) -> bool:
    """Verify *code* against the SMS session challenge. Clears the challenge on success."""
    import datetime
    challenge = session.get(_SESSION_SMS_OTP_KEY)
    if not challenge:
        return False

    expires_at_str = challenge.get('expires_at', '')
    try:
        expires_at = datetime.datetime.fromisoformat(expires_at_str)
    except (ValueError, TypeError):
        session.pop(_SESSION_SMS_OTP_KEY, None)
        return False

    if utcnow_naive() > expires_at:
        session.pop(_SESSION_SMS_OTP_KEY, None)
        return False

    if check_password_hash(challenge['hash'], (code or '').strip()):
        session.pop(_SESSION_SMS_OTP_KEY, None)
        return True

    return False


# ── Backup codes ──────────────────────────────────────────────────────────────

def generate_backup_codes(user: "User") -> list[str]:
    """Generate N single-use backup codes, store their hashes on *user*.

    Returns the plaintext codes — display them once to the user.
    Commits are handled by the caller.
    """
    count = _gi('mfa_backup_codes_count', 10)
    codes: list[str] = [secrets.token_hex(4).upper() for _ in range(count)]
    hashes: list[str] = [generate_password_hash(c) for c in codes]

    user.mfa_backup_codes_hash = json.dumps(hashes)
    user.mfa_backup_codes_remaining = count
    return codes


def verify_backup_code(user: "User", code: str) -> bool:
    """Check *code* against stored hashes; consume (delete) the matched code.

    Returns True on success. Commits are handled by the caller.
    """
    code = (code or '').strip().upper()
    raw = user.mfa_backup_codes_hash
    if not raw:
        return False

    try:
        hashes: list[str] = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return False

    for i, h in enumerate(hashes):
        if check_password_hash(h, code):
            hashes.pop(i)
            user.mfa_backup_codes_hash = json.dumps(hashes)
            user.mfa_backup_codes_remaining = max(0, (user.mfa_backup_codes_remaining or 1) - 1)
            return True

    return False


# ── MFA method helpers ────────────────────────────────────────────────────────

def get_active_methods(user: "User") -> list[str]:
    """Return the list of active MFA method identifiers for *user*."""
    raw = getattr(user, 'mfa_methods', '') or ''
    return [m.strip() for m in raw.split(',') if m.strip()]


def set_active_methods(user: "User", methods: list[str]) -> None:
    """Persist the MFA methods list on *user*. Commits handled by caller."""
    user.mfa_methods = ','.join(sorted(set(methods)))
    user.mfa_enabled = bool(methods)


def is_mfa_required(user: "User") -> bool:
    """Return True when the system or user policy mandates MFA for this user."""
    if not _gb('mfa_enabled', False):
        return False
    enforcement = config_manager.get('mfa_enforcement') or 'optional'
    if enforcement == 'required_all':
        return True
    if enforcement == 'required_by_role':
        required_roles_str = config_manager.get('mfa_required_roles') or 'admin'
        required_roles = {r.strip().lower() for r in required_roles_str.split(',')}
        user_role = getattr(user.role, 'name', '') or ''
        return user_role.lower() in required_roles
    return False


# ── Session helpers for the two-step login flow ───────────────────────────────

def set_pending_user(user_id: int) -> None:
    """Store *user_id* in session awaiting MFA completion."""
    session[_SESSION_PENDING_USER] = user_id


def get_pending_user_id() -> int | None:
    """Return the user_id awaiting MFA, or None."""
    return session.get(_SESSION_PENDING_USER)


def clear_pending_user() -> None:
    """Remove the pending MFA state from session."""
    session.pop(_SESSION_PENDING_USER, None)
    session.pop(_SESSION_OTP_KEY, None)
    session.pop(_SESSION_SMS_OTP_KEY, None)
