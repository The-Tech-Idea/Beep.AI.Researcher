"""Admin feature flags management routes."""

from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required

from app.config_manager import config_manager
from app.config import get_config
from app.routes.admin_routes import admin_bp, admin_required


FEATURE_METADATA = {
    "ai_discovery_enabled": {
        "label": "AI Discovery & Personalized Feed",
        "description": "Research-interest inference, personalized reading feed, and smart alerts",
        "category": "ai",
        "icon": "bi-stars",
    },
    "auto_extract": {
        "label": "Auto Document Extraction",
        "description": "Automatically extract structured data from uploaded documents",
        "category": "core",
        "icon": "bi-file-earmark-arrow-up",
    },
    "web_search_enabled": {
        "label": "Web & Academic Search",
        "description": "External search integration (PubMed, arXiv, Crossref, Google Scholar)",
        "category": "search",
        "icon": "bi-search",
    },
    "plugins_enabled": {
        "label": "Plugin System",
        "description": "Enable plugin architecture for extensibility and custom integrations",
        "category": "system",
        "icon": "bi-puzzle",
    },
    "chat_enabled": {
        "label": "Chat Interface",
        "description": "AI-powered chat for asking questions about documents and projects",
        "category": "ai",
        "icon": "bi-chat-dots",
    },
    "code_generation_enabled": {
        "label": "Code Generation",
        "description": "Generate analysis code from documents and research data",
        "category": "ai",
        "icon": "bi-code-slash",
    },
    "rag_enabled": {
        "label": "RAG (Retrieval-Augmented Generation)",
        "description": "Ground AI responses in your document library for accurate answers",
        "category": "ai",
        "icon": "bi-database",
    },
    "notifications_enabled": {
        "label": "Notifications",
        "description": "Email and in-app notifications for important events",
        "category": "system",
        "icon": "bi-bell",
    },
    "audit_logging_enabled": {
        "label": "Audit Logging",
        "description": "Track all user actions for compliance and security",
        "category": "system",
        "icon": "bi-journal-text",
    },
}

CATEGORIES = {
    "core": {"label": "Core Features", "icon": "bi-gear"},
    "ai": {"label": "AI & Intelligence", "icon": "bi-robot"},
    "search": {"label": "Search & Discovery", "icon": "bi-search"},
    "system": {"label": "System & Compliance", "icon": "bi-shield-check"},
}


@admin_bp.route("/feature-flags")
@login_required
@admin_required
def feature_flags():
    """Feature flags management page."""
    runtime_config = get_config()
    features = runtime_config.get_all_features()

    feature_list = []
    for name, config in features.items():
        enabled = (
            config.get("enabled", False) if isinstance(config, dict) else bool(config)
        )
        meta = FEATURE_METADATA.get(name, {})
        feature_list.append(
            {
                "name": name,
                "enabled": enabled,
                "label": meta.get("label", name),
                "description": meta.get("description", ""),
                "category": meta.get("category", "system"),
                "icon": meta.get("icon", "bi-toggle-on"),
                "level": config.get("level", "optional")
                if isinstance(config, dict)
                else "optional",
            }
        )

    grouped = {}
    for cat_key, cat_info in CATEGORIES.items():
        grouped[cat_key] = {
            "label": cat_info["label"],
            "icon": cat_info["icon"],
            "features": [f for f in feature_list if f["category"] == cat_key],
        }

    enabled_count = sum(1 for f in feature_list if f["enabled"])
    total_count = len(feature_list)

    return render_template(
        "admin/feature_flags.html",
        grouped=grouped,
        feature_list=feature_list,
        enabled_count=enabled_count,
        total_count=total_count,
    )


@admin_bp.route("/feature-flags/toggle", methods=["POST"])
@login_required
@admin_required
def feature_flag_toggle():
    """Toggle a single feature flag via API."""
    data = request.get_json()
    feature_name = data.get("feature_name")
    enabled = data.get("enabled", False)

    if not feature_name or feature_name not in FEATURE_METADATA:
        return jsonify({"error": "Invalid feature name"}), 400

    runtime_config = get_config()
    result = runtime_config.set_feature_enabled(feature_name, enabled)

    if not result:
        return jsonify({"error": "Feature not found in configuration"}), 404

    features = runtime_config.get_all_features()
    persisted = {}
    for k, v in features.items():
        if isinstance(v, dict):
            v["enabled"] = v.get("enabled", False) if k != feature_name else enabled
            persisted[k] = v
        else:
            persisted[k] = enabled if k == feature_name else bool(v)
    config_manager.set("features", persisted)
    config_manager.save()

    return jsonify(
        {
            "feature_name": feature_name,
            "enabled": enabled,
            "label": FEATURE_METADATA.get(feature_name, {}).get("label", feature_name),
        }
    )


@admin_bp.route("/feature-flags/toggle-all", methods=["POST"])
@login_required
@admin_required
def feature_flag_toggle_all():
    """Enable or disable all feature flags at once."""
    data = request.get_json()
    enabled = data.get("enabled", False)

    runtime_config = get_config()
    results = {}

    for feature_name in FEATURE_METADATA:
        runtime_config.set_feature_enabled(feature_name, enabled)
        results[feature_name] = enabled

    config_manager.set("features", results)
    config_manager.save()

    return jsonify(
        {
            "enabled": enabled,
            "count": len(results),
            "features": results,
        }
    )


@admin_bp.route("/feature-flags/status")
@login_required
@admin_required
def feature_flag_status():
    """Get current status of all feature flags."""
    runtime_config = get_config()
    features = runtime_config.get_all_features()

    status = {}
    for name, config in features.items():
        enabled = (
            config.get("enabled", False) if isinstance(config, dict) else bool(config)
        )
        status[name] = {
            "enabled": enabled,
            "label": FEATURE_METADATA.get(name, {}).get("label", name),
            "category": FEATURE_METADATA.get(name, {}).get("category", "system"),
        }

    return jsonify(status)


@admin_bp.route("/feature-flags/reset-defaults", methods=["POST"])
@login_required
@admin_required
def feature_flag_reset_defaults():
    """Reset all feature flags to their documented defaults from defaults.py."""
    from app.config.defaults import DEFAULT_FEATURES

    runtime_config = get_config()
    results = {}

    for feature_name, feature_def in DEFAULT_FEATURES.items():
        enabled = feature_def.get("enabled", False)
        runtime_config.set_feature_enabled(feature_name, enabled)
        results[feature_name] = {
            "enabled": enabled,
            "label": FEATURE_METADATA.get(feature_name, {}).get("label", feature_name),
        }

    config_manager.set(
        "features",
        {
            k: v.get("enabled", False) if isinstance(v, dict) else v
            for k, v in results.items()
        },
    )
    config_manager.save()

    return jsonify(
        {
            "count": len(results),
            "features": results,
        }
    )
