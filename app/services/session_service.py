"""Server-side session tracking service.

A random opaque token (``session_cookie_id``) is stored in the Flask session
on login.  Its SHA-256 hash is persisted in ``UserSession`` so that a DB dump
does not expose valid session tokens.

On every authenticated request Flask middleware calls ``heartbeat()`` to update
``last_seen_at`` and enforce idle-timeout / lifetime policies.

Config keys consumed:
  session_lifetime_hours       int  default 24   (absolute max age; 0 = unlimited)
  session_idle_timeout_minutes int  default 60   (inactivity timeout; 0 = disabled)
  session_max_concurrent       int  default 5    (0 = unlimited)
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import TYPE_CHECKING

from flask import session, request
from flask_login import logout_user

from app.config_manager import config_manager
from app.core.time_utils import utcnow_naive
from app.database import db

if TYPE_CHECKING:
    from app.models.core import User

_SESSION_TOKEN_KEY = 'session_cookie_id'


def _gi(key: str, default: int) -> int:
    v = config_manager.get(key)
    try:
        return int(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _ua_label() -> str:
    ua = (request.user_agent.string or '') if request else ''
    if len(ua) > 100:
        browser = getattr(request.user_agent, 'browser', '') or ''
        version = getattr(request.user_agent, 'version', '') or ''
        platform = getattr(request.user_agent, 'platform', '') or ''
        ua = f"{browser} {version} on {platform}".strip()
    return ua[:100]


# ── Session creation ───────────────────────────────────────────────────────────

def create_session(user: "User") -> str:
    """Create a ``UserSession`` record and write the token to the Flask session.

    Returns the raw token (only used here; only its hash is persisted).
    Calls ``db.session.flush()`` — the caller must commit.
    """
    from app.models.user_management import UserSession

    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    session[_SESSION_TOKEN_KEY] = token

    max_concurrent = _gi('session_max_concurrent', 5)
    if max_concurrent > 0:
        _evict_oldest(user.id, keep=max_concurrent - 1)

    lifetime_hours = _gi('session_lifetime_hours', 24)
    expires_at = None
    if lifetime_hours > 0:
        expires_at = utcnow_naive() + timedelta(hours=lifetime_hours)

    ip = (request.remote_addr or '') if request else ''
    ua = _ua_label() if request else ''

    sess = UserSession(
        user_id=user.id,
        session_token_hash=token_hash,
        ip_address=ip[:45],
        user_agent=ua,
        device_label=ua[:100],
        created_at=utcnow_naive(),
        last_seen_at=utcnow_naive(),
        expires_at=expires_at,
        is_active=True,
    )
    db.session.add(sess)
    db.session.flush()
    return token


def _evict_oldest(user_id: int, keep: int) -> None:
    """Revoke the oldest active sessions for *user_id* keeping the *keep* most recent."""
    from app.models.user_management import UserSession

    active = (
        UserSession.query
        .filter_by(user_id=user_id, is_active=True)
        .order_by(UserSession.created_at.desc())
        .all()
    )
    for old in active[keep:]:
        old.is_active = False
        old.revoked_at = utcnow_naive()


# ── Heartbeat / enforcement ────────────────────────────────────────────────────

def heartbeat() -> bool:
    """Update ``last_seen_at`` and enforce timeouts for the current request.

    Returns True when the session is still valid.
    Call from a ``before_request`` hook — only when the user is authenticated.
    Returns False and logs out the user when the session should be terminated.
    """
    from app.models.user_management import UserSession

    token = session.get(_SESSION_TOKEN_KEY)
    if not token:
        return True  # no server-side tracking for this session (legacy / pre-feature)

    token_hash = _hash_token(token)
    user_session = UserSession.query.filter_by(
        session_token_hash=token_hash, is_active=True
    ).first()

    if not user_session:
        logout_user()
        session.clear()
        return False

    now = utcnow_naive()

    # Absolute lifetime check
    if user_session.expires_at and now > user_session.expires_at:
        _revoke(user_session, reason='expired')
        db.session.commit()
        logout_user()
        session.clear()
        return False

    # Idle timeout check
    idle_minutes = _gi('session_idle_timeout_minutes', 60)
    if idle_minutes > 0 and user_session.last_seen_at:
        idle_deadline = user_session.last_seen_at + timedelta(minutes=idle_minutes)
        if now > idle_deadline:
            _revoke(user_session, reason='idle')
            db.session.commit()
            logout_user()
            session.clear()
            return False

    # Update last_seen_at (throttled to once per minute to reduce writes)
    if not user_session.last_seen_at or (now - user_session.last_seen_at).total_seconds() > 60:
        user_session.last_seen_at = now
        db.session.commit()

    return True


def _revoke(user_session, reason: str = '') -> None:
    user_session.is_active = False
    user_session.revoked_at = utcnow_naive()


# ── Admin / user revocation ────────────────────────────────────────────────────

def revoke_session(session_id: int, revoked_by_id: int | None = None) -> bool:
    """Revoke a specific ``UserSession`` by DB id. Returns False if not found."""
    from app.models.user_management import UserSession

    user_session = db.session.get(UserSession, session_id)
    if not user_session or not user_session.is_active:
        return False

    user_session.is_active = False
    user_session.revoked_at = utcnow_naive()
    user_session.revoked_by_id = revoked_by_id
    db.session.commit()
    return True


def revoke_all_sessions(user_id: int, except_current: bool = False,
                        revoked_by_id: int | None = None) -> int:
    """Revoke all active sessions for *user_id*.

    If *except_current* is True, the session matching the current request token
    is kept active.  Returns the count of revoked sessions.
    """
    from app.models.user_management import UserSession

    current_hash = _hash_token(session.get(_SESSION_TOKEN_KEY, ''))

    active = UserSession.query.filter_by(user_id=user_id, is_active=True).all()
    count = 0
    for s in active:
        if except_current and s.session_token_hash == current_hash:
            continue
        s.is_active = False
        s.revoked_at = utcnow_naive()
        s.revoked_by_id = revoked_by_id
        count += 1

    if count:
        db.session.commit()
    return count


def terminate_current_session() -> None:
    """Revoke the current session token record (call before ``logout_user()``)."""
    from app.models.user_management import UserSession

    token = session.get(_SESSION_TOKEN_KEY)
    if token:
        token_hash = _hash_token(token)
        record = UserSession.query.filter_by(session_token_hash=token_hash).first()
        if record and record.is_active:
            _revoke(record)
            db.session.commit()
    session.pop(_SESSION_TOKEN_KEY, None)
