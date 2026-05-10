"""Password policy service — validation, history, expiry, and account lockout.

All policy thresholds are read live from config_manager so admin changes
take effect immediately without a restart.

Config keys used (all in config_manager.CONFIG_KEYS):
  password_min_length          int   default 8
  password_require_uppercase   bool  default True
  password_require_lowercase   bool  default True
  password_require_number      bool  default True
  password_require_special     bool  default False
  password_history_count       int   default 5   (0 = disabled)
  password_expiry_days         int   default 0   (0 = never expires)
  password_max_failed_attempts int   default 5   (0 = lockout disabled)
  password_lockout_minutes     int   default 15
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import TYPE_CHECKING

from werkzeug.security import check_password_hash

from app.config_manager import config_manager
from app.core.time_utils import utcnow_naive, _gi, _gb
from app.database import db

if TYPE_CHECKING:
    from app.models.core import User


# ── Password validation ────────────────────────────────────────────────────────


def validate_password(
    password: str, user: "User | None" = None
) -> tuple[bool, list[str]]:
    """Validate *password* against the current policy.

    Returns ``(is_valid, errors)`` where *errors* is a list of human-readable
    strings describing each violation (empty list when valid).

    Pass *user* to also check the password history.
    """
    errors: list[str] = []

    min_len = _gi("password_min_length", 8)
    if len(password) < min_len:
        errors.append(f"Password must be at least {min_len} characters.")

    if _gb("password_require_uppercase", True) and not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter.")

    if _gb("password_require_lowercase", True) and not re.search(r"[a-z]", password):
        errors.append("Password must contain at least one lowercase letter.")

    if _gb("password_require_number", True) and not re.search(r"\d", password):
        errors.append("Password must contain at least one number.")

    if _gb("password_require_special", False) and not re.search(
        r"[^A-Za-z0-9]", password
    ):
        errors.append("Password must contain at least one special character.")

    # History check — only possible when we have a user
    if not errors and user is not None:
        history_count = _gi("password_history_count", 5)
        if history_count > 0:
            from app.models.user_management import PasswordHistory

            history = (
                PasswordHistory.query.filter_by(user_id=user.id)
                .order_by(PasswordHistory.created_at.desc())
                .limit(history_count)
                .all()
            )
            for record in history:
                if check_password_hash(record.password_hash, password):
                    errors.append(
                        f"You cannot reuse any of your last {history_count} passwords."
                    )
                    break

    return (len(errors) == 0, errors)


# ── Password lifecycle ─────────────────────────────────────────────────────────


def record_password_change(user_id: int, password_hash: str) -> None:
    """Store the new hash in PasswordHistory and trim old records.

    Call this *after* saving the new hash on the User row.
    """
    from app.models.user_management import PasswordHistory

    entry = PasswordHistory(user_id=user_id, password_hash=password_hash)
    db.session.add(entry)
    db.session.flush()  # give entry an id so ORDER BY works

    history_count = _gi("password_history_count", 5)
    if history_count > 0:
        # Keep only the most recent `history_count` records; delete the rest
        all_history = (
            PasswordHistory.query.filter_by(user_id=user_id)
            .order_by(PasswordHistory.created_at.desc())
            .all()
        )
        for old in all_history[history_count:]:
            db.session.delete(old)


def is_password_expired(user: "User") -> bool:
    """Return True when the user's password has exceeded the configured maximum age."""
    expiry_days = _gi("password_expiry_days", 0)
    if expiry_days <= 0:
        return False
    if not getattr(user, "password_changed_at", None):
        return False
    deadline = user.password_changed_at + timedelta(days=expiry_days)
    return utcnow_naive() > deadline


# ── Account lockout ────────────────────────────────────────────────────────────


def is_locked_out(user: "User") -> bool:
    """Return True when the account is currently under a time-based lockout."""
    if not getattr(user, "locked_until", None):
        return False
    if utcnow_naive() < user.locked_until:
        return True
    # Lockout period has passed — auto-clear
    user.failed_login_attempts = 0
    user.locked_until = None
    db.session.flush()
    return False


def record_failed_login(user: "User") -> None:
    """Increment the failed-login counter and apply lockout if threshold is reached.

    Commits are handled by the caller.
    """
    max_attempts = _gi("password_max_failed_attempts", 5)

    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1

    if max_attempts > 0 and user.failed_login_attempts >= max_attempts:
        lockout_minutes = _gi("password_lockout_minutes", 15)
        user.locked_until = utcnow_naive() + timedelta(minutes=lockout_minutes)


def record_successful_login(user: "User") -> None:
    """Reset lockout counters and stamp last_login_at.

    Commits are handled by the caller.
    """
    user.failed_login_attempts = 0
    user.locked_until = None
    if hasattr(user, "last_login_at"):
        user.last_login_at = utcnow_naive()
