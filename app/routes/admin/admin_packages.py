"""Admin optional packages management.

Allows admin users to install/uninstall heavy optional packages
(docling, unstructured, llama-index, etc.) from the admin UI.
"""

from __future__ import annotations

import json
import logging

from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required

from app.config_manager import config_manager
from app.routes.admin_routes import admin_required
from app.services.package_manager_service import (
    OPTIONAL_PACKAGES,
    check_optional_feature,
    install_packages,
    uninstall_packages,
)

logger = logging.getLogger(__name__)

admin_packages_bp = Blueprint(
    "admin_packages",
    __name__,
    url_prefix="/admin/packages",
)


@admin_packages_bp.route("/", methods=["GET"])
@login_required
@admin_required
def list_optional_packages():
    """Show installable optional packages with their status."""
    features = []
    for key, info in OPTIONAL_PACKAGES.items():
        features.append(
            {
                "key": info.key,
                "label": info.label,
                "description": info.description,
                "packages": info.packages,
                "size_hint": info.size_hint,
                "feature_flag": info.feature_flag,
                "installed": info.is_installed,
                "depends_on": info.depends_on,
            }
        )
    return render_template(
        "admin/optional_packages.html",
        features=features,
    )


@admin_packages_bp.route("/<key>/status", methods=["GET"])
@login_required
@admin_required
def package_status(key):
    """Return JSON status for a specific optional package."""
    result = check_optional_feature(key)
    return jsonify(result)


@admin_packages_bp.route("/<key>/install", methods=["POST"])
@login_required
@admin_required
def install_package(key):
    """Install an optional package group."""
    info = OPTIONAL_PACKAGES.get(key)
    if info is None:
        return jsonify({"error": f"Unknown package group: {key}"}), 404

    if info.is_installed:
        return jsonify({"ok": True, "message": "Already installed."})

    # Check dependencies
    for dep_key in info.depends_on:
        dep = OPTIONAL_PACKAGES.get(dep_key)
        if dep and not dep.is_installed:
            return jsonify(
                {
                    "error": f"This requires '{dep.label}' to be installed first.",
                }
            ), 400

    result = install_packages(info.packages)
    if result["ok"]:
        config_manager.set_feature_enabled(info.feature_flag, True)
    return jsonify(result)


@admin_packages_bp.route("/<key>/uninstall", methods=["POST"])
@login_required
@admin_required
def uninstall_package(key):
    """Uninstall an optional package group."""
    info = OPTIONAL_PACKAGES.get(key)
    if info is None:
        return jsonify({"error": f"Unknown package group: {key}"}), 404

    result = uninstall_packages(info.packages)
    if result["ok"]:
        config_manager.set_feature_enabled(info.feature_flag, False)
    return jsonify(result)
