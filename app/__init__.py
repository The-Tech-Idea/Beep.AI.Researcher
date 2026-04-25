"""Beep.AI.Researcher — Internal research app (Flask). All config via config_manager."""
import os
from flask import Flask, redirect, url_for, render_template, request
from flask_login import LoginManager
from sqlalchemy import inspect, text
from datetime import timedelta

from app.config_manager import config_manager
from app.config import get_config
from app.services.localization_manager import localization_manager


def _migrate_user_columns(db):
    """Add User model columns for email verification if missing."""
    cols = [
        ('email_verified', 'BOOLEAN DEFAULT 1'),  # 1 for existing users (backward compat)
        ('verification_token', 'VARCHAR(120)'),
        ('verification_token_expires', 'DATETIME'),
        ('display_name', 'VARCHAR(120)'),
        ('updated_at', 'DATETIME'),
    ]
    for col, col_type in cols:
        try:
            db.session.execute(text(f'ALTER TABLE users ADD COLUMN {col} {col_type}'))
            db.session.commit()
        except Exception:
            db.session.rollback()


def _migrate_feed_recommendation_columns(db):
    """Add persisted Phase 1 feed metadata columns when upgrading an existing database."""
    try:
        inspector = inspect(db.engine)
        if 'feed_recommendations' not in inspector.get_table_names():
            return
        existing_columns = {column['name'] for column in inspector.get_columns('feed_recommendations')}
    except Exception:
        db.session.rollback()
        return

    columns = [
        ('source_id', 'VARCHAR(255)'),
        ('url', 'TEXT'),
        ('publication_date', 'VARCHAR(40)'),
        ('doi', 'VARCHAR(255)'),
    ]
    for column_name, column_type in columns:
        if column_name in existing_columns:
            continue
        try:
            db.session.execute(text(f'ALTER TABLE feed_recommendations ADD COLUMN {column_name} {column_type}'))
            db.session.commit()
        except Exception:
            db.session.rollback()



def create_app(config_name=None):
    """Application factory. All configuration from config_manager."""
    base_path = config_manager.base_path
    template_path = str(base_path / 'templates')
    static_path = str(base_path / 'static')

    app = Flask(__name__,
                template_folder=template_path,
                static_folder=static_path)

    app.config['SECRET_KEY'] = config_manager.get_with_env(
        'secret_key', 'SECRET_KEY', 'beep-researcher-secret'
    )
    
    # Session configuration - prevent random logouts
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Allow same-origin AJAX
    app.config['SESSION_COOKIE_HTTPONLY'] = True   # Security
    app.config['SESSION_COOKIE_SECURE'] = False    # Set True for HTTPS only
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)  # Session lasts 7 days
    app.config['SESSION_REFRESH_EACH_REQUEST'] = True  # Extend session on activity
    app.config['TESTING'] = os.getenv('TESTING', '').lower() in ('1', 'true', 'yes')
    
    default_uri = f'sqlite:///{config_manager.db_path}'
    configured_database_url = config_manager.get_with_env(
        'SQLALCHEMY_DATABASE_URI', 'DATABASE_URL', default_uri
    )
    if app.config['TESTING'] and os.getenv('DATABASE_URL'):
        configured_database_url = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_DATABASE_URI'] = configured_database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    from app.database import db
    from app.models.core import User
    db.init_app(app)

    login_manager = LoginManager(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    with app.app_context():
        # Import core models first (no dependencies)
        from app.models.core import User, Role, AuditLog
        from app.models.tenant import Tenant, TenantMember
        from app.models.rbac import RBACRole, UserRole, DocumentAccess, UserGroup  # Phase 1.8 RBAC
        
        # NOW import researcher models (depends on Tenant being registered)
        from app.models.researcher import (
            ResearchProject, ProjectMember, ProjectComment, ResearcherDocument, Code, CodedReference,
            DocumentAnnotation, ChatSession, ChatMessage,
            ResearcherDataSource, SavedChart, ScheduledReport,
            ExtractionSchema, ExtractionResult,
            Flashcard, Quiz, QuizQuestion, QuizAttempt,
            ResearchTask, Reference, TaskNotification,
            LibrarySource, SourceConnection, SourceImportLog,  # Phase 2.2 Library sources
            SearchCache, SearchIndex  # Phase 2.5 Search caching & indexing
        )
        from app.models.researcher.plugin_permissions import (
            PluginPermission, PluginRoleAssignment, PluginAudit
        )
        # Phase B models
        from app.models.researcher.phase_b_models import (
            RetentionPolicy, CompliancePolicyTemplate
        )
        # Phase 1 — AI Discovery models
        from app.models.researcher.phase_1_models import (
            ResearchInterestProfile, FeedRecommendation, ReadingListItem, PaperAlert,
        )
        # Phase C sector models
        from app.models.researcher.sector_models import (
            Hypothesis, HypothesisEvidence, PlagiarismCheck,
            EvidenceGrade, ClauseTemplate, CitationValidation
        )
        # Integration models
        from app.models.researcher.integrations import (
            IntegrationCredential, ProjectIntegration,
            WebhookSubscription, WebhookDelivery
        )

        if not app.config.get('TESTING', False):
            try:
                db.create_all()
            except Exception as _create_all_err:  # noqa: F841
                # Tables already exist (e.g. after hot-reload); use checkfirst path instead
                try:
                    with db.engine.connect() as _conn:
                        db.metadata.create_all(bind=_conn, checkfirst=True)
                except Exception:
                    app.logger.warning(
                        "db.create_all() skipped (tables already exist): %s", _create_all_err
                    )
            _migrate_user_columns(db)
            _migrate_feed_recommendation_columns(db)
        
        # Phase 1.8: Seed built-in RBAC roles
        if os.getenv('SKIP_SEED_ROLES', '').lower() not in ('1', 'true', 'yes'):
            try:
                from app.scripts.seed_roles import seed_builtin_roles
                seed_builtin_roles()
            except Exception as e:
                print(f"Warning: Could not seed RBAC roles: {e}")
        
        # Phase 2.5: Register cache invalidation event handlers
        if not app.config.get('TESTING', False):
            try:
                from app.services.cache_event_handlers import register_cache_invalidation_handlers
                register_cache_invalidation_handlers()
            except Exception as e:
                print(f"Warning: Could not register cache event handlers: {e}")

        try:
            from app.services.scheduled_report_service import initialize_scheduled_report_runtime
            initialize_scheduled_report_runtime(app, start_dispatcher=not app.config.get('TESTING', False))
        except Exception as e:
            print(f"Warning: Could not initialize scheduled report runtime: {e}")

        # Phase B.2: Seed built-in compliance templates
        if not app.config.get('TESTING', False):
            try:
                from app.models.researcher.phase_b_models import seed_compliance_templates
                seed_compliance_templates()
            except Exception as e:
                print(f"Warning: Could not seed compliance templates: {e}")

        # Phase 9b: Seed default integration services
        if not app.config.get('TESTING', False):
            try:
                from app.services.integration_service import seed_default_services
                seed_default_services()
            except Exception as e:
                print(f"Warning: Could not seed default integration services: {e}")

    from app.routes.dashboard import dashboard_bp
    from app.routes.projects import projects_bp
    from app.routes.documents import documents_bp, doc_access_bp
    from app.routes.search import search_bp
    from app.routes.extended_search import extended_search_bp
    from app.routes.chat import chat_bp
    from app.routes.global_chat import global_chat_bp
    from app.routes.codes import codes_bp
    from app.routes.data_analyst import data_bp
    from app.routes.export_routes import export_bp
    from app.routes.ai_coding import ai_coding_bp
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
    from app.routes.observability import observability_bp
    from app.routes.phi_routes import phi_bp
    from app.routes.tenants import tenants_bp
    from app.routes.tasks import tasks_bp
    from app.routes.tenants_ui import tenants_ui_bp
    from app.routes.auth_routes import auth_bp
    from app.routes.setup import setup_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.admin_integrations import admin_integrations_bp
    from app.routes.user_integrations import user_integrations_bp
    from app.routes.references import references_bp
    from app.routes.ai_templates import ai_templates_bp
    from app.routes.library_sources import library_sources_bp
    from app.routes.document_import import document_import_bp
    from app.routes.search_advanced import search_advanced_bp
    from app.routes.cache_management import cache_management_bp  # Phase 2.5 Cache management
    from app.routes.project_start import project_start_bp
    from app.routes.video_sources import video_sources_bp  # Phase 03 video ingest
    from app.routes.manuscripts import manuscripts_bp  # Phase 04 writing studio
    from app.routes.export_jobs import export_jobs_bp  # Phase 05 export
    from app.routes.feed import feed_bp  # Phase 1 AI Discovery
    from app.routes.reading_list import reading_list_bp  # Phase 1 AI Discovery
    from app.routes.alerts import alerts_bp  # Phase 1 AI Discovery
    from app.routes.research_interests import research_interests_bp  # Phase 1 AI Discovery

    # Phase 1.8 RBAC routes
    from app.routes.admin.roles import role_admin_bp
    from app.routes.admin.user_roles import user_role_admin_bp
    from app.routes.admin.debug import debug_bp
    from app.routes.admin.monitoring import monitoring_bp
    from app.routes.admin.batch_operations import batch_bp
    from app.routes.admin.permission_management import permission_bp
    from app.routes.admin.plugin_management import plugin_admin
    from app.routes.retention import retention_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(setup_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(admin_integrations_bp)
    app.register_blueprint(user_integrations_bp)
    app.register_blueprint(references_bp)
    app.register_blueprint(ai_templates_bp)
    app.register_blueprint(global_chat_bp)
    
    # Phase 1.8 RBAC blueprints
    app.register_blueprint(role_admin_bp)
    app.register_blueprint(user_role_admin_bp)
    app.register_blueprint(doc_access_bp)
    app.register_blueprint(debug_bp)
    app.register_blueprint(monitoring_bp)
    app.register_blueprint(batch_bp)
    app.register_blueprint(permission_bp)
    app.register_blueprint(plugin_admin)
    app.register_blueprint(project_start_bp)

    @app.before_request
    def check_setup():
        from flask import request, current_app
        if current_app.config.get('TESTING'):
            return None
        if config_manager.is_configured:
            return None
        if request.endpoint and ('setup' in request.endpoint or request.endpoint == 'static'):
            return None
        if request.path.startswith('/static/'):
            return None
        return redirect(url_for('setup.index'))

    @app.before_request
    def enforce_session():
        """Heartbeat server-side sessions and enforce idle/lifetime timeouts."""
        from flask_login import current_user
        if current_user and current_user.is_authenticated:
            from app.services.session_service import heartbeat
            heartbeat()

    @app.context_processor
    def inject_locale():
        supported_locales = localization_manager.get_supported_locales() or ['en']
        cookie_locale = request.cookies.get('preferred_locale')
        locale = cookie_locale if cookie_locale in supported_locales else None
        if not locale:
            locale = request.accept_languages.best_match(supported_locales) or 'en'
        def t(key):
            return localization_manager.translate(key, lang=locale)
        names = {loc: localization_manager.get_locale_label(loc) for loc in supported_locales}
        runtime_config = get_config()
        ui_features = {
            'ai_discovery_enabled': runtime_config.is_feature_enabled('ai_discovery_enabled'),
            'chat_enabled': runtime_config.is_feature_enabled('chat_enabled'),
            'web_search_enabled': runtime_config.is_feature_enabled('web_search_enabled'),
            'plugins_enabled': runtime_config.is_feature_enabled('plugins_enabled'),
            'notifications_enabled': runtime_config.is_feature_enabled('notifications_enabled'),
        }
        return {
            't': t,
            'current_locale': locale,
            'supported_locales': supported_locales,
            'locale_label': names.get(locale, locale),
            'locale_names': names,
            'ui_features': ui_features,
        }

    @app.route('/set-locale/<locale>')
    def set_locale(locale):
        supported_locales = localization_manager.get_supported_locales() or ['en']
        target = locale if locale in supported_locales else 'en'
        next_url = request.args.get('next') or request.referrer or url_for('researcher.index')
        resp = redirect(next_url)
        resp.set_cookie('preferred_locale', target, max_age=30 * 24 * 60 * 60)
        return resp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(projects_bp, url_prefix='/projects')
    app.register_blueprint(documents_bp, url_prefix='/projects')
    app.register_blueprint(search_bp, url_prefix='/projects')
    app.register_blueprint(extended_search_bp, url_prefix='')
    app.register_blueprint(chat_bp, url_prefix='/projects')
    app.register_blueprint(codes_bp, url_prefix='/projects')
    app.register_blueprint(data_bp, url_prefix='/projects')
    app.register_blueprint(export_bp, url_prefix='/projects')
    app.register_blueprint(ai_coding_bp, url_prefix='/projects')
    app.register_blueprint(extraction_bp, url_prefix='/projects')
    app.register_blueprint(stats_bp, url_prefix='/projects')
    app.register_blueprint(training_bp, url_prefix='/projects')
    app.register_blueprint(document_map_bp, url_prefix='/projects')
    app.register_blueprint(related_bp, url_prefix='/projects')
    app.register_blueprint(report_bp, url_prefix='/projects')
    app.register_blueprint(contradiction_bp, url_prefix='/projects')
    app.register_blueprint(annotations_bp, url_prefix='/projects')
    app.register_blueprint(reports_bp, url_prefix='/projects')
    app.register_blueprint(matrices_bp, url_prefix='/projects')
    app.register_blueprint(collab_bp, url_prefix='/projects')
    app.register_blueprint(compliance_bp, url_prefix='/projects')
    app.register_blueprint(lifecycle_bp, url_prefix='/projects')
    app.register_blueprint(retention_bp, url_prefix='/projects')
    app.register_blueprint(observability_bp, url_prefix='/projects')
    app.register_blueprint(phi_bp, url_prefix='/projects')
    app.register_blueprint(tasks_bp, url_prefix='/projects')
    app.register_blueprint(library_sources_bp, url_prefix='/projects')
    app.register_blueprint(document_import_bp, url_prefix='/projects')
    app.register_blueprint(search_advanced_bp, url_prefix='/projects')
    app.register_blueprint(cache_management_bp, url_prefix='/projects')  # Phase 2.5 Cache management
    app.register_blueprint(video_sources_bp, url_prefix='/projects')  # Phase 03 video ingest
    app.register_blueprint(manuscripts_bp, url_prefix='')  # Phase 04 writing studio
    app.register_blueprint(export_jobs_bp, url_prefix='')  # Phase 05 export
    app.register_blueprint(feed_bp)  # Phase 1 AI Discovery
    app.register_blueprint(reading_list_bp)  # Phase 1 AI Discovery
    app.register_blueprint(alerts_bp)  # Phase 1 AI Discovery
    app.register_blueprint(research_interests_bp)  # Phase 1 AI Discovery
    app.register_blueprint(tenants_bp, url_prefix='/tenants')
    app.register_blueprint(tenants_ui_bp)

    @app.route('/')
    def index():
        from flask_login import current_user
        if not config_manager.is_configured:
            return redirect(url_for('setup.index'))
        if current_user.is_authenticated:
            return redirect(url_for('researcher.index'))
        # Preserve historical behavior used by tests: root lands on researcher dashboard path.
        return redirect(url_for('researcher.index'))

    @app.route('/landing')
    def landing():
        from flask_login import current_user
        if not config_manager.is_configured:
            return redirect(url_for('setup.index'))
        if current_user.is_authenticated:
            return redirect(url_for('researcher.index'))
        return render_template('landing.html')

    @app.route('/check-ai-server')
    def check_ai_server():
        """Check AI Server connection status for the navbar indicator"""
        from flask import jsonify
        from flask_login import current_user, login_required
        
        # Only allow authenticated users
        if not current_user.is_authenticated:
            return jsonify({'configured': False, 'server_reachable': False, 'token_valid': False, 'error': 'Not authenticated'}), 401
        
        try:
            from app.services.beep_ai_client import get_connection_status
            status = get_connection_status()
            return jsonify(status)
        except Exception as e:
            return jsonify({
                'configured': False,
                'server_reachable': False,
                'token_valid': False,
                'error': str(e)
            })

    return app
