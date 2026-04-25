from app.database import db
from app.models.researcher import ResearcherDocument
from app.services.document_annotation_service import (
    DocumentAnnotationValidationError,
    create_document_annotation,
    list_document_annotations,
)


def test_create_document_annotation_persists_preview_and_creator(app_context, test_document, test_user):
    document = db.session.get(ResearcherDocument, test_document.id)

    annotation = create_document_annotation(
        document,
        created_by_id=test_user.id,
        chunk_id=None,
        start_offset=10,
        end_offset=24,
        note="Important supporting sentence",
        highlight_color="#ABCDEF",
    )

    assert annotation["created_by_id"] == test_user.id
    assert annotation["highlight_color"] == "#abcdef"
    assert annotation["note"] == "Important supporting sentence"
    assert annotation["selected_text"] == "test document"
    assert annotation["context_preview"]

    listed = list_document_annotations(document)
    assert len(listed) == 1
    assert listed[0]["id"] == annotation["id"]


def test_create_document_annotation_rejects_invalid_offsets(app_context, test_document, test_user):
    document = db.session.get(ResearcherDocument, test_document.id)

    try:
        create_document_annotation(
            document,
            created_by_id=test_user.id,
            chunk_id="chunk-0",
            start_offset=25,
            end_offset=10,
            note="Broken range",
            highlight_color="#fef08a",
        )
    except DocumentAnnotationValidationError as exc:
        assert "greater than start_offset" in str(exc)
    else:
        raise AssertionError("Expected annotation validation error for invalid offsets")
