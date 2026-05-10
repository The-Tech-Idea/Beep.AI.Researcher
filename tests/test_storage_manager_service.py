from app.database import db
from app.models.core import AuditLog
from app.models.researcher import ResearcherDocument
from app.services.storage.storage_manager_service import storage_manager_service


class FakeStorageBackend:
    backend_name = "fake"

    def __init__(self, *, exists=True, size=256):
        self._exists = exists
        self._size = size

    def exists(self, key):
        return self._exists

    def file_size(self, key):
        return self._size


def _create_document(project_id: int, *, file_path="stored/path/doc.txt", file_size=128):
    doc = ResearcherDocument(
        project_id=project_id,
        filename="doc.txt",
        file_path=file_path,
        mime_type="text/plain",
        file_size=file_size,
        text_content="hello",
        status="ready",
    )
    db.session.add(doc)
    db.session.commit()
    return doc


def test_safe_storage_reference_hides_path():
    reference = storage_manager_service.safe_storage_reference("tenant/a/b/private-name.pdf")

    assert reference["name"] == "private-name.pdf"
    assert reference["sha256"]
    assert "tenant/a/b" not in reference["name"]


def test_consistency_scan_reports_size_mismatch_without_raw_display_reference(app_context, test_project, monkeypatch):
    doc = _create_document(test_project.id, file_size=128)
    monkeypatch.setattr(
        "app.services.storage.get_storage_backend",
        lambda: FakeStorageBackend(exists=True, size=512),
    )

    issues = storage_manager_service.consistency_scan(limit=10)

    issue = next(item for item in issues if item.document_id == doc.id)
    assert issue.issue_type == "size_mismatch"
    assert issue.storage_key == "stored/path/doc.txt"
    assert issue.storage_reference["name"] == "doc.txt"
    assert issue.actual_size == 512


def test_consistency_scan_reports_missing_object(app_context, test_project, monkeypatch):
    doc = _create_document(test_project.id, file_size=128)
    monkeypatch.setattr(
        "app.services.storage.get_storage_backend",
        lambda: FakeStorageBackend(exists=False, size=0),
    )

    issues = storage_manager_service.consistency_scan(limit=10)

    issue = next(item for item in issues if item.document_id == doc.id)
    assert issue.issue_type == "missing_object"
    assert issue.storage_reference["name"] == "doc.txt"


def test_repair_document_size_updates_db_and_audits(app_context, test_project, monkeypatch):
    doc = _create_document(test_project.id, file_size=128)
    monkeypatch.setattr(
        "app.services.storage.get_storage_backend",
        lambda: FakeStorageBackend(exists=True, size=512),
    )

    actual_size = storage_manager_service.repair_document_size(doc.id, actor_user_id=7)

    refreshed = db.session.get(ResearcherDocument, doc.id)
    audit = AuditLog.query.filter_by(action="admin.storage.repair_size", resource_id=str(doc.id)).first()
    assert actual_size == 512
    assert refreshed.file_size == 512
    assert audit is not None
    assert audit.user_id == 7
