"""Tests for the project-scoped Zotero citation sync service."""
import json
import uuid

from app.database import db
from app.integrations.citation.base_citation import CitationItem
from app.models.core import Role, User
from app.models.integrations_registry import GlobalIntegrationService, UserIntegrationCredential
from app.models.researcher.researcher_references import Reference
from app.services.integration_service import encrypt_secret
from app.services.zotero_library_sync_service import (
    get_project_zotero_sync_status,
    sync_project_references_from_zotero,
)


class FakeZoteroSyncProvider:
    def __init__(self):
        self.credentials = None

    def connect(self, credentials):
        self.credentials = credentials
        return True

    def list_collections(self):
        return [
            {"key": "methods", "name": "Methods", "item_count": 1},
            {"key": "reviews", "name": "Reviews", "item_count": 2},
        ]

    def list_items(self, collection_id=None, limit=100):
        return (
            [
                CitationItem(
                    id="ZOT-001",
                    title="Updated Methods Review",
                    authors=["Smith, J."],
                    year="2024",
                    doi="10.1000/example",
                    item_type="journalArticle",
                    journal="Methods Journal",
                    tags=["methods", "review"],
                    collections=["methods"],
                    metadata={"zotero_version": 4, "date_modified": "2026-04-11T08:00:00Z"},
                ),
                CitationItem(
                    id="ZOT-002",
                    title="New Zotero Import",
                    authors=["Jones, A."],
                    year="2025",
                    item_type="book",
                    journal="Scholarly Press",
                    tags=["books"],
                    collections=["reviews"],
                    metadata={"zotero_version": 2, "date_modified": "2026-04-11T08:05:00Z"},
                ),
            ],
            4,
        )


def _create_user():
    role = Role.query.filter_by(name="User").first()
    if role is None:
        role = Role(name="User")
        db.session.add(role)
        db.session.flush()

    suffix = uuid.uuid4().hex[:8]
    user = User(
        username=f"zotero_sync_user_{suffix}",
        email=f"zotero_sync_user_{suffix}@example.com",
        role_id=role.id,
        is_active=True,
    )
    user.set_password("Passw0rd!")
    db.session.add(user)
    db.session.commit()
    return user


def test_get_project_zotero_sync_status_reports_ready_connection(app_context, test_project, monkeypatch):
    monkeypatch.setattr(
        "app.services.zotero_library_sync_service.build_zotero_provider",
        lambda connection: FakeZoteroSyncProvider(),
    )

    user = _create_user()
    service = GlobalIntegrationService(
        service_type="zotero",
        name="Zotero",
        scope="dual",
        is_enabled=True,
        allow_user_override=True,
    )
    db.session.add(service)
    db.session.flush()
    db.session.add(
        UserIntegrationCredential(
            user_id=user.id,
            service_id=service.id,
            api_key_encrypted=encrypt_secret("secret-key"),
            is_active=True,
            display_name="Zotero user 12345",
            extra_data=json.dumps({"user_id": "12345", "library_type": "user"}),
        )
    )
    db.session.commit()

    status = get_project_zotero_sync_status(test_project, user_id=user.id)

    assert status["available"] is True
    assert status["connected"] is True
    assert status["ready"] is True
    assert status["display_name"] == "Zotero user 12345"
    assert [entry["key"] for entry in status["collections"]] == ["methods", "reviews"]


def test_sync_project_references_from_zotero_creates_and_updates_references(app_context, test_project, monkeypatch):
    monkeypatch.setattr(
        "app.services.zotero_library_sync_service.build_zotero_provider",
        lambda connection: FakeZoteroSyncProvider(),
    )

    user = _create_user()
    service = GlobalIntegrationService(
        service_type="zotero",
        name="Zotero",
        scope="dual",
        is_enabled=True,
        allow_user_override=True,
    )
    db.session.add(service)
    db.session.flush()
    db.session.add(
        UserIntegrationCredential(
            user_id=user.id,
            service_id=service.id,
            api_key_encrypted=encrypt_secret("secret-key"),
            is_active=True,
            extra_data=json.dumps({"user_id": "12345", "library_type": "user"}),
        )
    )

    existing_reference = Reference(
        project_id=test_project.id,
        title="Original Methods Review",
        citation_key="OriginalMethodsReview",
        doi="10.1000/example",
        notes="Local note",
    )
    existing_reference.set_metadata_dict({"tags": ["local-note"]})
    db.session.add(existing_reference)
    db.session.commit()

    result = sync_project_references_from_zotero(test_project, user_id=user.id)

    assert result["ok"] is True
    assert result["created"] == 1
    assert result["updated"] == 1
    assert result["imported"] == 2

    updated_reference = db.session.get(Reference, existing_reference.id)
    assert updated_reference.title == "Updated Methods Review"
    assert updated_reference.get_authors() == ["Smith, J."]
    assert set(updated_reference.get_metadata_dict()["tags"]) == {"local-note", "methods", "review"}
    assert updated_reference.get_metadata_dict()["external_library"]["provider"] == "zotero"
    assert updated_reference.get_metadata_dict()["external_library"]["item_key"] == "ZOT-001"

    created_reference = Reference.query.filter_by(project_id=test_project.id, title="New Zotero Import").first()
    assert created_reference is not None
    assert created_reference.source_type == "book"
    assert created_reference.get_metadata_dict()["external_library"]["item_key"] == "ZOT-002"
