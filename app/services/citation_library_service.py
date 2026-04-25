"""Project-scoped citation library filtering and tag helpers."""
from __future__ import annotations

import re
from collections import Counter
from datetime import timedelta
from typing import Any

from sqlalchemy import or_

from app.core.time_utils import utcnow_naive
from app.models.researcher import Reference, ResearchProject


SMART_COLLECTION_KEYS = (
    "all",
    "recent",
    "linked",
    "notes",
    "needs_doi",
)

DEFAULT_SMART_COLLECTION = "all"
RECENT_REFERENCE_DAYS = 30


def normalize_reference_tags(raw_tags: Any) -> list[str]:
    """Normalize raw tag input into a deduplicated list."""
    if raw_tags is None:
        return []

    raw_items: list[str] = []
    if isinstance(raw_tags, str):
        raw_items = re.split(r"[;,]", raw_tags)
    elif isinstance(raw_tags, (list, tuple, set)):
        for item in raw_tags:
            if item is None:
                continue
            if isinstance(item, str):
                raw_items.extend(re.split(r"[;,]", item))
            else:
                raw_items.append(str(item))
    else:
        raw_items = [str(raw_tags)]

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        cleaned = " ".join(str(raw_item).strip().split())
        if not cleaned:
            continue
        marker = cleaned.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        normalized.append(cleaned)
    return normalized


def get_reference_tags(reference: Reference) -> list[str]:
    """Return normalized tags from reference metadata."""
    metadata = reference.get_metadata_dict()
    return normalize_reference_tags(metadata.get("tags"))


def set_reference_tags(reference: Reference, raw_tags: Any) -> list[str]:
    """Persist normalized tags into reference metadata without clobbering other metadata."""
    metadata = reference.get_metadata_dict()
    tags = normalize_reference_tags(raw_tags)
    if tags:
        metadata["tags"] = tags
    else:
        metadata.pop("tags", None)
    reference.set_metadata_dict(metadata)
    return tags


def build_project_citation_library(
    project: ResearchProject,
    *,
    collection: str | None = None,
    tag: str | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    """Build project-scoped references, smart collection counts, and tag filters."""
    selected_collection = (
        collection if collection in SMART_COLLECTION_KEYS else DEFAULT_SMART_COLLECTION
    )
    search_query = (query or "").strip()

    references = _query_project_references(project.id, search_query)
    collection_counts = _build_collection_counts(references)

    scoped_references = [
        reference
        for reference in references
        if _matches_collection(reference, selected_collection)
    ]
    tag_counts = _build_tag_counts(scoped_references)
    selected_tag = _resolve_selected_tag(tag, tag_counts)

    if selected_tag:
        scoped_references = [
            reference
            for reference in scoped_references
            if _reference_has_tag(reference, selected_tag)
        ]

    return {
        "references": scoped_references,
        "collections": collection_counts,
        "tags": tag_counts,
        "selected_collection": selected_collection,
        "selected_tag": selected_tag,
        "search_query": search_query,
        "result_count": len(scoped_references),
        "has_active_filters": bool(
            search_query or selected_tag or selected_collection != DEFAULT_SMART_COLLECTION
        ),
        "reference_tags_by_id": {
            reference.id: get_reference_tags(reference) for reference in scoped_references
        },
    }


def _query_project_references(project_id: int, search_query: str) -> list[Reference]:
    query = Reference.query.filter_by(project_id=project_id)
    if search_query:
        pattern = f"%{search_query}%"
        query = query.filter(
            or_(
                Reference.title.ilike(pattern),
                Reference.source.ilike(pattern),
                Reference.publication.ilike(pattern),
                Reference.doi.ilike(pattern),
                Reference.notes.ilike(pattern),
                Reference.authors_json.ilike(pattern),
                Reference.keywords_json.ilike(pattern),
                Reference.metadata_json.ilike(pattern),
            )
        )
    return query.order_by(Reference.created_at.desc()).all()


def _build_collection_counts(references: list[Reference]) -> list[dict[str, Any]]:
    return [
        {
            "key": key,
            "count": sum(1 for reference in references if _matches_collection(reference, key)),
        }
        for key in SMART_COLLECTION_KEYS
    ]


def _build_tag_counts(references: list[Reference]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    display_by_marker: dict[str, str] = {}
    for reference in references:
        for tag in get_reference_tags(reference):
            marker = tag.casefold()
            display_by_marker.setdefault(marker, tag)
            counts[marker] += 1

    return [
        {"name": display_by_marker[marker], "count": counts[marker]}
        for marker in sorted(
            counts,
            key=lambda value: (display_by_marker[value].casefold(), display_by_marker[value]),
        )
    ]


def _resolve_selected_tag(tag: str | None, tag_counts: list[dict[str, Any]]) -> str | None:
    normalized = normalize_reference_tags(tag)
    if not normalized:
        return None
    requested = normalized[0]
    for entry in tag_counts:
        if entry["name"].casefold() == requested.casefold():
            return entry["name"]
    return requested


def _matches_collection(reference: Reference, collection: str) -> bool:
    if collection == "recent":
        cutoff = utcnow_naive() - timedelta(days=RECENT_REFERENCE_DAYS)
        return bool(reference.created_at and reference.created_at >= cutoff)
    if collection == "linked":
        return bool(reference.document_id or (reference.citation_count or 0) > 0)
    if collection == "notes":
        return bool((reference.notes or "").strip())
    if collection == "needs_doi":
        return not bool((reference.doi or "").strip())
    return True


def _reference_has_tag(reference: Reference, selected_tag: str) -> bool:
    selected_marker = selected_tag.casefold()
    return any(tag.casefold() == selected_marker for tag in get_reference_tags(reference))
