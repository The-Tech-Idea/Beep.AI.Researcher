from types import SimpleNamespace

from app.database import db
from app.models.researcher.researcher_references import Reference, ReferenceSourceType
from app.services.reference_external_attachment_service import (
    get_cached_reference_external_attachments,
    get_project_reference_external_attachments,
)


def _create_reference(project_id: int, *, attachments=None) -> Reference:
    reference = Reference(
        project_id=project_id,
        title="Attachment reference",
        source="Journal of Testing",
        source_type=ReferenceSourceType.JOURNAL.value,
        citation_key="AttachmentReference2026",
        year=2026,
    )
    reference.set_metadata_dict({
        "external_library": {
            "provider": "zotero",
            "item_key": "ITEM-42",
            "library_type": "user",
            "attachments": attachments or [],
        }
    })
    db.session.add(reference)
    db.session.commit()
    return reference


def test_get_project_reference_external_attachments_refreshes_live_zotero_metadata(
    app_context,
    test_project,
    monkeypatch,
):
    reference = _create_reference(test_project.id)

    class FakeProvider:
        def list_item_attachments(self, item_key):
            assert item_key == "ITEM-42"
            return [{
                "item_key": "ATT-1",
                "title": "Methods appendix",
                "filename": "appendix.pdf",
                "content_type": "application/pdf",
                "link_mode": "linked_url",
                "item_url": "https://www.zotero.org/users/123/items/ATT-1",
            }]

    monkeypatch.setattr(
        "app.services.reference_external_attachment_service.resolve_user_service_connection",
        lambda user_id, service_type: {
            "service": SimpleNamespace(name="Zotero"),
            "connected": True,
            "api_key": "secret",
            "extra_data": {"user_id": "123", "library_type": "user"},
            "source": "user",
            "display_name": "Zotero user 123",
        },
    )
    monkeypatch.setattr(
        "app.services.reference_external_attachment_service.build_zotero_provider",
        lambda connection: FakeProvider(),
    )

    result = get_project_reference_external_attachments(test_project, reference, user_id=7)

    assert result["provider"] == "zotero"
    assert result["refreshed"] is True
    assert result["cached"] is False
    assert result["attachments"][0]["title"] == "Methods appendix"
    assert result["attachments"][0]["can_import"] is False
    db.session.refresh(reference)
    assert get_cached_reference_external_attachments(reference)[0]["filename"] == "appendix.pdf"


def test_get_project_reference_external_attachments_uses_cached_metadata_without_connection(
    app_context,
    test_project,
    monkeypatch,
):
    reference = _create_reference(
        test_project.id,
        attachments=[{
            "item_key": "ATT-2",
            "title": "Saved attachment",
            "filename": "saved.pdf",
            "content_type": "application/pdf",
            "link_mode": "linked_file",
            "item_url": "https://www.zotero.org/users/123/items/ATT-2",
        }],
    )

    monkeypatch.setattr(
        "app.services.reference_external_attachment_service.resolve_user_service_connection",
        lambda user_id, service_type: {
            "service": SimpleNamespace(name="Zotero"),
            "connected": False,
            "api_key": None,
            "extra_data": {"user_id": "123", "library_type": "user"},
            "source": "user",
            "display_name": "Zotero user 123",
        },
    )

    result = get_project_reference_external_attachments(test_project, reference, user_id=7)

    assert result["provider"] == "zotero"
    assert result["cached"] is True
    assert result["refreshed"] is False
    assert result["attachments"][0]["title"] == "Saved attachment"
    assert result["attachments"][0]["can_import"] is False
