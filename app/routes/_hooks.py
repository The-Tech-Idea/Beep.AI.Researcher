"""Request lifecycle hooks — registered in create_app().

Hooks run before and after every request. Extracted from create_app()
to keep the factory function focused on extension setup.
"""

from __future__ import annotations

from flask import Flask, redirect, url_for, request
from flask_login import current_user

from app.config_manager import config_manager
from app.services import session_service


def register_request_hooks(app: Flask) -> None:
    """Register before_request and after_request hooks."""

    @app.before_request
    def check_setup():
        """Redirect to setup wizard if the app is not yet configured or no admin users exist."""
        if request.path.startswith("/static") or request.path.startswith("/setup"):
            return None
        if (
            request.path.startswith("/login")
            or request.path.startswith("/register")
            or request.path.startswith("/auth/")
        ):
            return None
        if not config_manager.is_configured:
            return redirect(url_for("setup.setup"))

    @app.before_request
    def enforce_session():
        """Heartbeat session for authenticated users (idle timeout)."""
        if current_user.is_authenticated:
            try:
                session_service.heartbeat()
            except Exception:
                # Don't break the request if session heartbeat fails
                pass
