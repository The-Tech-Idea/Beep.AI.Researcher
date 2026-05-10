from types import SimpleNamespace
import hashlib

import pytest

from app.database import db
from app.models.researcher import DocumentIngestionState, ResearcherDocument
from app.models.researcher.researcher_references import DocumentReference, Reference, ReferenceSourceType
from app.services.reference_attachment_ingest_service import import_project_reference_attachment


def _create_reference(project_id: int, *, attachment_link_mode: str = "imported_file") -> Reference:
    reference = Reference(
        project_id=project_id,
        title="Attachment import reference",
        source="Journal of Testing",
        source_type=ReferenceSourceType.JOURNAL.value,
        citation_key="AttachmentImportReference2026",
        year=2026,
    )
    reference.set_metadata_dict({
        "external_library": {
            "provider": "zotero",
            "item_key": "ITEM-42",
            "library_type": "user",
            "attachments": [{
                "item_key": "ATT-42",
                "title": "Methods appendix",
                "filename": "appendix.txt",
                "content_type": "text/plain",
                "link_mode": attachment_link_mode,
                "open_url": "https://www.zotero.org/users/123/items/ATT-42",
                "can_import": attachment_link_mode not in {"linked_url", "linked_file"},
            }],
        }
    })
    db.session.add(reference)
    db.session.commit()
    return reference


def test_import_project_reference_attachment_creates_document_links_reference_and_syncs_text(
    app_context,
    test_project,
    monkeypatch,
):
    reference = _create_reference(test_project.id)
    test_project.collection_id = "library-collection-42"
    db.session.commit()

    saved_payload = {}
    quota_calls = {"checked": None, "recorded": None}
    sync_calls = []

    class FakeBackend:
        def save(self, stream, key):
            saved_payload["key"] = key
            saved_payload["content"] = stream.read()
            return f"stored/{key}"

    class FakeProvider:
        def download_attachment(self, item_key):
            assert item_key == "ATT-42"
            return {
                "content": b"attachment body for grounded review",
                "content_type": "text/plain; charset=utf-8",
                "filename": "grounded-review.txt",
                "download_url": "https://api.zotero.org/downloads/ATT-42",
            }

    monkeypatch.setattr(
        "app.services.reference_attachment_ingest_service.get_project_reference_external_attachments",
        lambda project, ref, user_id: {
            "provider": "zotero",
            "attachments": [{
                "item_key": "ATT-42",
                "title": "Methods appendix",
                "filename": "appendix.txt",
                "content_type": "text/plain",
                "link_mode": "imported_file",
                "open_url": "https://www.zotero.org/users/123/items/ATT-42",
                "can_import": True,
            }],
        },
    )
    monkeypatch.setattr(
        "app.services.reference_attachment_ingest_service.resolve_user_service_connection",
        lambda user_id, service_type: {
            "service": SimpleNamespace(name="Zotero"),
            "connected": True,
            "api_key": "secret",
            "extra_data": {"user_id": "123", "library_type": "user"},
        },
    )
    monkeypatch.setattr(
        "app.services.reference_attachment_ingest_service.build_zotero_provider",
        lambda connection: FakeProvider(),
    )
    monkeypatch.setattr(
        "app.services.reference_attachment_ingest_service.get_storage_backend",
        lambda: FakeBackend(),
    )
    monkeypatch.setattr(
        "app.services.reference_attachment_ingest_service.quota_service.check_quota",
        lambda user_id, upload_size_bytes=0, tenant_id=None: quota_calls.__setitem__("checked", upload_size_bytes),
    )
    monkeypatch.setattr(
        "app.services.reference_attachment_ingest_service.quota_service.record_upload",
        lambda user_id, file_size_bytes=0, tenant_id=None: quota_calls.__setitem__("recorded", file_size_bytes),
    )
    monkeypatch.setattr(
        "app.services.reference_attachment_ingest_service.is_configured",
        lambda: True,
    )
    synced_documents = []
    monkeypatch.setattr(
        "app.services.reference_attachment_ingest_service.sync_document_to_rag",
        lambda project, document, user_id=None: (
            sync_calls.append(document.id),
            synced_documents.append(document),
        ) and (True, {"ok": True}),
    )

    result = import_project_reference_attachment(
        test_project,
        reference,
        attachment_item_key="ATT-42",
        user_id=9,
    )

    assert result["created"] is True
    assert result["linked"] is True
    assert result["message"] == "Attachment added to the project files."
    assert result["rag_sync"]["attempted"] is True
    assert result["rag_sync"]["synced"] is True
    assert quota_calls["checked"] == len(b"attachment body for grounded review")
    assert quota_calls["recorded"] == len(b"attachment body for grounded review")
    assert saved_payload["content"] == b"attachment body for grounded review"

    created_document = result["document"]
    assert created_document.filename == "grounded-review.txt"
    assert created_document.file_path.startswith("stored/")
    assert created_document.text_content == "attachment body for grounded review"
    assert created_document.source_type == "zotero_attachment"
    assert created_document.source_id == "ATT-42"
    assert created_document.source_url == "https://www.zotero.org/users/123/items/ATT-42"
    assert created_document.rag_document_id.startswith("researcher_doc_")
    assert created_document.rag_collection_id == "library-collection-42"
    assert created_document.rag_content_hash == hashlib.sha256(
        b"attachment body for grounded review"
    ).hexdigest()
    assert created_document.rag_sync_status == "indexed"
    assert created_document.rag_sync_message == "File indexed for library search."
    assert created_document.rag_synced_at is not None
    ingestion_state = DocumentIngestionState.query.filter_by(document_id=created_document.id).first()
    assert ingestion_state is not None
    assert ingestion_state.ingestion_status == "synced"
    assert ingestion_state.document_hash == created_document.document_hash
    assert ingestion_state.content_hash == created_document.rag_content_hash
    assert ingestion_state.rag_document_id == created_document.rag_document_id
    assert reference.document_id == created_document.id
    assert sync_calls == [created_document.id]
    assert synced_documents[0].rag_document_id == created_document.rag_document_id

    document_link = DocumentReference.query.filter_by(
        reference_id=reference.id,
        document_id=created_document.id,
    ).first()
    assert document_link is not None
    assert document_link.citation_type == "attachment"
    assert "Methods appendix" in (document_link.citation_context or "")


def test_import_project_reference_attachment_reuses_existing_project_document(
    app_context,
    test_project,
    monkeypatch,
):
    reference = _create_reference(test_project.id)
    existing_document = ResearcherDocument(
        project_id=test_project.id,
        filename="existing-appendix.pdf",
        file_path="stored/existing-appendix.pdf",
        mime_type="application/pdf",
        file_size=2048,
        source_type="zotero_attachment",
        source_id="ATT-42",
        source_url="https://www.zotero.org/users/123/items/ATT-42",
    )
    db.session.add(existing_document)
    db.session.commit()

    monkeypatch.setattr(
        "app.services.reference_attachment_ingest_service.get_project_reference_external_attachments",
        lambda project, ref, user_id: {
            "provider": "zotero",
            "attachments": [{
                "item_key": "ATT-42",
                "title": "Methods appendix",
                "filename": "appendix.pdf",
                "content_type": "application/pdf",
                "link_mode": "imported_file",
                "open_url": "https://www.zotero.org/users/123/items/ATT-42",
                "can_import": True,
            }],
        },
    )
    monkeypatch.setattr(
        "app.services.reference_attachment_ingest_service.resolve_user_service_connection",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("connection lookup should not run")),
    )

    result = import_project_reference_attachment(
        test_project,
        reference,
        attachment_item_key="ATT-42",
        user_id=9,
    )

    assert result["created"] is False
    assert result["linked"] is True
    assert result["document"].id == existing_document.id
    assert result["rag_sync"]["attempted"] is False
    assert reference.document_id == existing_document.id

    links = DocumentReference.query.filter_by(reference_id=reference.id, document_id=existing_document.id).all()
    assert len(links) == 1


def test_import_project_reference_attachment_rejects_non_downloadable_link_modes(
    app_context,
    test_project,
    monkeypatch,
):
    reference = _create_reference(test_project.id, attachment_link_mode="linked_url")

    monkeypatch.setattr(
        "app.services.reference_attachment_ingest_service.get_project_reference_external_attachments",
        lambda project, ref, user_id: {
            "provider": "zotero",
            "attachments": [{
                "item_key": "ATT-42",
                "title": "Linked web page",
                "filename": "",
                "content_type": "text/html",
                "link_mode": "linked_url",
                "open_url": "https://example.com/linked-page",
                "can_import": False,
            }],
        },
    )

    with pytest.raises(ValueError) as excinfo:
        import_project_reference_attachment(
            test_project,
            reference,
            attachment_item_key="ATT-42",
            user_id=9,
        )

    assert "cannot be imported automatically" in str(excinfo.value)
