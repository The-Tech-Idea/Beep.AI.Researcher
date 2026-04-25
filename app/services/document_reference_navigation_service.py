"""Document-to-reference navigation helpers for the viewer surface."""
from __future__ import annotations

from typing import Any

from app.models.researcher import DocumentReference, Reference, ResearchProject, ResearcherDocument


def build_document_reference_navigation(
    project: ResearchProject,
    document: ResearcherDocument,
    *,
    highlighted_reference_id: int | None = None,
) -> dict[str, Any]:
    """Return linked-reference context for one project document."""
    linked_references = _collect_document_references(project, document, highlighted_reference_id=highlighted_reference_id)
    active_reference = next((item for item in linked_references if item["is_active"]), None)
    return {
        "active_reference": active_reference,
        "linked_references": linked_references,
        "reference_count": len(linked_references),
        "has_references": bool(linked_references),
    }


def _collect_document_references(
    project: ResearchProject,
    document: ResearcherDocument,
    *,
    highlighted_reference_id: int | None,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen_reference_ids: set[int] = set()

    primary_references = (
        Reference.query
        .filter_by(project_id=project.id, document_id=document.id)
        .order_by(Reference.updated_at.desc(), Reference.id.desc())
        .all()
    )
    for reference in primary_references:
        seen_reference_ids.add(reference.id)
        entries.append(
            _serialize_document_reference_entry(
                project,
                reference,
                link=None,
                is_primary=True,
                highlighted_reference_id=highlighted_reference_id,
            )
        )

    linked_rows = (
        DocumentReference.query
        .filter_by(document_id=document.id)
        .order_by(DocumentReference.created_at.desc(), DocumentReference.id.desc())
        .all()
    )
    for link in linked_rows:
        reference = link.reference
        if reference is None or reference.project_id != project.id or reference.id in seen_reference_ids:
            continue
        seen_reference_ids.add(reference.id)
        entries.append(
            _serialize_document_reference_entry(
                project,
                reference,
                link=link,
                is_primary=False,
                highlighted_reference_id=highlighted_reference_id,
            )
        )

    return sorted(
        entries,
        key=lambda item: (
            not item["is_active"],
            not item["is_primary"],
            item["title"].casefold(),
        ),
    )


def _serialize_document_reference_entry(
    project: ResearchProject,
    reference: Reference,
    *,
    link: DocumentReference | None,
    is_primary: bool,
    highlighted_reference_id: int | None,
) -> dict[str, Any]:
    authors = reference.get_authors()
    return {
        "id": reference.id,
        "title": reference.title,
        "authors_text": ", ".join(authors[:3]),
        "year": reference.year,
        "doi": reference.doi,
        "source_label": reference.publication or reference.source or "",
        "detail_url": f"/researcher/projects/{project.id}/references/{reference.id}",
        "report_url": f"/researcher/projects/{project.id}/report?ref_id={reference.id}",
        "open_doi_url": f"https://doi.org/{reference.doi}" if reference.doi else None,
        "citation_context": link.citation_context if link is not None else None,
        "citation_type": link.citation_type if link is not None else None,
        "is_primary": is_primary,
        "is_active": reference.id == highlighted_reference_id,
    }
