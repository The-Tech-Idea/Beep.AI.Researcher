"""Project-scoped Zotero library sync for citation references."""
from __future__ import annotations

from typing import Any

from app.core.time_utils import utcnow_naive
from app.database import db
from app.integrations.citation.base_citation import CitationItem
from app.models.integrations_registry import SERVICE_TYPE_ZOTERO
from app.models.researcher import Reference, ResearchProject
from app.services.reference_service import create_reference
from app.services.user_integration_connection_service import resolve_user_service_connection
from app.services.zotero_connection_service import build_zotero_provider


DEFAULT_ZOTERO_SYNC_LIMIT = 100


def get_project_zotero_sync_status(project: ResearchProject, *, user_id: int) -> dict[str, Any]:
    """Return the current Zotero connection state for a project/user."""
    connection = resolve_user_service_connection(user_id, SERVICE_TYPE_ZOTERO)
    service = connection["service"]
    if service is None:
        return {
            "available": False,
            "connected": False,
            "ready": False,
            "service_name": "Zotero",
            "message": "Zotero is not enabled for this workspace yet.",
            "collections": [],
        }

    if not connection["connected"] or not connection["api_key"]:
        return {
            "available": True,
            "connected": False,
            "ready": False,
            "service_name": service.name,
            "message": "Connect a Zotero library to import references into this project.",
            "collections": [],
            "connection_source": connection["source"],
        }

    try:
        provider = build_zotero_provider(connection)
        collections = provider.list_collections()
    except ValueError as exc:
        return {
            "available": True,
            "connected": True,
            "ready": False,
            "service_name": service.name,
            "message": str(exc),
            "collections": [],
            "connection_source": connection["source"],
            "display_name": connection["display_name"],
        }

    extra_data = connection["extra_data"]
    return {
        "available": True,
        "connected": True,
        "ready": True,
        "service_name": service.name,
        "message": "Zotero is ready to sync into this project's citation library.",
        "collections": sorted(collections, key=lambda item: item.get("name", "").casefold()),
        "connection_source": connection["source"],
        "display_name": connection["display_name"],
        "library_type": extra_data.get("library_type", "user"),
        "zotero_user_id": extra_data.get("user_id", ""),
        "zotero_group_id": extra_data.get("group_id", ""),
    }


def sync_project_references_from_zotero(
    project: ResearchProject,
    *,
    user_id: int,
    collection_key: str | None = None,
    limit: int = DEFAULT_ZOTERO_SYNC_LIMIT,
) -> dict[str, Any]:
    """Pull Zotero items into project references with dedupe/upsert behavior."""
    connection = resolve_user_service_connection(user_id, SERVICE_TYPE_ZOTERO)
    service = connection["service"]
    if service is None or not connection["connected"] or not connection["api_key"]:
        raise ValueError("Connect Zotero before importing into this project.")

    provider = build_zotero_provider(connection)
    safe_limit = min(max(int(limit or DEFAULT_ZOTERO_SYNC_LIMIT), 1), DEFAULT_ZOTERO_SYNC_LIMIT)
    items, _version = provider.list_items(collection_id=collection_key or None, limit=safe_limit)

    existing_references = Reference.query.filter_by(project_id=project.id).all()
    index = _build_reference_index(existing_references)

    created = 0
    updated = 0
    skipped = 0
    synced_reference_ids: list[int] = []

    for item in items:
        reference = _find_existing_reference(item, index)
        if reference is None:
            reference = create_reference(
                project,
                _citation_item_to_reference_payload(item),
                commit=False,
            )
            db.session.flush()
            created += 1
        else:
            _apply_citation_item_to_reference(reference, item)
            updated += 1

        _merge_external_library_metadata(reference, item, connection)
        synced_reference_ids.append(reference.id)
        _register_reference_index(index, reference)

    credential = connection.get("credential")
    if credential is not None:
        credential.last_sync_at = utcnow_naive()

    db.session.commit()
    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "imported": created + updated,
        "collection_key": collection_key or "",
        "reference_ids": synced_reference_ids,
    }
def _build_reference_index(references: list[Reference]) -> dict[str, dict[str, Reference]]:
    index = {
        "external": {},
        "doi": {},
        "title_year": {},
    }
    for reference in references:
        _register_reference_index(index, reference)
    return index


def _register_reference_index(index: dict[str, dict[str, Reference]], reference: Reference) -> None:
    metadata = reference.get_metadata_dict()
    external = metadata.get("external_library")
    if isinstance(external, dict):
        item_key = str(external.get("item_key") or "").strip()
        if external.get("provider") == "zotero" and item_key:
            index["external"][item_key] = reference

    if reference.doi:
        index["doi"][reference.doi.casefold()] = reference

    title_year = _build_title_year_key(reference.title, reference.year)
    if title_year:
        index["title_year"][title_year] = reference


def _find_existing_reference(item: CitationItem, index: dict[str, dict[str, Reference]]) -> Reference | None:
    if item.id and item.id in index["external"]:
        return index["external"][item.id]

    if item.doi:
        doi_key = item.doi.casefold()
        if doi_key in index["doi"]:
            return index["doi"][doi_key]

    title_year = _build_title_year_key(item.title, item.year)
    if title_year and title_year in index["title_year"]:
        return index["title_year"][title_year]
    return None


def _build_title_year_key(title: str | None, year: Any) -> str | None:
    if not title:
        return None
    normalized_title = " ".join(str(title).strip().casefold().split())
    if not normalized_title:
        return None
    normalized_year = str(year).strip() if year is not None else ""
    return f"{normalized_title}|{normalized_year}"


def _citation_item_to_reference_payload(item: CitationItem) -> dict[str, Any]:
    publication = item.journal or None
    return {
        "title": item.title,
        "authors": item.authors,
        "year": _parse_year(item.year),
        "publication": publication,
        "source": publication,
        "source_type": _map_item_type(item.item_type),
        "doi": item.doi,
        "url": item.url,
        "abstract": item.abstract,
        "volume": item.volume,
        "issue": item.issue,
        "pages": item.pages,
        "notes": "\n\n".join(note.strip() for note in item.notes if str(note).strip()) or None,
        "tags": item.tags,
        "citation_key": item.id or item.title,
    }


def _apply_citation_item_to_reference(reference: Reference, item: CitationItem) -> None:
    payload = _citation_item_to_reference_payload(item)
    if payload["title"]:
        reference.title = payload["title"]
    if payload["authors"]:
        reference.set_authors(payload["authors"])
    if payload["year"] is not None:
        reference.year = payload["year"]
    if payload["source"]:
        reference.source = payload["source"]
    if payload["publication"]:
        reference.publication = payload["publication"]
    if payload["source_type"]:
        reference.source_type = payload["source_type"]
    if payload["doi"]:
        reference.doi = payload["doi"]
    if payload["url"]:
        reference.url = payload["url"]
    if payload["abstract"]:
        reference.abstract = payload["abstract"]
    if payload["volume"]:
        reference.volume = payload["volume"]
    if payload["issue"]:
        reference.issue = payload["issue"]
    if payload["pages"]:
        reference.pages = payload["pages"]
    if payload["notes"]:
        reference.notes = payload["notes"]


def _merge_external_library_metadata(
    reference: Reference,
    item: CitationItem,
    connection: dict[str, Any],
) -> None:
    metadata = reference.get_metadata_dict()
    existing_tags = metadata.get("tags", [])
    merged_tags = _normalize_tag_union(existing_tags, item.tags)

    metadata["external_library"] = {
        "provider": "zotero",
        "item_key": item.id,
        "library_type": connection["extra_data"].get("library_type", "user"),
        "user_id": connection["extra_data"].get("user_id"),
        "group_id": connection["extra_data"].get("group_id"),
        "collection_keys": item.collections,
        "version": item.metadata.get("zotero_version"),
        "date_added": item.metadata.get("date_added"),
        "date_modified": item.metadata.get("date_modified"),
        "synced_at": utcnow_naive().isoformat(),
        "connection_source": connection["source"],
    }
    if merged_tags:
        metadata["tags"] = merged_tags
    else:
        metadata.pop("tags", None)
    reference.set_metadata_dict(metadata)


def _normalize_tag_union(existing_tags: Any, incoming_tags: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for raw_tag in list(existing_tags or []) + list(incoming_tags or []):
        cleaned = " ".join(str(raw_tag).strip().split())
        if not cleaned:
            continue
        marker = cleaned.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        merged.append(cleaned)
    return merged


def _map_item_type(item_type: str | None) -> str:
    normalized = (item_type or "").strip()
    mapping = {
        "journalArticle": "journal",
        "conferencePaper": "conference",
        "book": "book",
        "bookSection": "book",
        "thesis": "thesis",
        "report": "report",
        "webpage": "website",
    }
    return mapping.get(normalized, "other")


def _parse_year(raw_year: Any) -> int | None:
    if raw_year is None:
        return None
    text = str(raw_year).strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None
