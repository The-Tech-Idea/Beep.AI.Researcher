from app.database import db
from app.models.core import AuditLog
from app.models.researcher import ResearcherDocument
from app.services.document_manager_service import document_manager_service


class FakeDeleteBackend:
    def __init__(self):
        self.deleted = []

    def delete(self, key):
        self.deleted.append(key)


def test_delete_document_removes_backend_object_updates_quota_and_audits(
    app_context,
    test_project,
    monkeypatch,
):
    backend = FakeDeleteBackend()
    quota_calls = []
    doc = ResearcherDocument(
        project_id=test_project.id,
        filename="delete-me.txt",
        file_path="stored/delete-me.txt",
        mime_type="text/plain",
        text_content="delete me",
        file_size=321,
        status="ready",
    )
    db.session.add(doc)
    db.session.commit()
    doc_id = doc.id

    monkeypatch.setattr("app.services.storage.get_storage_backend", lambda: backend)
    monkeypatch.setattr("app.services.beep_ai_client.is_configured", lambda: False)
    monkeypatch.setattr(
        "app.services.quota_service.quota_service.record_delete",
        lambda user_id, file_size_bytes, tenant_id=None: quota_calls.append(
            (user_id, file_size_bytes, tenant_id)
        ),
    )

    filename = document_manager_service.delete_document(doc_id, actor_user_id=99)

    audit = AuditLog.query.filter_by(action="admin.documents.delete", resource_id=str(doc_id)).first()
    assert filename == "delete-me.txt"
    assert backend.deleted == ["stored/delete-me.txt"]
    assert db.session.get(ResearcherDocument, doc_id) is None
    assert quota_calls == [(test_project.owner_id, 321, None)]
    assert audit is not None
    assert audit.user_id == 99


def test_archive_and_restore_document_update_lifecycle_and_audit(app_context, test_project, monkeypatch):
    doc = ResearcherDocument(
        project_id=test_project.id,
        filename="archive-me.txt",
        file_path="stored/archive-me.txt",
        mime_type="text/plain",
        text_content="archive me",
        file_size=123,
        status="ready",
        rag_collection_id="collection-1",
        rag_document_id="rag-doc-1",
        rag_sync_status="indexed",
    )
    db.session.add(doc)
    db.session.commit()
    doc_id = doc.id
    rag_deletes = []

    monkeypatch.setattr("app.services.beep_ai_client.is_configured", lambda: True)
    monkeypatch.setattr(
        "app.services.beep_ai_client.remove_document_from_project_rag",
        lambda project, document_ids, user_id=None: rag_deletes.append(document_ids) or (True, {}),
    )

    filename = document_manager_service.archive_document(doc_id, actor_user_id=99)
    archived = db.session.get(ResearcherDocument, doc_id)
    archive_audit = AuditLog.query.filter_by(action="admin.documents.archive", resource_id=str(doc_id)).first()
    assert filename == "archive-me.txt"
    assert archived.status == "archived"
    assert archived.archived_at is not None
    assert archived.rag_sync_status == "archived"
    assert rag_deletes == [["rag-doc-1"]]
    assert archive_audit is not None

    filename = document_manager_service.restore_document(doc_id, actor_user_id=99)
    restored = db.session.get(ResearcherDocument, doc_id)
    restore_audit = AuditLog.query.filter_by(action="admin.documents.restore", resource_id=str(doc_id)).first()
    assert filename == "archive-me.txt"
    assert restored.status == "ready"
    assert restored.archived_at is None
    assert restored.rag_sync_status == "not_indexed"
    assert restore_audit is not None
