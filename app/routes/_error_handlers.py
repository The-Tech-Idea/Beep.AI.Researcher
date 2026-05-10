"""Error handlers — registered in create_app().

Provides JSON responses for API requests and HTML pages for browser requests.
"""

from __future__ import annotations

from flask import Flask, request, jsonify, render_template
from app.database import db


def register_error_handlers(app: Flask) -> None:
    """Register HTTP error handlers on the Flask app."""

    @app.errorhandler(400)
    def bad_request(e):
        if _wants_json():
            return jsonify({"error": "Bad request"}), 400
        return render_template("errors/400.html"), 400

    @app.errorhandler(401)
    def unauthorized(e):
        if _wants_json():
            return jsonify({"error": "Unauthorized"}), 401
        return render_template("errors/401.html"), 401

    @app.errorhandler(403)
    def forbidden(e):
        if _wants_json():
            return jsonify({"error": "Forbidden"}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        if _wants_json():
            return jsonify({"error": "Not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        if _wants_json():
            return jsonify({"error": "Method not allowed"}), 405
        return render_template("errors/405.html"), 405

    @app.errorhandler(500)
    def server_error(e):
        # Always rollback on 500 to clear bad session state
        try:
            db.session.rollback()
        except Exception:
            pass

        app.logger.exception("Unhandled server error")
        if _wants_json():
            return jsonify({"error": "Internal server error"}), 500
        return render_template("errors/500.html"), 500


def _wants_json() -> bool:
    """Check if the client prefers JSON responses."""
    best = request.accept_mimetypes.best
    if best is None:
        return False
    return best.lower() in ("application/json", "text/javascript")
