from app.database import db
from app.models.researcher import ResearcherDocument
from app.models.researcher.researcher_references import DocumentReference, Reference, ReferenceSourceType
from app.services.document_reference_navigation_service import build_document_reference_navigation


def _create_document(project_id: int, filename: str) -> ResearcherDocument:
    document = ResearcherDocument(
        project_id=project_id,
        filename=filename,
        file_path=f"/tmp/{filename}",
        mime_type="application/pdf",
        text_content="Supportive project text.",
        file_size=1024,
        source_type="pdf",
    )
    db.session.add(document)
    db.session.flush()
    return document


def _create_reference(project_id: int, title: str, *, document_id: int | None = None) -> Reference:
    reference = Reference(
        project_id=project_id,
        document_id=document_id,
        title=title,
        source="Journal of Testing",
        source_type=ReferenceSourceType.JOURNAL.value,
        citation_key=title.replace(" ", "") + "2026",
        year=2026,
        doi=f"10.1000/{title.replace(' ', '-').lower()}",
    )
    reference.set_authors(["Smith, A."])
    db.session.add(reference)
    db.session.flush()
    return reference


def test_build_document_reference_navigation_includes_primary_and_linked_references(
    app_context,
    test_project,
):
    document = _create_document(test_project.id, "review.pdf")
    primary_reference = _create_reference(test_project.id, "Primary source", document_id=document.id)
    linked_reference = _create_reference(test_project.id, "Secondary source")
    db.session.add(
        DocumentReference(
            document_id=document.id,
            reference_id=linked_reference.id,
            citation_context="Used in the discussion section.",
            citation_type="supporting",
            confidence=0.82,
        )
    )
    db.session.commit()

    navigation = build_document_reference_navigation(
        test_project,
        document,
        highlighted_reference_id=linked_reference.id,
    )

    assert navigation["has_references"] is True
    assert navigation["reference_count"] == 2
    assert navigation["active_reference"]["id"] == linked_reference.id
    assert navigation["linked_references"][0]["id"] == linked_reference.id

    primary_entry = next(item for item in navigation["linked_references"] if item["id"] == primary_reference.id)
    assert primary_entry["is_primary"] is True
    assert primary_entry["detail_url"].endswith(f"/references/{primary_reference.id}")
    assert primary_entry["open_doi_url"].endswith(primary_reference.doi)

    linked_entry = next(item for item in navigation["linked_references"] if item["id"] == linked_reference.id)
    assert linked_entry["citation_context"] == "Used in the discussion section."
    assert linked_entry["citation_type"] == "supporting"
    assert linked_entry["is_active"] is True
