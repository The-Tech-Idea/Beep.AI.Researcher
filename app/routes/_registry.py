"""Blueprint registration — central registry of all Flask blueprints.

All route registration happens here. To add a new blueprint:
1. Import the blueprint
2. Call app.register_blueprint() with the appropriate url_prefix

Blueprints are grouped by domain: core, projects, admin, ai_discovery, etc.
"""

from __future__ import annotations

from flask import Flask


def register_blueprints(app: Flask) -> None:
    """Register all blueprints on the Flask application."""

    # ── Core: auth, setup, dashboard, landing ──────────────────────────────
    from app.routes.auth_routes import auth_bp
    from app.routes.setup import setup_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.landing import landing_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(setup_bp)
    app.register_blueprint(dashboard_bp, url_prefix="/researcher")
    app.register_blueprint(landing_bp)

    # ── Projects (all scoped under /projects/<id>) ─────────────────────────
    from app.routes.projects import projects_bp
    from app.routes.documents import documents_bp
    from app.routes.documents.access import doc_access_bp
    from app.routes.search import search_bp
    from app.routes.extended_search import extended_search_bp
    from app.routes.search_advanced import search_advanced_bp
    from app.routes.chat import chat_bp
    from app.routes.codes import codes_bp
    from app.routes.data_analyst import data_bp
    from app.routes.extraction import extraction_bp
    from app.routes.stats import stats_bp
    from app.routes.training import training_bp
    from app.routes.document_map import document_map_bp
    from app.routes.related import related_bp
    from app.routes.report_writing import report_bp
    from app.routes.contradiction import contradiction_bp
    from app.routes.annotations import annotations_bp
    from app.routes.scheduled_reports import reports_bp
    from app.routes.coding_matrices import matrices_bp
    from app.routes.collaboration import collab_bp
    from app.routes.compliance import compliance_bp
    from app.routes.lifecycle import lifecycle_bp
    from app.routes.retention import retention_bp
    from app.routes.observability import observability_bp
    from app.routes.phi_routes import phi_bp
    from app.routes.tasks import tasks_bp
    from app.routes.library_sources import library_sources_bp
    from app.routes.document_import import document_import_bp
    from app.routes.cache_management import cache_management_bp
    from app.routes.video_sources import video_sources_bp
    from app.routes.ai_coding import ai_coding_bp
    from app.routes.export_routes import export_bp
    from app.routes.project_start import project_start_bp

    app.register_blueprint(projects_bp, url_prefix="/projects")
    app.register_blueprint(documents_bp, url_prefix="/projects")
    app.register_blueprint(doc_access_bp)
    app.register_blueprint(search_bp, url_prefix="/projects")
    app.register_blueprint(extended_search_bp)
    app.register_blueprint(search_advanced_bp, url_prefix="/projects")
    app.register_blueprint(chat_bp, url_prefix="/projects")
    app.register_blueprint(codes_bp, url_prefix="/projects")
    app.register_blueprint(data_bp, url_prefix="/projects")
    app.register_blueprint(extraction_bp, url_prefix="/projects")
    app.register_blueprint(stats_bp, url_prefix="/projects")
    app.register_blueprint(training_bp, url_prefix="/projects")
    app.register_blueprint(document_map_bp, url_prefix="/projects")
    app.register_blueprint(related_bp, url_prefix="/projects")
    app.register_blueprint(report_bp, url_prefix="/projects")
    app.register_blueprint(contradiction_bp, url_prefix="/projects")
    app.register_blueprint(annotations_bp, url_prefix="/projects")
    app.register_blueprint(reports_bp, url_prefix="/projects")
    app.register_blueprint(matrices_bp, url_prefix="/projects")
    app.register_blueprint(collab_bp, url_prefix="/projects")
    app.register_blueprint(compliance_bp, url_prefix="/projects")
    app.register_blueprint(lifecycle_bp, url_prefix="/projects")
    app.register_blueprint(retention_bp, url_prefix="/projects")
    app.register_blueprint(observability_bp, url_prefix="/projects")
    app.register_blueprint(phi_bp, url_prefix="/projects")
    app.register_blueprint(tasks_bp, url_prefix="/projects")
    app.register_blueprint(library_sources_bp, url_prefix="/projects")
    app.register_blueprint(document_import_bp, url_prefix="/projects")
    app.register_blueprint(cache_management_bp, url_prefix="/projects")
    app.register_blueprint(video_sources_bp, url_prefix="/projects")
    app.register_blueprint(ai_coding_bp, url_prefix="/projects")
    app.register_blueprint(export_bp, url_prefix="/projects")
    app.register_blueprint(project_start_bp)

    # ── Global / unscoped pages ─────────────────────────────────────────────
    from app.routes.global_chat import global_chat_bp
    from app.routes.references import references_bp
    from app.routes.ai_templates import ai_templates_bp
    from app.routes.integration import integration_bp
    from app.routes.user_integrations import user_integrations_bp
    from app.routes.manuscripts import manuscripts_bp
    from app.routes.export_jobs import export_jobs_bp
    from app.routes.tenants_ui import tenants_ui_bp

    app.register_blueprint(global_chat_bp)
    app.register_blueprint(references_bp)
    app.register_blueprint(ai_templates_bp)
    app.register_blueprint(integration_bp)
    app.register_blueprint(user_integrations_bp)
    app.register_blueprint(manuscripts_bp)
    app.register_blueprint(export_jobs_bp)
    app.register_blueprint(tenants_ui_bp)

    # ── AI Discovery (Phase 1) ─────────────────────────────────────────────
    from app.routes.feed import feed_bp
    from app.routes.reading_list import reading_list_bp
    from app.routes.alerts import alerts_bp
    from app.routes.research_interests import research_interests_bp

    app.register_blueprint(feed_bp)
    app.register_blueprint(reading_list_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(research_interests_bp)

    # ── Phase 2 — Evidence Synthesis ────────────────────────────────────────
    from app.routes.synthesis import synthesis_bp

    app.register_blueprint(synthesis_bp)

    # ── Phase 3 — Knowledge Map ────────────────────────────────────────────
    from app.routes.knowledge_map import knowledge_map_bp

    app.register_blueprint(knowledge_map_bp)

    # ── Admin ───────────────────────────────────────────────────────────────
    from app.routes.admin_routes import admin_bp
    from app.routes.admin.admin_api import admin_api_bp
    from app.routes.admin.admin_documents import admin_documents_bp
    from app.routes.admin.admin_storage import admin_storage_bp
    from app.routes.admin.admin_quotas import admin_quotas_bp
    from app.routes.admin.admin_users import admin_users_bp
    from app.routes.admin.admin_settings import admin_settings_bp
    from app.routes.admin.admin_packages import admin_packages_bp
    from app.routes.admin.admin_invites import admin_invites_bp
    from app.routes.admin.roles import role_admin_bp
    from app.routes.admin.user_roles import user_role_admin_bp
    from app.routes.admin.debug import debug_bp
    from app.routes.admin.monitoring import monitoring_bp
    from app.routes.admin.batch_operations import batch_bp
    from app.routes.admin.permission_management import permission_bp
    from app.routes.admin.plugin_management import plugin_admin
    from app.routes.admin_integrations import admin_integrations_bp

    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(admin_api_bp, url_prefix="/admin/api")
    app.register_blueprint(admin_documents_bp, url_prefix="/admin/documents")
    app.register_blueprint(admin_storage_bp, url_prefix="/admin/storage")
    app.register_blueprint(admin_quotas_bp, url_prefix="/admin/quota")
    app.register_blueprint(admin_users_bp, url_prefix="/admin/users")
    app.register_blueprint(admin_settings_bp, url_prefix="/admin/settings")
    app.register_blueprint(admin_packages_bp)
    app.register_blueprint(admin_invites_bp, url_prefix="/admin/invites")
    app.register_blueprint(role_admin_bp, url_prefix="/admin/roles")
    app.register_blueprint(user_role_admin_bp, url_prefix="/admin/user-roles")
    app.register_blueprint(debug_bp)
    app.register_blueprint(monitoring_bp)
    app.register_blueprint(batch_bp)
    app.register_blueprint(permission_bp)
    app.register_blueprint(plugin_admin)
    app.register_blueprint(admin_integrations_bp)

    # ── Tenant API ─────────────────────────────────────────────────────────
    from app.routes.tenants import tenants_bp

    app.register_blueprint(tenants_bp, url_prefix="/tenants")
