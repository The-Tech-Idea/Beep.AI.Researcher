"""Pytest fixtures."""
import os
import asyncio
import inspect
import uuid
import builtins
from importlib.util import find_spec

import pytest
from types import SimpleNamespace
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Guard: only register the SQLite pragma listener once across all fixture calls
_sqlite_pragma_registered = False

_TESTS_DIR = os.path.dirname(__file__)
_PROJECT_ROOT = os.path.abspath(os.path.join(_TESTS_DIR, '..'))
_TEST_DB_PATH = os.path.join(_PROJECT_ROOT, 'pytest_test.db')
_HAS_PYTEST_ASYNCIO = find_spec('pytest_asyncio') is not None

# Use in-memory DB before importing app
os.environ['DATABASE_URL'] = f"sqlite:///{_TEST_DB_PATH.replace(os.sep, '/')}"
os.environ['SKIP_SEED_ROLES'] = '1'
os.environ['TESTING'] = '1'

# Configure pytest-asyncio when available so synchronous suites can still run
# in lightweight environments that only have pytest installed.
if _HAS_PYTEST_ASYNCIO:
    pytestmark = pytest.mark.asyncio
    pytest_plugins = ('pytest_asyncio',)


def pytest_addoption(parser):
    """Register fallback asyncio ini options when pytest-asyncio is unavailable."""
    if _HAS_PYTEST_ASYNCIO:
        return

    parser.addini('asyncio_mode', 'Fallback pytest-asyncio mode placeholder', default='auto')
    parser.addini(
        'asyncio_default_fixture_loop_scope',
        'Fallback pytest-asyncio loop scope placeholder',
        default='function',
    )


def pytest_configure(config):
    """Configure pytest with asyncio support."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as a coroutine that should be executed by pytest asyncio"
    )


def pytest_collection_modifyitems(config, items):
    """Skip async-only tests when pytest-asyncio is unavailable."""
    if _HAS_PYTEST_ASYNCIO:
        return

    skip_async = pytest.mark.skip(reason="pytest_asyncio is not installed in this environment")
    for item in items:
        item_obj = getattr(item, 'obj', None)
        if (
            inspect.iscoroutinefunction(item_obj)
            or item.get_closest_marker('asyncio') is not None
            or 'async_client' in getattr(item, 'fixturenames', ())
        ):
            item.add_marker(skip_async)


@pytest.fixture(scope='session', autouse=True)
def clean_test_db_session():
    """Delete the test DB file at the start of the session so create_all is always clean.
    On Windows the file may be locked by a previous process; skip deletion gracefully in that case."""
    if os.path.exists(_TEST_DB_PATH):
        try:
            os.remove(_TEST_DB_PATH)
        except PermissionError:
            pass  # File still locked by a prior process; create_all will reuse it safely.
    yield


@pytest.fixture
def app():
    from app import create_app
    app = create_app()
    
    with app.app_context():
        # Import all models to ensure they're registered with SQLAlchemy
        from app.models.core import User, Role, AuditLog
        from app.models.tenant import Tenant, TenantMember
        from app.models.rbac import RBACRole, UserRole, DocumentAccess, UserGroup
        from app.models.researcher import (
            ResearchProject, ProjectMember, ProjectComment, ResearcherDocument, Code, CodedReference,
            DocumentAnnotation, ChatSession, ChatMessage,
            ResearcherDataSource, SavedChart, ScheduledReport,
            ExtractionSchema, ExtractionResult,
            Flashcard, Quiz, QuizQuestion,
            ResearchTask, Reference, TaskNotification,
            LibrarySource, SourceConnection, SourceImportLog,
            SearchCache, SearchIndex,
        )
        from app.models.researcher.phase_a_models import (
            ResearchBrief, EvidenceItem, Claim, ClaimEvidence,
            ReviewStep, SourceProvenance,
        )
        from app.models.researcher.phase_1_models import (
            ResearchInterestProfile, FeedRecommendation, ReadingListItem, PaperAlert,
        )
        from app.models.researcher.phase_b_models import (
            RetentionPolicy, CompliancePolicyTemplate,
        )
        # Import plugin models to ensure they're registered
        from app.models.researcher.plugins import (
            Plugin, PluginConfiguration, PluginHookRegistration, PluginExecutionLog
        )
        from app.models.researcher.plugin_permissions import (
            PluginPermission, PluginRoleAssignment, PluginAudit
        )
        from app.models.researcher.extraction_plugins import (
            ExtractionField, ExtractedFieldValue, ExtractionValidationResult
        )
        from app.models.researcher.researcher_references import (
            DocumentReference
        )
        from app.models.researcher.sector_models import (
            Hypothesis, HypothesisEvidence, PlagiarismCheck,
            EvidenceGrade, ClauseTemplate, CitationValidation,
        )
        from app.models.researcher.hallucination_audit import HallucinationAuditLog
        # Phase 8/9 models — must be imported so create_all includes all new columns
        try:
            from app.models.researcher.storage_quota import PlanTier, TenantQuota, UserStorageStats
        except Exception:
            pass
        try:
            from app.models.user_management import UserInvite, PasswordHistory, UserSession
        except Exception:
            pass
        try:
            from app.models.integrations_registry import GlobalIntegrationService, UserIntegrationCredential
        except Exception:
            pass

        # Disable foreign key constraints for testing (register only once)
        global _sqlite_pragma_registered
        if not _sqlite_pragma_registered:
            @event.listens_for(Engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=OFF")
                cursor.close()
            _sqlite_pragma_registered = True
        
        from app.database import db
        # Recreate the schema from a clean test database file.
        db.metadata.create_all(bind=db.engine, checkfirst=True)

    yield app

    # Dispose the engine so the SQLite file is fully released (important on Windows)
    with app.app_context():
        from app.database import db
        db.engine.dispose()


@pytest.fixture(autouse=True)
def ensure_app_context(app):
    """Ensure all tests have an active app context (some tests use db without requesting app fixture)."""
    with app.app_context():
        from app.models.rbac import UserRole
        builtins.UserRole = UserRole
        yield


@pytest.fixture(autouse=True)
def cleanup_db(app):
    """Auto-cleanup database after each test."""
    yield
    
    with app.app_context():
        from app.database import db
        from sqlalchemy import text, inspect
        
        try:
            # Disable foreign key constraints
            db.session.execute(text('PRAGMA foreign_keys=OFF'))
            
            # Get all tables and delete in reverse order
            inspector = inspect(db.engine)
            all_tables = inspector.get_table_names()
            for table_name in reversed(all_tables):
                try:
                    db.session.execute(text(f'DELETE FROM "{table_name}"'))
                except Exception:
                    pass
            
            db.session.commit()
            
            # Re-enable foreign key constraints
            db.session.execute(text('PRAGMA foreign_keys=ON'))
            db.session.commit()
        except Exception:
            db.session.rollback()
        finally:
            db.session.remove()


@pytest.fixture
def app_context(app):
    """Provide application context for tests."""
    with app.app_context():
        from app.database import db
        from sqlalchemy import text, inspect
        
        # Drop references table if it exists to recreate with new schema
        try:
            inspector = inspect(db.engine)
            if 'references' in inspector.get_table_names():
                db.session.execute(text('DROP TABLE IF EXISTS references'))
                db.session.commit()
        except Exception:
            pass
        
        # Create all tables with full schema (checkfirst avoids "table already exists")
        db.metadata.create_all(db.engine, checkfirst=True)
        
        yield app
        
        # Cleanup after each test - clear all data
        try:
            # Get inspector
            inspector = inspect(db.engine)
            
            # Disable foreign key constraints
            db.session.execute(text('PRAGMA foreign_keys=OFF'))
            
            # Get all tables and delete in reverse order
            all_tables = inspector.get_table_names()
            for table_name in reversed(all_tables):
                try:
                    db.session.execute(text(f'DELETE FROM "{table_name}"'))
                except Exception:
                    pass
            
            db.session.commit()
            
            # Re-enable foreign key constraints
            db.session.execute(text('PRAGMA foreign_keys=ON'))
            db.session.commit()
        except Exception:
            db.session.rollback()
        finally:
            db.session.remove()


@pytest.fixture
def client(app):
    app.config['TESTING'] = True
    with app.app_context():
        from app.database import db
        from app.models.core import User
        from app.models.rbac import RBACRole, UserRole, Permission

        user = User(username=f"client_{uuid.uuid4().hex[:8]}", email=f"client_{uuid.uuid4().hex[:8]}@example.com")
        db.session.add(user)
        db.session.flush()

        admin_role = RBACRole(
            name=f"test_admin_{uuid.uuid4().hex[:8]}",
            permissions=[Permission.ALL],
            is_builtin=False
        )
        db.session.add(admin_role)
        db.session.flush()

        db.session.add(UserRole(user_id=str(user.id), role_id=admin_role.id, scope='global'))
        user_id = user.id
        db.session.commit()

        test_client = app.test_client()
        with test_client.session_transaction() as sess:
            sess['_user_id'] = str(user_id)
            sess['_fresh'] = True
            sess['user_id'] = user_id

        yield test_client


if _HAS_PYTEST_ASYNCIO:
    @pytest.fixture
    async def async_client(app):
        """Async test client fixture."""
        app.config['TESTING'] = True
        with app.app_context():
            yield app.test_client()
else:
    @pytest.fixture
    def async_client(app):
        """Fallback client fixture when pytest-asyncio is unavailable."""
        app.config['TESTING'] = True
        with app.app_context():
            yield app.test_client()


@pytest.fixture
def db():
    """Provide database instance."""
    from app.database import db as database
    return SimpleNamespace(
        db=database.session,
        session=database.session
    )


@pytest.fixture
def mock_user():
    """Simple mock user payload for service tests."""
    return {'id': 1, 'username': 'mock_user'}

@pytest.fixture
def test_user(app_context, request):
    """Create a test user with unique username per test."""
    from app.database import db
    from app.models.core import User
    import time
    
    # Create unique username to avoid UNIQUE constraint violations
    unique_id = str(int(time.time() * 1000000) % 1000000)
    user = User(
        username=f"testuser_{unique_id}", 
        email=f"test_{unique_id}@example.com", 
        password_hash="hashed_password"
    )
    db.session.add(user)
    db.session.commit()
    return SimpleNamespace(id=user.id, username=user.username, email=user.email)


@pytest.fixture
def test_project(app_context, test_user):
    """Create a test research project."""
    from app.database import db
    from app.models.researcher import ResearchProject
    
    project = ResearchProject(
        name="Test Research Project",
        description="A test project for unit tests",
        owner_id=test_user.id,
        status="active"
    )
    db.session.add(project)
    db.session.commit()
    return SimpleNamespace(id=project.id, owner_id=project.owner_id, name=project.name)


@pytest.fixture
def test_document(app_context, test_project):
    """Create a test research document."""
    from app.database import db
    from app.models.researcher import ResearcherDocument
    
    document = ResearcherDocument(
        project_id=test_project.id,
        filename="test_document.pdf",
        file_path="/tmp/test_document.pdf",
        mime_type="application/pdf",
        text_content="This is a test document with content.",
        file_size=1024,
        source_type="test"
    )
    db.session.add(document)
    db.session.commit()
    return SimpleNamespace(id=document.id, project_id=document.project_id, filename=document.filename)
