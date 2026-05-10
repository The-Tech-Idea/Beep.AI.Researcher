"""CAPTCHA service — multi-backend challenge/response for login and registration.

Supported backends (set via Admin → Settings → Registration):

  ``math``          Simple arithmetic (e.g. "3 + 5 = ?"). Zero dependencies.
  ``text``          Word scramble / pattern matching. Zero dependencies.
  ``hcaptcha``      hCaptcha invisible or v2 checkbox. Requires site key + secret.
  ``recaptcha_v2``  Google reCAPTCHA v2 checkbox. Requires site key + secret.

The active backend is chosen from ``config_manager.get('captcha_method')``.
Built-in methods (math, text) store the answer in the Flask session and never
leave the server. External services validate via their respective APIs.
"""

from __future__ import annotations

import hashlib
import logging
import random
import string
from typing import Optional, Tuple

import requests

from app.config_manager import config_manager

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

SESSION_CHALLENGE_KEY = "_captcha_challenge"

# Word bank for text captcha — common short words
_WORD_BANK = [
    "apple",
    "brave",
    "cloud",
    "drive",
    "eagle",
    "flame",
    "grape",
    "house",
    "image",
    "juice",
    "knife",
    "lemon",
    "maple",
    "night",
    "ocean",
    "pearl",
    "queen",
    "river",
    "stone",
    "train",
    "umbra",
    "valve",
    "water",
    "xenon",
    "yacht",
    "zebra",
    "beach",
    "chair",
    "dream",
    "earth",
    "frost",
    "giant",
]


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────────────────────


def is_configured() -> bool:
    """Return True if the configured captcha backend has enough credentials."""
    method = _method()
    if method in ("math", "text"):
        return True  # zero-dependency, always available
    if method == "hcaptcha":
        return bool(
            config_manager.get_setting("captcha_hcaptcha_site_key")
            and config_manager.get_setting("captcha_hcaptcha_secret")
        )
    if method == "recaptcha_v2":
        return bool(
            config_manager.get_setting("captcha_recaptcha_site_key")
            and config_manager.get_setting("captcha_recaptcha_secret")
        )
    return False


def generate_challenge(session) -> Optional[dict]:
    """Create a new captcha challenge and store it in the session.

    Returns a dict with the data needed to render the captcha widget, or None
    if captcha is not enabled.

    Keys returned:
      - method: backend name
      - question: human-readable prompt (math / text only)
      - challenge_hash: opaque token stored server-side (math / text only)
      - site_key: public key for external services (hcaptcha / recaptcha only)
    """
    if not _enabled():
        return None

    method = _method()
    if method == "math":
        a, b, answer = _math_problem()
        challenge_hash = _hash_answer(str(answer))
        session[SESSION_CHALLENGE_KEY] = challenge_hash
        return {
            "method": method,
            "question": f"{a} + {b} = ?",
            "challenge_hash": challenge_hash,
        }

    if method == "text":
        word, scrambled, answer = _text_problem()
        challenge_hash = _hash_answer(answer)
        session[SESSION_CHALLENGE_KEY] = challenge_hash
        return {
            "method": method,
            "question": f"Unscramble: **{scrambled}**",
            "challenge_hash": challenge_hash,
        }

    if method == "hcaptcha":
        return {
            "method": method,
            "site_key": config_manager.get_setting("captcha_hcaptcha_site_key", ""),
        }

    if method == "recaptcha_v2":
        return {
            "method": method,
            "site_key": config_manager.get_setting("captcha_recaptcha_site_key", ""),
        }

    return None


def verify_response(session, form) -> Tuple[bool, Optional[str]]:
    """Validate the user's captcha answer.

    Args:
        session: Flask session object
        form: request.form dict

    Returns:
        (success: bool, error_message: str | None)
    """
    if not _enabled():
        return True, None  # captcha not enabled — auto-pass

    method = _method()

    if method in ("math", "text"):
        return _verify_builtin(session, form)

    if method == "hcaptcha":
        return _verify_hcaptcha(form)

    if method == "recaptcha_v2":
        return _verify_recaptcha(form)

    return False, "Unknown captcha method"


def clear_challenge(session):
    """Remove the stored captcha challenge from the session."""
    session.pop(SESSION_CHALLENGE_KEY, None)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _enabled() -> bool:
    return bool(config_manager.get("registration_captcha_enabled", False))


def _method() -> str:
    return (config_manager.get("captcha_method") or "math").strip().lower()


def _math_problem() -> Tuple[int, int, int]:
    """Generate a simple addition problem with numbers 1-20."""
    a = random.randint(1, 20)
    b = random.randint(1, 20)
    return a, b, a + b


def _text_problem() -> Tuple[str, str, str]:
    """Pick a word, scramble it, return (original, scrambled, original_lower)."""
    word = random.choice(_WORD_BANK)
    chars = list(word)
    # Fisher-Yates shuffle ensuring the result differs from original
    while True:
        for i in range(len(chars) - 1, 0, -1):
            j = random.randint(0, i)
            chars[i], chars[j] = chars[j], chars[i]
        scrambled = "".join(chars)
        if scrambled != word:
            break
    return word, scrambled, word.lower()


def _hash_answer(answer: str) -> str:
    """Hash an answer for server-side comparison (prevents session tampering)."""
    return hashlib.sha256(answer.strip().lower().encode()).hexdigest()


def _verify_builtin(session, form) -> Tuple[bool, Optional[str]]:
    """Verify math or text captcha against the session-stored hash."""
    stored_hash = session.get(SESSION_CHALLENGE_KEY)
    if not stored_hash:
        return False, "CAPTCHA expired. Please try again."

    user_answer = (form.get("captcha_answer") or "").strip()
    if not user_answer:
        return False, "Please complete the CAPTCHA."

    user_hash = _hash_answer(user_answer)
    clear_challenge(session)

    if user_hash != stored_hash:
        return False, "CAPTCHA answer was incorrect. Please try again."

    return True, None


def _verify_hcaptcha(form) -> Tuple[bool, Optional[str]]:
    """Verify hCaptcha response token against their API."""
    token = form.get("h-captcha-response") or form.get("hcaptcha_response") or ""
    if not token:
        return False, "Please complete the CAPTCHA."

    secret = config_manager.get_setting("captcha_hcaptcha_secret", "")
    try:
        resp = requests.post(
            "https://hcaptcha.com/siteverify",
            data={"secret": secret, "response": token},
            timeout=10,
        )
        result = resp.json()
        if result.get("success"):
            return True, None
        error_codes = result.get("error-codes", [])
        return False, f"hCaptcha failed: {', '.join(error_codes)}"
    except Exception as e:
        logger.warning("hCaptcha verification error: %s", e)
        return False, "CAPTCHA verification service unavailable."


def _verify_recaptcha(form) -> Tuple[bool, Optional[str]]:
    """Verify Google reCAPTCHA v2 response token."""
    token = form.get("g-recaptcha-response") or ""
    if not token:
        return False, "Please complete the CAPTCHA."

    secret = config_manager.get_setting("captcha_recaptcha_secret", "")
    try:
        resp = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": secret, "response": token},
            timeout=10,
        )
        result = resp.json()
        if result.get("success"):
            return True, None
        error_codes = result.get("error-codes", [])
        return False, f"reCAPTCHA failed: {', '.join(error_codes)}"
    except Exception as e:
        logger.warning("reCAPTCHA verification error: %s", e)
        return False, "CAPTCHA verification service unavailable."
