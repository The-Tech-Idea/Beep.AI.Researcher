"""Document annotation validation and persistence helpers."""
from __future__ import annotations

import re

from app.database import db
from app.models.researcher import DocumentAnnotation, ResearcherDocument


DEFAULT_HIGHLIGHT_COLOR = "#fef08a"
DEFAULT_CHUNK_ID = "chunk-0"
MAX_NOTE_LENGTH = 2000
MAX_SELECTED_TEXT_PREVIEW = 240
MAX_CONTEXT_PREVIEW = 320
CONTEXT_PADDING = 36
HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


class DocumentAnnotationValidationError(ValueError):
    """Raised when an annotation payload is invalid."""


def list_document_annotations(document: ResearcherDocument) -> list[dict]:
    """Return serialized annotations for one document."""
    annotations = (
        DocumentAnnotation.query
        .filter_by(document_id=document.id)
        .order_by(DocumentAnnotation.created_at.desc(), DocumentAnnotation.id.desc())
        .all()
    )
    return [serialize_document_annotation(annotation) for annotation in annotations]


def create_document_annotation(
    document: ResearcherDocument,
    *,
    created_by_id: int | None,
    chunk_id: str | None,
    start_offset,
    end_offset,
    note: str | None,
    highlight_color: str | None,
) -> dict:
    """Validate and persist a document annotation."""
    start_value, end_value = _normalize_offsets(document, start_offset, end_offset)
    annotation = DocumentAnnotation(
        document_id=document.id,
        chunk_id=_normalize_chunk_id(chunk_id),
        start_offset=start_value,
        end_offset=end_value,
        note=_normalize_note(note),
        highlight_color=_normalize_highlight_color(highlight_color),
        created_by_id=created_by_id,
    )
    db.session.add(annotation)
    db.session.commit()
    return serialize_document_annotation(annotation)


def delete_document_annotation(document: ResearcherDocument, annotation_id: int) -> bool:
    """Delete one annotation for a document."""
    annotation = (
        DocumentAnnotation.query
        .filter_by(document_id=document.id, id=annotation_id)
        .first()
    )
    if annotation is None:
        return False

    db.session.delete(annotation)
    db.session.commit()
    return True


def serialize_document_annotation(annotation: DocumentAnnotation) -> dict:
    """Return a stable route payload for one annotation."""
    document_text = (annotation.document.text_content or "") if annotation.document else ""
    selected_text, safe_start, safe_end = _slice_document_text(
        document_text,
        annotation.start_offset,
        annotation.end_offset,
    )
    return {
        "id": annotation.id,
        "chunk_id": annotation.chunk_id,
        "start_offset": safe_start,
        "end_offset": safe_end,
        "note": annotation.note or "",
        "highlight_color": annotation.highlight_color or DEFAULT_HIGHLIGHT_COLOR,
        "created_by_id": annotation.created_by_id,
        "created_by_name": getattr(annotation.created_by, "username", None),
        "created_at": annotation.created_at.isoformat() if annotation.created_at else None,
        "selected_text": _truncate_preview(selected_text, MAX_SELECTED_TEXT_PREVIEW),
        "context_preview": _build_context_preview(document_text, safe_start, safe_end),
    }


def _normalize_offsets(
    document: ResearcherDocument,
    start_offset,
    end_offset,
) -> tuple[int, int]:
    text = document.text_content or ""
    if not text:
        raise DocumentAnnotationValidationError(
            "This file does not contain readable text for saved highlights yet."
        )

    try:
        start_value = int(start_offset)
        end_value = int(end_offset)
    except (TypeError, ValueError) as exc:
        raise DocumentAnnotationValidationError(
            "start_offset and end_offset must be numeric."
        ) from exc

    if start_value < 0 or end_value < 0:
        raise DocumentAnnotationValidationError(
            "start_offset and end_offset must be zero or greater."
        )
    if end_value <= start_value:
        raise DocumentAnnotationValidationError(
            "end_offset must be greater than start_offset."
        )
    if end_value > len(text):
        raise DocumentAnnotationValidationError(
            "The selected passage is outside the readable text for this file."
        )
    return start_value, end_value


def _normalize_chunk_id(chunk_id: str | None) -> str:
    value = " ".join((chunk_id or "").strip().split())
    return value or DEFAULT_CHUNK_ID


def _normalize_note(note: str | None) -> str | None:
    value = " ".join((note or "").strip().split())
    if not value:
        return None
    if len(value) > MAX_NOTE_LENGTH:
        raise DocumentAnnotationValidationError(
            f"Notes must stay under {MAX_NOTE_LENGTH} characters."
        )
    return value


def _normalize_highlight_color(highlight_color: str | None) -> str:
    value = (highlight_color or DEFAULT_HIGHLIGHT_COLOR).strip()
    if not HEX_COLOR_PATTERN.match(value):
        raise DocumentAnnotationValidationError(
            "highlight_color must use #RRGGBB format."
        )
    return value.lower()


def _slice_document_text(text: str, start_offset, end_offset) -> tuple[str, int, int]:
    if not text:
        return "", 0, 0

    safe_start = max(0, min(int(start_offset or 0), len(text)))
    safe_end = max(safe_start, min(int(end_offset or 0), len(text)))
    if safe_end <= safe_start:
        return "", safe_start, safe_end
    return text[safe_start:safe_end], safe_start, safe_end


def _build_context_preview(text: str, start_offset: int, end_offset: int) -> str:
    if not text or end_offset <= start_offset:
        return ""

    context_start = max(0, start_offset - CONTEXT_PADDING)
    context_end = min(len(text), end_offset + CONTEXT_PADDING)
    prefix = "..." if context_start > 0 else ""
    suffix = "..." if context_end < len(text) else ""
    preview = prefix + text[context_start:context_end] + suffix
    return _truncate_preview(" ".join(preview.split()), MAX_CONTEXT_PREVIEW)


def _truncate_preview(value: str, limit: int) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."
