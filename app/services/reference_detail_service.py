"""Project reference detail and single-reference export helpers."""
from __future__ import annotations

import json
from io import BytesIO
from typing import Any

from app.models.researcher import DocumentAnnotation, DocumentReference, Reference, ResearchProject
from app.services.citation_library_service import get_reference_tags
from app.services.document_annotation_service import serialize_document_annotation
from app.services.reference_external_attachment_service import get_cached_reference_external_attachments


SINGLE_REFERENCE_EXPORT_STYLES = ("apa", "mla", "chicago", "bibtex", "ris", "json")
RECENT_ANNOTATION_LIMIT = 5


def build_project_reference_detail(project: ResearchProject, reference_id: int) -> dict[str, Any] | None:
    """Return project-scoped reference detail context for the detail page."""
    reference = (
        Reference.query
        .filter_by(project_id=project.id, id=reference_id)
        .first()
    )
    if reference is None:
        return None

    metadata = reference.get_metadata_dict()
    external_library = metadata.get("external_library") if isinstance(metadata.get("external_library"), dict) else None
    external_attachments = get_cached_reference_external_attachments(reference)
    linked_documents = _build_linked_document_details(reference)
    return {
        "reference": reference,
        "authors": reference.get_authors(),
        "keywords": reference.get_keywords(),
        "tags": get_reference_tags(reference),
        "external_library": external_library,
        "external_attachments": external_attachments,
        "attachment_count": len(external_attachments),
        "formatted_exports": {
            "apa": reference.to_apa(),
            "mla": reference.to_mla(),
            "chicago": reference.to_chicago(),
            "bibtex": reference.to_bibtex(),
            "ris": reference.to_ris(),
            "json": json.dumps(reference.to_json(), indent=2, ensure_ascii=False),
        },
        "linked_documents": linked_documents,
        "annotation_count": sum(item["annotation_count"] for item in linked_documents),
        "has_linked_documents": bool(linked_documents),
    }


def export_project_reference(reference: Reference, style: str) -> tuple[str, str, str]:
    """Return single-reference export content, mimetype, and filename."""
    normalized_style = normalize_single_reference_style(style)
    filename_base = _slugify(reference.citation_key or reference.title or f"reference-{reference.id}")

    if normalized_style == "apa":
        return reference.to_apa() + "\n", "text/plain; charset=utf-8", f"{filename_base}.txt"
    if normalized_style == "mla":
        return reference.to_mla() + "\n", "text/plain; charset=utf-8", f"{filename_base}.txt"
    if normalized_style == "chicago":
        return reference.to_chicago() + "\n", "text/plain; charset=utf-8", f"{filename_base}.txt"
    if normalized_style == "bibtex":
        return reference.to_bibtex() + "\n", "application/x-bibtex; charset=utf-8", f"{filename_base}.bib"
    if normalized_style == "ris":
        return reference.to_ris(), "application/x-research-info-systems; charset=utf-8", f"{filename_base}.ris"
    return json.dumps(reference.to_json(), indent=2, ensure_ascii=False), "application/json; charset=utf-8", f"{filename_base}.json"


def normalize_single_reference_style(style: str | None) -> str:
    value = (style or "apa").strip().lower()
    if value in SINGLE_REFERENCE_EXPORT_STYLES:
        return value
    return "apa"


def build_reference_download_buffer(content: str) -> BytesIO:
    buffer = BytesIO(content.encode("utf-8"))
    buffer.seek(0)
    return buffer


def _build_linked_document_details(reference: Reference) -> list[dict[str, Any]]:
    document_entries: list[dict[str, Any]] = []
    seen_document_ids: set[int] = set()

    primary_document = reference.document
    if primary_document is not None:
        seen_document_ids.add(primary_document.id)
        document_entries.append(
            _serialize_linked_document(
                primary_document,
                reference=reference,
                reference_link=None,
                is_primary=True,
            )
        )

    reference_links = (
        DocumentReference.query
        .filter_by(reference_id=reference.id)
        .order_by(DocumentReference.created_at.desc(), DocumentReference.id.desc())
        .all()
    )
    for reference_link in reference_links:
        document = reference_link.document
        if document is None or document.id in seen_document_ids:
            continue
        seen_document_ids.add(document.id)
        document_entries.append(
            _serialize_linked_document(
                document,
                reference=reference,
                reference_link=reference_link,
                is_primary=False,
            )
        )

    return document_entries


def _serialize_linked_document(
    document,
    *,
    reference: Reference,
    reference_link: DocumentReference | None,
    is_primary: bool,
) -> dict[str, Any]:
    annotations = (
        DocumentAnnotation.query
        .filter_by(document_id=document.id)
        .order_by(DocumentAnnotation.created_at.desc(), DocumentAnnotation.id.desc())
        .limit(RECENT_ANNOTATION_LIMIT)
        .all()
    )
    return {
        "document_id": document.id,
        "filename": document.filename,
        "source_type": document.source_type,
        "is_primary": is_primary,
        "open_url": (
            f"/researcher/projects/{document.project_id}/documents/{document.id}"
            f"?source_view=reference&reference_id={reference.id}"
        ),
        "citation_context": reference_link.citation_context if reference_link is not None else None,
        "citation_type": reference_link.citation_type if reference_link is not None else None,
        "confidence": reference_link.confidence if reference_link is not None else None,
        "annotation_count": DocumentAnnotation.query.filter_by(document_id=document.id).count(),
        "recent_annotations": [serialize_document_annotation(annotation) for annotation in annotations],
    }


def _slugify(value: str) -> str:
    cleaned = "".join(char if char.isalnum() else "-" for char in value.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-").lower() or "reference"
