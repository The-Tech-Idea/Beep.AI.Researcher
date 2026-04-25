"""External-library attachment helpers for project references."""
from __future__ import annotations

from typing import Any

from app.database import db
from app.models.integrations_registry import SERVICE_TYPE_ZOTERO
from app.models.researcher import Reference, ResearchProject
from app.services.user_integration_connection_service import resolve_user_service_connection
from app.services.zotero_connection_service import build_zotero_provider


def get_cached_reference_external_attachments(reference: Reference) -> list[dict[str, Any]]:
    """Return normalized cached attachment metadata for one reference."""
    metadata = reference.get_metadata_dict()
    external_library = metadata.get("external_library")
    if not isinstance(external_library, dict):
        return []
    return _normalize_attachment_list(external_library.get("attachments"))


def get_project_reference_external_attachments(
    project: ResearchProject,
    reference: Reference,
    *,
    user_id: int,
) -> dict[str, Any]:
    """Return attachment metadata for one external-library reference."""
    if reference.project_id != project.id:
        raise ValueError("Reference does not belong to this project.")

    metadata = reference.get_metadata_dict()
    external_library = metadata.get("external_library")
    if not isinstance(external_library, dict):
        return {
            "provider": None,
            "attachments": [],
            "cached": False,
            "refreshed": False,
        }

    provider_name = str(external_library.get("provider") or "").strip().lower()
    item_key = str(external_library.get("item_key") or "").strip()
    cached_attachments = get_cached_reference_external_attachments(reference)

    if provider_name != "zotero" or not item_key:
        return {
            "provider": provider_name or None,
            "attachments": cached_attachments,
            "cached": bool(cached_attachments),
            "refreshed": False,
        }

    connection = resolve_user_service_connection(user_id, SERVICE_TYPE_ZOTERO)
    if not connection["service"] or not connection["connected"] or not connection["api_key"]:
        if cached_attachments:
            return {
                "provider": "zotero",
                "attachments": cached_attachments,
                "cached": True,
                "refreshed": False,
            }
        raise ValueError("Connect Zotero to load attachment details for this source.")

    try:
        provider = build_zotero_provider(connection)
        live_attachments = _normalize_attachment_list(provider.list_item_attachments(item_key))
    except ValueError:
        raise
    except Exception as exc:
        if cached_attachments:
            return {
                "provider": "zotero",
                "attachments": cached_attachments,
                "cached": True,
                "refreshed": False,
                "message": str(exc),
            }
        raise ValueError("Could not load Zotero attachments for this source.") from exc

    if live_attachments != cached_attachments:
        external_library["attachments"] = live_attachments
        metadata["external_library"] = external_library
        reference.set_metadata_dict(metadata)
        db.session.commit()

    return {
        "provider": "zotero",
        "attachments": live_attachments,
        "cached": False,
        "refreshed": True,
    }


def _normalize_attachment_list(entries: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw_entry in list(entries or []):
        if not isinstance(raw_entry, dict):
            continue
        normalized_entry = _normalize_attachment_entry(raw_entry)
        if not normalized_entry:
            continue
        normalized.append(normalized_entry)
    return normalized


def _normalize_attachment_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    title = " ".join(str(entry.get("title") or entry.get("filename") or "").strip().split())
    item_key = " ".join(str(entry.get("item_key") or "").strip().split())
    filename = " ".join(str(entry.get("filename") or "").strip().split())
    content_type = " ".join(str(entry.get("content_type") or "").strip().split())
    link_mode = " ".join(str(entry.get("link_mode") or "").strip().split())
    open_url = " ".join(str(entry.get("url") or entry.get("item_url") or "").strip().split())

    if not any([title, item_key, filename, open_url]):
        return None

    normalized_link_mode = link_mode.lower()

    return {
        "item_key": item_key,
        "title": title or filename or "Attachment",
        "filename": filename or title or "",
        "content_type": content_type,
        "link_mode": link_mode,
        "open_url": open_url or None,
        "can_import": bool(item_key and normalized_link_mode not in {"linked_url", "linked_file"}),
    }
