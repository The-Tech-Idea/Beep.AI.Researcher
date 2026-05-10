import uuid
from pathlib import Path

import pytest

from app.database import db
from app.models.core import Role, User


RESEARCHER_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def admin_client(app):
    with app.app_context():
        role = Role.query.filter_by(name="Admin").first()
        if role is None:
            role = Role(name="Admin")
            db.session.add(role)
            db.session.flush()
        user = User(
            username=f"doc_admin_{uuid.uuid4().hex[:8]}",
            email=f"doc_admin_{uuid.uuid4().hex[:8]}@example.com",
            role_id=role.id,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True
            sess["user_id"] = user.id
        yield client


@pytest.fixture
def non_admin_client(app):
    with app.app_context():
        user = User(
            username=f"doc_user_{uuid.uuid4().hex[:8]}",
            email=f"doc_user_{uuid.uuid4().hex[:8]}@example.com",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        client = app.test_client()
        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True
            sess["user_id"] = user.id
        yield client


def test_admin_document_manager_pages_load(admin_client):
    for path in (
        "/admin/documents",
        "/admin/quota",
        "/admin/storage",
        "/admin/document-manager/jobs",
    ):
        response = admin_client.get(path)
        assert response.status_code == 200, path


def test_non_admin_user_cannot_access_document_manager_pages(non_admin_client):
    response = non_admin_client.get("/admin/documents", follow_redirects=False)

    assert response.status_code in {302, 303}
    assert "/admin/documents" not in response.headers.get("Location", "")


def test_admin_document_manager_routes_use_session_admin_auth_and_not_token_api():
    for relative_path in (
        "app/routes/admin/admin_documents.py",
        "app/routes/admin/admin_quotas.py",
        "app/routes/admin/admin_storage.py",
    ):
        source = (RESEARCHER_ROOT / relative_path).read_text(encoding="utf-8")
        assert "@login_required" in source
        assert "@admin_required" in source
        assert "application_token" not in source
        assert "ai_middleware" not in source
