"""Index reference metadata to the project RAG collection (Phase 07 — Flow A).

When a ``Reference`` is added or updated, calling ``sync_reference_to_rag``
pushes the title + authors + abstract + bibliographic fields as a lightweight
chunk so the project chat can answer questions like "what did Smith (2020)
argue?" even before the full PDF is attached.

The stable document key ``reference_{ref.id}`` means repeated calls are
idempotent — the Server replaces the existing chunk if it already exists.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _build_reference_text(ref) -> str:
    """Compose a searchable text block from reference fields."""
    authors = ref.get_authors() if callable(getattr(ref, "get_authors", None)) else []
    authors_str = "; ".join(authors) if authors else "Unknown authors"

    parts = [
        f"Title: {ref.title}",
        f"Authors: {authors_str}",
    ]
    if ref.year:
        parts.append(f"Year: {ref.year}")
    if ref.source:
        parts.append(f"Source: {ref.source}")
    if ref.volume or ref.issue or ref.pages:
        vol_str = ", ".join(
            filter(None, [
                f"vol. {ref.volume}" if ref.volume else None,
                f"no. {ref.issue}" if ref.issue else None,
                f"pp. {ref.pages}" if ref.pages else None,
            ])
        )
        parts.append(f"Volume/Pages: {vol_str}")
    if ref.doi:
        parts.append(f"DOI: {ref.doi}")
    if ref.abstract:
        # Truncate very long abstracts to avoid huge chunk sizes
        abstract = ref.abstract.strip()
        if len(abstract) > 2000:
            abstract = abstract[:2000] + "…"
        parts.append(f"Abstract: {abstract}")

    keywords = ref.get_keywords() if callable(getattr(ref, "get_keywords", None)) else []
    if keywords:
        parts.append(f"Keywords: {'; '.join(keywords)}")

    return "\n".join(parts)


def sync_reference_to_rag(
    project,
    ref,
    user_id: Optional[int] = None,
) -> tuple:
    """Push reference metadata to the project RAG collection.

    Returns ``(ok, result_or_error)`` — same contract as
    ``beep_ai_client.add_document_to_project_rag``.

    Safe to call on every Reference save; the stable ``document_id``
    (``reference_{ref.id}``) makes the operation idempotent on the Server.

    Also safe to call when Beep.AI.Server is not configured — returns
    ``(False, "Beep.AI.Server not configured")`` without raising.
    """
    from app.services.beep_ai_client import is_configured, add_document_to_project_rag

    if not is_configured():
        return False, "Beep.AI.Server not configured"

    if not getattr(project, "collection_id", None):
        return False, "Project has no RAG collection"

    text = _build_reference_text(ref)
    if not text.strip():
        return False, "Reference has no indexable content"

    metadata = {
        "source_type": "reference",
        "reference_id": str(ref.id),
        "rag_document_id": f"reference_{ref.id}",
        "citation_key": ref.citation_key or "",
        "year": str(ref.year) if ref.year else "",
        "ref_source_type": str(ref.source_type or ""),
        "content_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }

    try:
        result = add_document_to_project_rag(
            project=project,
            document_content=text,
            source=ref.title or ref.citation_key or f"ref_{ref.id}",
            document_id=f"reference_{ref.id}",
            user_id=user_id,
            metadata=metadata,
        )
    except Exception as exc:
        logger.warning("reference_rag_sync: unexpected error for ref %s: %s", ref.id, exc)
        return False, str(exc)

    return result


def sync_references_bulk(
    project,
    refs: list,
    user_id: Optional[int] = None,
) -> dict:
    """Sync a list of references; returns a summary dict.

    ::

        {"ok": 3, "failed": 1, "skipped": 0}
    """
    counts = {"ok": 0, "failed": 0, "skipped": 0}
    for ref in refs:
        if not getattr(ref, "title", None):
            counts["skipped"] += 1
            continue
        ok, _ = sync_reference_to_rag(project, ref, user_id=user_id)
        if ok:
            counts["ok"] += 1
        else:
            counts["failed"] += 1
    return counts
