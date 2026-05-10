# Beep.AI.Researcher — Clean Architecture Restructuring Plan

> **Generated**: 2026-05-04
> **Based on**: Flask official docs, Microsoft cookiecutter, Real Python, current codebase scan

---

## Problem Statement

Current issues identified in the codebase:

1. **No service-layer boundary** — 61 services and 45+ route files all import `from app.database import db` and query models directly. Routes mix HTTP handling with business logic.
2. **Heavy packages at startup** — `docling`, `unstructured`, `llama-index`, `scikit-learn` are in `requirements.txt` and installed on every `./run.bat`. These add GBs of ML models but are only needed for optional features.
3. **No repository pattern** — Data access is scattered across routes and services with no abstraction layer.
4. **No dependency injection** — Services instantiate their own dependencies (e.g., `EvidenceSynthesisService()` creates its own `BeepAIClient`).
5. **Messy blueprint registration** — 45+ blueprints, many with no URL prefix, registered in a monolithic `create_app()`.
6. **No error handlers** — Flask default error pages are shown for 404, 500, 403.
7. **No configuration classes** — Single JSON config, no dev/test/prod separation.
8. **No CLI commands** — No `flask db migrate`, no admin CLI tools.

---

## Phase A — Service & Repository Architecture

### A.1 Define base classes

```
app/
  repositories/
    __init__.py
    base.py              # BaseRepository ABC with CRUD
    user_repository.py
    project_repository.py
    document_repository.py
    reference_repository.py
    ...                  # One per aggregate root
  services/
    __init__.py
    base.py              # BaseService with DI container
    user_service.py
    project_service.py
    ...
  extensions/            # Flask extension instances (not bound to app)
    __init__.py
    db.py                # db = SQLAlchemy(model_class=Base)
    login_manager.py
    mail.py
    ...
```

### A.2 Dependency injection container

Create a simple DI container (no framework needed):

```python
# app/services/container.py
from typing import Dict, Type, Callable, Any

class Container:
    """Simple dependency injection container."""
    _registry: Dict[Type, Callable[[], Any]] = {}
    _singletons: Dict[Type, Any] = {}

    @classmethod
    def register(cls, interface: Type, factory: Callable[[], Any], *, singleton: bool = False):
        cls._registry[interface] = factory
        cls._singletons[interface] = None if not singleton else factory()

    @classmethod
    def get(cls, interface: Type) -> Any:
        if interface in cls._singletons and cls._singletons[interface] is not None:
            return cls._singletons[interface]
        return cls._registry[interface]()

    @classmethod
    def reset(cls):
        """Clear all registrations — for testing."""
        cls._registry.clear()
        cls._singletons.clear()
```

### A.3 Register services at startup

```python
# app/services/container_setup.py
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService
from app.services.container import Container
from app.extensions.db import db

def setup_container(app):
    with app.app_context():
        # Repositories
        Container.register(UserRepository, lambda: UserRepository(db.session), singleton=False)

        # Services (inject repositories)
        Container.register(
            UserService,
            lambda: UserService(Container.get(UserRepository)),
            singleton=True
        )
```

### A.4 Clean service example

```python
# app/repositories/base.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List
from sqlalchemy.orm import Session

T = TypeVar('T')

class BaseRepository(ABC, Generic[T]):
    def __init__(self, session: Session):
        self._session = session

    @abstractmethod
    def get(self, id: int) -> Optional[T]: ...

    @abstractmethod
    def get_all(self) -> List[T]: ...

    def add(self, entity: T) -> T:
        self._session.add(entity)
        self._session.flush()
        return entity

    def delete(self, entity: T) -> None:
        self._session.delete(entity)

    def commit(self) -> None:
        self._session.commit()
```

```python
# app/repositories/project_repository.py
from typing import Optional, List
from app.models.researcher.researcher_projects import ResearchProject
from app.repositories.base import BaseRepository

class ProjectRepository(BaseRepository[ResearchProject]):
    def get(self, id: int) -> Optional[ResearchProject]:
        return self._session.get(ResearchProject, id)

    def get_all(self) -> List[ResearchProject]:
        return self._session.query(ResearchProject).all()

    def get_by_owner(self, owner_id: int) -> List[ResearchProject]:
        return self._session.query(ResearchProject).filter_by(owner_id=owner_id).all()
```

```python
# app/services/project_service.py
from typing import List, Optional
from app.services.container import Container
from app.repositories.project_repository import ProjectRepository
from app.models.researcher.researcher_projects import ResearchProject

class ProjectService:
    """Business logic for projects. Only talks to repositories, never to db directly."""

    def __init__(self, repo: ProjectRepository):
        self._repo = repo

    def get_project(self, project_id: int, user_id: int) -> Optional[ResearchProject]:
        """Get project only if user has access."""
        project = self._repo.get(project_id)
        if not project:
            return None
        if project.owner_id == user_id:
            return project
        # Check membership...
        return None

    def list_user_projects(self, user_id: int) -> List[ResearchProject]:
        return self._repo.get_by_owner(user_id)
```

### A.5 Clean route example

```python
# app/routes/projects.py
from flask import Blueprint, jsonify, request, current_app
from flask_login import current_user, login_required
from app.services.container import Container
from app.services.project_service import ProjectService

projects_bp = Blueprint('projects', __name__, url_prefix='/api/projects')

@projects_bp.route('/<int:project_id>', methods=['GET'])
@login_required
def get_project(project_id):
    """Thin controller — delegates to service."""
    service = Container.get(ProjectService)
    project = service.get_project(project_id, current_user.id)
    if project is None:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(project.to_dict())
```

### A.6 Migration path (incremental, not rewrite)

**Do NOT rewrite everything at once.** Migrate feature by feature:

1. **Start with new features only** — all new code uses the container + service + repository pattern
2. **Migrate Phase 1 (AI Discovery)** first — it's complete and well-tested
3. **Migrate Phase 2 (Evidence Synthesis)** next
4. **Continue phase by phase** — old code still works alongside new code
5. **Never break existing routes** — keep both patterns coexisting during migration

---

## Phase B — Optional Feature Packages

### B.1 Split requirements.txt

```
# requirements.txt — CORE (always installed)
Flask>=3.0.0
Flask-SQLAlchemy>=3.1.0
Flask-Login>=0.6.0
Werkzeug>=3.0.0
Jinja2>=3.1.2
requests>=2.31.0
openpyxl>=3.1.0
python-docx>=0.8.11
xhtml2pdf>=0.2.14
markdown>=3.4.0
pypdf>=4.0.0
psutil>=5.9.0
alembic>=1.12.0
cryptography>=41.0.0
pyotp>=2.9.0
qrcode[pil]>=7.4.2
scikit-learn>=1.3.0
citeproc-py>=0.6.0
pytest>=7.0.0

# requirements-optional.txt — INSTALLED ON DEMAND via admin UI
# docling[easyocr,rapidocr,htmlrender,onnxruntime,asr,xbrl,vlm]>=2.8.0
# pymupdf4llm>=0.0.27
# PyMuPDF>=1.25.0
# unstructured[all-docs,local-inference]>=0.16.0
# pdfplumber>=0.11.0
# pytesseract>=0.3.10
# Pillow>=10.0.0
# llama-index-core>=0.12.0
# llama-index-readers-file>=0.4.0
# llama-index-storage-docstore-redis>=0.3.0
# llama-index-storage-docstore-mongodb>=0.3.0
# boto3>=1.34.0
# azure-storage-blob>=12.19.0
# smbprotocol>=1.13.0
# msal>=1.26.0
# google-api-python-client>=2.100.0
# google-auth>=2.22.0
# google-auth-httplib2>=0.1.1
# google-auth-oauthlib>=1.2.0
# spacy>=3.7.0
```

### B.2 Admin feature installer

```python
# app/routes/admin/admin_packages.py
import subprocess
import json
from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required

from app.config_manager import config_manager

OPTIONAL_PACKAGES = {
    "document_ocr": {
        "packages": ["docling[easyocr,rapidocr]", "pytesseract", "Pillow"],
        "label": "Document OCR & Layout Analysis",
        "description": "Advanced PDF parsing, OCR, table recognition",
        "size_mb": "~2000",
        "feature_flag": "document_ocr_enabled",
    },
    "rag_ingestion": {
        "packages": ["llama-index-core", "llama-index-readers-file", "pymupdf4llm", "PyMuPDF"],
        "label": "RAG Document Ingestion",
        "description": "LlamaIndex document store, chunking, vector indexing",
        "size_mb": "~500",
        "feature_flag": "rag_ingestion_enabled",
    },
    "s3_storage": {
        "packages": ["boto3"],
        "label": "S3/MinIO Storage Backend",
        "description": "Store documents on S3-compatible storage",
        "size_mb": "~50",
        "feature_flag": "s3_storage_enabled",
    },
    "azure_storage": {
        "packages": ["azure-storage-blob"],
        "label": "Azure Blob Storage Backend",
        "description": "Store documents on Azure Blob Storage",
        "size_mb": "~100",
        "feature_flag": "azure_storage_enabled",
    },
    "email_oauth2": {
        "packages": ["msal", "google-api-python-client", "google-auth", "google-auth-oauthlib"],
        "label": "OAuth2 Email Integration",
        "description": "Microsoft 365 and Gmail via OAuth2",
        "size_mb": "~200",
        "feature_flag": "email_oauth2_enabled",
    },
    "nlp_readability": {
        "packages": ["spacy"],
        "label": "NLP Readability Analysis",
        "description": "Passive voice, hedge detection, sentence analysis",
        "size_mb": "~800",
        "feature_flag": "nlp_readability_enabled",
    },
}

admin_packages_bp = Blueprint('admin_packages', __name__, url_prefix='/admin/packages')

@admin_packages_bp.route('/', methods=['GET'])
@login_required
def list_optional_packages():
    """Show installable optional packages."""
    installed = _get_installed_packages()
    features = []
    for key, info in OPTIONAL_PACKAGES.items():
        all_installed = all(pkg.split('[')[0].lower() in installed for pkg in info['packages'])
        features.append({
            'key': key,
            **info,
            'installed': all_installed,
        })
    return render_template('admin/optional_packages.html', features=features)

@admin_packages_bp.route('/<key>/install', methods=['POST'])
@login_required
def install_package(key):
    info = OPTIONAL_PACKAGES.get(key)
    if not info:
        return jsonify({'error': 'Unknown package'}), 404

    result = _install_packages(info['packages'])
    if result['ok']:
        config_manager.set_feature_enabled(info['feature_flag'], True)
    return jsonify(result)

@admin_packages_bp.route('/<key>/uninstall', methods=['POST'])
@login_required
def uninstall_package(key):
    info = OPTIONAL_PACKAGES.get(key)
    if not info:
        return jsonify({'error': 'Unknown package'}), 404

    result = _uninstall_packages(info['packages'])
    if result['ok']:
        config_manager.set_feature_enabled(info['feature_flag'], False)
    return jsonify(result)

def _get_installed_packages():
    result = subprocess.run(['pip', 'list', '--format=json'], capture_output=True, text=True)
    packages = json.loads(result.stdout)
    return {p['name'].lower() for p in packages}

def _install_packages(packages):
    try:
        subprocess.run(
            ['pip', 'install'] + packages + ['-q'],
            capture_output=True, text=True, timeout=600
        )
        return {'ok': True, 'message': 'Packages installed successfully'}
    except subprocess.TimeoutExpired:
        return {'ok': False, 'message': 'Installation timed out'}
    except Exception as e:
        return {'ok': False, 'message': str(e)}
```

### B.3 Graceful optional-feature fallback

Every service that depends on optional packages must check at import time:

```python
# app/services/document_extraction_service.py
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

# Lazy import — only loads when actually needed
_docling_available = False
try:
    from docling.document_converter import DocumentConverter
    _docling_available = True
except ImportError:
    _docling_available = False

def extract(filename, raw_bytes):
    if not _docling_available:
        return {
            'text': '',
            'error': 'Document OCR not installed. Install from Admin > Optional Packages.',
            'status': 'unavailable',
        }
    # ... actual extraction
```

---

## Phase C — Clean Startup Flow

### C.1 Slim create_app()

```python
# app/__init__.py
from flask import Flask
from flask_login import LoginManager

from app.extensions import db, login_manager
from app.config_manager import config_manager
from app.routes._registry import register_blueprints
from app.routes._error_handlers import register_error_handlers
from app.routes._hooks import register_request_hooks
from app.context_processors import register_context_processors


def create_app(config_overrides: dict | None = None) -> Flask:
    """Application factory — keeps setup lean and testable."""
    app = Flask(
        __name__,
        template_folder=str(config_manager.base_path / 'templates'),
        static_folder=str(config_manager.base_path / 'static'),
    )

    # ── Configuration ──────────────────────────────────────────────────────
    app.config['SECRET_KEY'] = config_manager.get('secret_key', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = _get_db_uri()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    if config_overrides:
        app.config.update(config_overrides)

    # ── Extensions ─────────────────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # ── Blueprint registration ─────────────────────────────────────────────
    register_blueprints(app)

    # ── Error handlers ─────────────────────────────────────────────────────
    register_error_handlers(app)

    # ── Request hooks ──────────────────────────────────────────────────────
    register_request_hooks(app)

    # ── Context processors ─────────────────────────────────────────────────
    register_context_processors(app)

    # ── Deferred initialization (inside app_context, after first request) ──
    with app.app_context():
        _initialize_database(app)
        _initialize_services(app)

    return app


def _get_db_uri() -> str:
    """Cross-platform SQLite URI."""
    path = config_manager.db_path.resolve()
    return f"sqlite:///{path.as_posix()}?timeout=5000&check_same_thread=False"


def _initialize_database(app):
    """Create tables and run migrations — only if not TESTING."""
    if app.config.get('TESTING'):
        return

    # 1. Create tables (safe — skips existing)
    db.create_all()

    # 2. Run column migrations (idempotent checks)
    from app._migrations import run_all
    run_all()

    # 3. Seed built-in data
    from app.scripts.seed_roles import seed_builtin_roles
    seed_builtin_roles()


def _initialize_services(app):
    """Initialize background services after DB is ready."""
    if app.config.get('TESTING'):
        return

    # Scheduled reports (non-blocking thread)
    from app.services.scheduled_report_service import initialize_scheduled_report_runtime
    initialize_scheduled_report_runtime(app, start_dispatcher=True)

    # Compliance templates
    from app.models.researcher.phase_b_models import seed_compliance_templates
    seed_compliance_templates()

    # Integration services
    from app.services.integration_service import seed_default_services
    seed_default_services()
```

### C.2 Blueprint registry

```python
# app/routes/_registry.py
"""Central blueprint registration — one place to see all routes."""

def register_blueprints(app):
    # Core
    from app.routes.auth_routes import auth_bp
    from app.routes.setup import setup_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.landing import landing_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(setup_bp)
    app.register_blueprint(dashboard_bp, url_prefix='/researcher')
    app.register_blueprint(landing_bp)

    # Projects (all under /projects/<id>)
    from app.routes.projects import projects_bp
    from app.routes.documents import documents_bp
    from app.routes.search import search_bp
    from app.routes.chat import chat_bp
    # ... register all project blueprints

    # Admin
    from app.routes.admin.admin_users import admin_users_bp
    from app.routes.admin.admin_settings import admin_settings_bp
    # ... register all admin blueprints

    # AI Discovery (Phase 1)
    from app.routes.feed import feed_bp
    from app.routes.reading_list import reading_list_bp
    from app.routes.alerts import alerts_bp
    # ... register

    # Phase 2+ (feature-flagged)
    from app.routes.synthesis import synthesis_bp
    from app.routes.knowledge_map import knowledge_map_bp
    # ... register
```

### C.3 Error handlers

```python
# app/routes/_error_handlers.py
from flask import render_template, jsonify

def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'error': 'Not found'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(403)
    def forbidden(e):
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'error': 'Forbidden'}), 403
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def server_error(e):
        from app.database import db
        db.session.rollback()  # Always rollback on 500
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500
```

---

## Phase D — Configuration Classes

### D.1 Config classes

```python
# app/config/classes.py
import os
from app.config_manager import config_manager

class BaseConfig:
    """Shared config."""
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SECRET_KEY = config_manager.get('secret_key', os.urandom(32).hex())

class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_ECHO = False  # Set True for SQL logging

class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # HTTPS only
    SESSION_COOKIE_HTTPONLY = True

config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
}
```

### D.2 Environment-based selection

```bash
# .env (not in git)
FLASK_ENV=development
FLASK_APP=app:create_app
DATABASE_URL=sqlite:///data/researcher.db
```

```python
# run.py
import os
from app import create_app

env = os.environ.get('FLASK_ENV', 'development')
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=(env == 'development'))
```

---

## Phase E — Recommended Target Structure

```
app/
├── __init__.py                    # create_app() factory (thin)
├── config/
│   ├── __init__.py
│   ├── classes.py                 # Dev/Test/Prod config classes
│   └── defaults.py                # Default feature flags, hooks
├── extensions/                    # Flask extension instances (unbound)
│   ├── __init__.py
│   ├── db.py                      # db = SQLAlchemy(...)
│   ├── login_manager.py
│   └── ...
├── models/                        # (unchanged — models stay here)
│   ├── core.py
│   ├── researcher/
│   └── ...
├── repositories/                  # NEW — data access layer
│   ├── __init__.py
│   ├── base.py                    # BaseRepository ABC
│   ├── project_repository.py
│   ├── document_repository.py
│   ├── user_repository.py
│   └── ...
├── services/                      # Business logic layer
│   ├── __init__.py
│   ├── container.py               # DI container
│   ├── container_setup.py         # Registration
│   ├── base.py                    # BaseService ABC
│   ├── project_service.py
│   ├── user_service.py
│   ├── document_service.py
│   └── [existing services moved gradually]
├── routes/                        # Controllers (thin)
│   ├── __init__.py
│   ├── _registry.py               # Blueprint registration
│   ├── _error_handlers.py         # 404/403/500 handlers
│   ├── _hooks.py                  # before_request hooks
│   ├── admin/
│   ├── auth_routes.py
│   ├── dashboard.py
│   ├── projects.py
│   └── ...
├── context_processors.py          # Template context (t(), features)
├── _migrations/                   # Idempotent column migrations
│   ├── __init__.py
│   └── [migration scripts]
├── scripts/                       # CLI seeders, tools
│   └── seed_roles.py
├── utils/                         # Pure utility functions
│   ├── __init__.py
│   └── time_utils.py
├── integrations/                  # External service connectors
│   ├── search/
│   ├── storage/
│   └── ...
├── core/                          # EventBus, JobQueue, Hooks
│   ├── event_bus.py
│   ├── job_queue.py
│   └── hooks.py
└── config_manager.py              # (unchanged — JSON config singleton)
```

---

## Implementation Order

| Sprint | Focus | Effort | Risk |
|--------|-------|--------|------|
| **1** | Error handlers, config classes, slim create_app() | 2 days | Low (additive) |
| **2** | DI container, BaseRepository, BaseService | 2 days | Low (new code) |
| **3** | Migrate Phase 1 (AI Discovery) to service-repository | 3 days | Medium (existing code) |
| **4** | Optional package admin installer | 2 days | Low (additive) |
| **5** | Migrate Phase 2-4 | 5 days | Medium |
| **6** | Migrate remaining phases | 5 days | Medium |
| **7** | Clean up legacy imports, add tests | 3 days | Low |

**Total: ~22 days** — but can be done incrementally without breaking existing functionality.
