from types import SimpleNamespace

from app.database import db
from app.models.researcher import DocumentAnnotation, ResearcherDocument
from app.models.researcher.researcher_references import DocumentReference, Reference, ReferenceSourceType
from app.services.reference_detail_service import (
    build_project_reference_detail,
    export_project_reference,
    normalize_single_reference_style,
)


def _create_document(project_id: int, *, filename: str, text_content: str) -> ResearcherDocument:
    document = ResearcherDocument(
        project_id=project_id,
        filename=filename,
        file_path=f"/tmp/{filename}",
        mime_type="application/pdf",
        text_content=text_content,
        file_size=2048,
        source_type="pdf",
    )
    db.session.add(document)
    db.session.flush()
    return document


def _create_reference(project_id: int, *, document_id: int | None = None) -> Reference:
    reference = Reference(
        project_id=project_id,
        document_id=document_id,
        title="Grounded review methods",
        source="Journal of Testing",
        publication="Journal of Testing",
        source_type=ReferenceSourceType.JOURNAL.value,
        citation_key="GroundedReviewMethods2026",
        year=2026,
        doi="10.1000/grounded-review-methods",
        url="https://example.com/grounded-review-methods",
    )
    reference.set_authors(["Smith, A.", "Jones, B."])
    reference.set_keywords(["methods", "review"])
    reference.set_metadata_dict({
        "tags": ["chapter 2", "methods"],
        "external_library": {
            "provider": "zotero",
            "item_key": "ITEM-42",
            "library_type": "user",
            "synced_at": "2026-04-12T08:30:00",
            "attachments": [{
                "item_key": "ATT-42",
                "title": "Methods appendix",
                "filename": "appendix.pdf",
                "content_type": "application/pdf",
                "link_mode": "imported_file",
                "item_url": "https://www.zotero.org/users/123/items/ATT-42",
            }],
        },
    })
    db.session.add(reference)
    db.session.flush()
    return reference


def test_build_project_reference_detail_returns_linked_documents_annotations_and_external_metadata(
    app_context,
    test_project,
    test_user,
):
    primary_document = _create_document(
        test_project.id,
        filename="primary-source.pdf",
        text_content="This primary source includes a key methods summary for the literature review.",
    )
    secondary_document = _create_document(
        test_project.id,
        filename="appendix-source.pdf",
        text_content="This appendix source adds supporting context for the same methods section.",
    )
    reference = _create_reference(test_project.id, document_id=primary_document.id)

    db.session.add(
        DocumentReference(
            document_id=secondary_document.id,
            reference_id=reference.id,
            citation_context="Used in the appendix discussion.",
            confidence=0.85,
            citation_type="supporting",
        )
    )
    db.session.add_all([
        DocumentAnnotation(
            document_id=primary_document.id,
            chunk_id="chunk-0",
            start_offset=5,
            end_offset=24,
            note="Primary annotation",
            highlight_color="#fef08a",
            created_by_id=test_user.id,
        ),
        DocumentAnnotation(
            document_id=secondary_document.id,
            chunk_id="chunk-0",
            start_offset=5,
            end_offset=28,
            note="Supporting annotation",
            highlight_color="#fef08a",
            created_by_id=test_user.id,
        ),
    ])
    db.session.commit()

    detail = build_project_reference_detail(test_project, reference.id)

    assert detail is not None
    assert detail["reference"].id == reference.id
    assert detail["authors"] == ["Smith, A.", "Jones, B."]
    assert detail["keywords"] == ["methods", "review"]
    assert detail["tags"] == ["chapter 2", "methods"]
    assert detail["external_library"]["provider"] == "zotero"
    assert detail["attachment_count"] == 1
    assert detail["external_attachments"][0]["filename"] == "appendix.pdf"
    assert detail["external_attachments"][0]["can_import"] is True
    assert detail["annotation_count"] == 2
    assert detail["has_linked_documents"] is True
    assert set(detail["formatted_exports"]) == {"apa", "mla", "chicago", "bibtex", "ris", "json"}

    linked_documents = detail["linked_documents"]
    assert len(linked_documents) == 2

    primary_entry = next(item for item in linked_documents if item["document_id"] == primary_document.id)
    assert primary_entry["is_primary"] is True
    assert primary_entry["open_url"].endswith(f"/documents/{primary_document.id}?source_view=reference&reference_id={reference.id}")
    assert primary_entry["annotation_count"] == 1
    assert primary_entry["recent_annotations"][0]["note"] == "Primary annotation"

    secondary_entry = next(item for item in linked_documents if item["document_id"] == secondary_document.id)
    assert secondary_entry["is_primary"] is False
    assert secondary_entry["citation_context"] == "Used in the appendix discussion."
    assert secondary_entry["citation_type"] == "supporting"
    assert secondary_entry["annotation_count"] == 1
    assert secondary_entry["recent_annotations"][0]["note"] == "Supporting annotation"


def test_build_project_reference_detail_returns_none_for_other_project_scope(app_context, test_project):
    reference = _create_reference(test_project.id)
    db.session.commit()

    detail = build_project_reference_detail(SimpleNamespace(id=test_project.id + 999), reference.id)

    assert detail is None


def test_export_project_reference_returns_expected_single_reference_formats(app_context, test_project):
    reference = _create_reference(test_project.id)
    db.session.commit()

    bibtex_content, bibtex_mimetype, bibtex_filename = export_project_reference(reference, "bibtex")
    ris_content, ris_mimetype, ris_filename = export_project_reference(reference, "ris")
    json_content, json_mimetype, json_filename = export_project_reference(reference, "json")

    assert "@journal{GroundedReviewMethods2026" in bibtex_content
    assert bibtex_mimetype == "application/x-bibtex; charset=utf-8"
    assert bibtex_filename.endswith(".bib")

    assert "TY  - JOUR" in ris_content
    assert ris_mimetype == "application/x-research-info-systems; charset=utf-8"
    assert ris_filename.endswith(".ris")

    assert "\"citation_key\": \"GroundedReviewMethods2026\"" in json_content
    assert json_mimetype == "application/json; charset=utf-8"
    assert json_filename.endswith(".json")

    assert normalize_single_reference_style("unknown-style") == "apa"
