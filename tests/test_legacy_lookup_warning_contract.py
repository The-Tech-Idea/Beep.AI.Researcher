from pathlib import Path


RESEARCHER_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path):
    return (RESEARCHER_ROOT / relative_path).read_text(encoding='utf-8')


def test_project_lookup_routes_do_not_use_legacy_query_get_or_404():
    for relative_path in (
        'app/routes/projects.py',
        'app/routes/training.py',
        'app/routes/report_writing.py',
        'app/routes/chat.py',
        'app/routes/ai_coding.py',
        'app/routes/annotations.py',
        'app/routes/collaboration.py',
        'app/routes/compliance.py',
        'app/routes/codes.py',
        'app/routes/coding_matrices.py',
        'app/routes/data_analyst.py',
        'app/routes/document_map.py',
        'app/routes/documents.py',
        'app/routes/document_import.py',
        'app/routes/extended_search.py',
        'app/routes/export_routes.py',
        'app/routes/lifecycle.py',
        'app/routes/library_sources.py',
        'app/routes/observability.py',
        'app/routes/retention.py',
        'app/routes/scheduled_reports.py',
        'app/routes/search.py',
        'app/routes/search_advanced.py',
        'app/routes/stats.py',
        'app/routes/tasks.py',
    ):
        source = _read(relative_path)
        assert 'ResearchProject.query.get_or_404(project_id)' not in source
        assert 'def _get_project_or_404(project_id):' in source

    references_source = _read('app/routes/references.py')
    assert 'ResearchProject.query.get_or_404(project_id)' not in references_source
    assert 'ResearchProject.query.get(project_id)' not in references_source
    assert 'def _get_project(project_id):' in references_source
    assert 'def _get_project_or_404(project_id):' in references_source


def test_chat_models_do_not_use_datetime_utcnow_defaults():
    source = _read('app/models/researcher/researcher_chat.py')
    assert 'datetime.utcnow' not in source
    assert 'utcnow_naive' in source

    for relative_path in (
        'app/routes/document_import.py',
        'app/routes/extended_search.py',
        'app/routes/library_sources.py',
        'app/routes/search_advanced.py',
    ):
        source = _read(relative_path)
        assert 'datetime.utcnow' not in source
        assert 'utcnow_naive' in source

    compliance_source = _read('app/routes/compliance.py')
    assert 'datetime.utcnow' not in compliance_source
    assert 'utcnow_naive' in compliance_source

    lifecycle_source = _read('app/routes/lifecycle.py')
    assert 'datetime.utcnow' not in lifecycle_source
    assert 'utcnow_naive' in lifecycle_source

    observability_source = _read('app/routes/observability.py')
    assert 'datetime.utcnow' not in observability_source
    assert 'utcnow_naive' in observability_source

    for relative_path in (
        'app/integrations/search/base.py',
        'app/integrations/search/search_manager.py',
        'app/models/researcher/library_sources.py',
        'app/models/researcher/phase_a_models.py',
        'app/models/researcher/phase_b_models.py',
        'app/models/researcher/researcher_coding.py',
    ):
        source = _read(relative_path)
        assert 'datetime.utcnow' not in source
        assert 'utcnow_naive' in source

    document_import_source = _read('app/routes/document_import.py')
    assert '.subquery()' not in document_import_source
    assert 'select(LibrarySource.id)' in document_import_source


def test_targeted_warning_regression_tests_use_session_get():
    for relative_path in (
        'tests/test_training.py',
        'tests/test_report_writing.py',
        'tests/test_report_editor_routes.py',
        'tests/test_anti_hallucination.py',
    ):
        source = _read(relative_path)
        assert 'ResearchProject.query.get(test_project.id)' not in source


def test_route_cluster_avoids_legacy_query_get_helpers():
    for relative_path in (
        'app/routes/admin/batch_operations.py',
        'app/routes/admin/debug.py',
        'app/routes/ai_templates.py',
        'app/integrations/search/base.py',
        'app/routes/collaboration.py',
        'app/routes/codes.py',
        'app/routes/document_import.py',
        'app/routes/documents.py',
        'app/routes/dashboard.py',
        'app/routes/references.py',
        'app/routes/tenants.py',
    ):
        source = _read(relative_path)
        assert '.query.get(' not in source


def test_admin_and_support_routes_avoid_legacy_query_get_or_404_helpers():
    for relative_path in (
        'app/routes/admin/debug.py',
        'app/routes/admin_routes.py',
        'app/routes/ai_templates.py',
        'app/routes/dashboard.py',
        'app/routes/tenants.py',
    ):
        source = _read(relative_path)
        assert '.query.get_or_404(' not in source


def test_service_lookup_helpers_avoid_legacy_query_get_helpers():
    for relative_path in (
        'app/services/extraction_service.py',
        'app/services/quota_service.py',
        'app/services/session_service.py',
    ):
        source = _read(relative_path)
        assert '.query.get(' not in source
        assert '.query.get_or_404(' not in source


def test_route_and_service_files_avoid_datetime_utcnow():
    """Enforce that all patched route/service files use utcnow_naive() from time_utils."""
    for relative_path in (
        'app/routes/admin/debug.py',
        'app/routes/admin/permission_management.py',
        'app/routes/ai_templates.py',
        'app/routes/phi_routes.py',
        'app/services/plugin_manager.py',
        'app/services/plugin_base.py',
        'app/services/task_notifications.py',
    ):
        source = _read(relative_path)
        assert 'datetime.utcnow' not in source, (
            f"{relative_path} still uses datetime.utcnow(); use utcnow_naive() instead"
        )
        assert 'utcnow_naive' in source, (
            f"{relative_path} does not import/use utcnow_naive()"
        )


def test_admin_blueprints_are_imported_in_app_init():
    """Ensure the previously-unregistered admin blueprints are wired into the app factory."""
    source = _read('app/__init__.py')
    for import_fragment in (
        'from app.routes.admin.batch_operations import batch_bp',
        'from app.routes.admin.permission_management import permission_bp',
        'from app.routes.admin.plugin_management import plugin_admin',
        'from app.routes.retention import retention_bp',
    ):
        assert import_fragment in source, (
            f"app/__init__.py is missing: {import_fragment}"
        )
    for register_fragment in (
        'app.register_blueprint(batch_bp)',
        'app.register_blueprint(permission_bp)',
        'app.register_blueprint(plugin_admin)',
        'app.register_blueprint(retention_bp',
    ):
        assert register_fragment in source, (
            f"app/__init__.py is missing registration: {register_fragment}"
        )


def test_model_and_job_files_avoid_datetime_utcnow():
    """Enforce that model, job, integration, and decorator files use utcnow_naive."""
    for relative_path in (
        'app/models/researcher/batch_operations.py',
        'app/models/researcher/ai_templates.py',
        'app/models/researcher/extraction_plugins.py',
        'app/models/researcher/plugin_permissions.py',
        'app/models/researcher/plugins.py',
        'app/models/researcher/researcher_notifications.py',
        'app/models/researcher/researcher_extraction.py',
        'app/models/researcher/researcher_data.py',
        'app/models/researcher/user_preferences.py',
        'app/jobs/pdf_download_handler.py',
        'app/integrations/webhooks/webhook_manager.py',
        'app/integrations/sync_engine.py',
        'app/integrations/export/markdown_export.py',
        'app/scripts/seed_roles.py',
        'app/decorators/plugin_permissions.py',
    ):
        source = _read(relative_path)
        assert 'datetime.utcnow' not in source, (
            f"{relative_path} still uses datetime.utcnow(); use utcnow_naive() instead"
        )
        assert 'utcnow_naive' in source, (
            f"{relative_path} does not import/use utcnow_naive()"
        )


def test_admin_routes_split_sub_modules_exist():
    """Enforce that admin_routes.py was split and sub-modules contain their routes."""
    admin_routes_source = _read('app/routes/admin_routes.py')
    lines = admin_routes_source.splitlines()
    assert len(lines) < 150, (
        f"admin_routes.py should be <150 lines after split; got {len(lines)}"
    )
    assert 'admin_bp = Blueprint' in admin_routes_source
    assert 'admin_required' in admin_routes_source
    # Sub-module trigger imports must be present
    for sub in ('admin_users', 'admin_settings', 'admin_quotas',
                 'admin_documents', 'admin_invites', 'admin_api'):
        assert sub in admin_routes_source, (
            f"admin_routes.py missing sub-module trigger import for {sub}"
        )

    # Each sub-module must exist and must register routes on admin_bp
    for relative_path in (
        'app/routes/admin/admin_users.py',
        'app/routes/admin/admin_settings.py',
        'app/routes/admin/admin_quotas.py',
        'app/routes/admin/admin_documents.py',
        'app/routes/admin/admin_invites.py',
        'app/routes/admin/admin_api.py',
    ):
        source = _read(relative_path)
        assert 'from app.routes.admin_routes import admin_bp' in source, (
            f"{relative_path} must import admin_bp from admin_routes"
        )
        assert '@admin_bp.route(' in source, (
            f"{relative_path} must define at least one route on admin_bp"
        )
