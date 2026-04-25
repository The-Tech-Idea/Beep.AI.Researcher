"""Import external reference attachments into project documents."""
from __future__ import annotations

import io
import logging
import mimetypes
import uuid
from pathlib import Path
from typing import Any

from app.core.time_utils import utcnow_naive
from app.database import db
from app.models.integrations_registry import SERVICE_TYPE_ZOTERO
from app.models.researcher import Reference, ResearchProject, ResearcherDocument
from app.services.beep_ai_client import is_configured, sync_document_to_rag
from app.services.quota_service import quota_service
from app.services.reference_external_attachment_service import (
    get_project_reference_external_attachments,
)
from app.services.reference_service import link_reference_to_document
from app.services.storage import get_storage_backend
from app.services.user_integration_connection_service import resolve_user_service_connection
from app.services.zotero_connection_service import build_zotero_provider


logger = logging.getLogger(__name__)

SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".html", ".csv", ".json"}
SUPPORTED_TEXT_MIME_PREFIXES = ("text/",)
SUPPORTED_TEXT_MIME_TYPES = {
    "application/json",
    "application/ld+json",
}


def import_project_reference_attachment(
    project: ResearchProject,
    reference: Reference,
    *,
    attachment_item_key: str,
    user_id: int,
) -> dict[str, Any]:
    """Import one external-library attachment into project documents."""
    if reference.project_id != project.id:
        raise ValueError("Reference does not belong to this project.")

    attachment = _get_attachment_or_raise(project, reference, attachment_item_key, user_id=user_id)
    existing_document = _get_existing_attachment_document(project.id, attachment_item_key)
    if existing_document is not None:
        _ensure_reference_document_link(reference, existing_document.id, attachment)
        _promote_primary_document_if_missing(reference, existing_document.id)
        return {
            "created": False,
            "linked": True,
            "document": existing_document,
            "rag_sync": {
                "attempted": False,
                "synced": False,
                "message": "This attachment is already in the project files.",
            },
            "message": "This attachment is already in the project files.",
        }

    provider_name = str(
        reference.get_metadata_dict().get("external_library", {}).get("provider") or ""
    ).strip().lower()
    if provider_name != "zotero":
        raise ValueError("This attachment source cannot be imported automatically yet.")

    connection = resolve_user_service_connection(user_id, SERVICE_TYPE_ZOTERO)
    if not connection["service"] or not connection["connected"] or not connection["api_key"]:
        raise ValueError("Connect Zotero before importing this attachment into the project.")

    provider = build_zotero_provider(connection)
    download = provider.download_attachment(attachment_item_key)

    raw_bytes = download.get("content") or b""
    if not raw_bytes:
        raise ValueError("The selected attachment did not return any file content.")

    file_size = len(raw_bytes)
    quota_service.check_quota(user_id=user_id, upload_size_bytes=file_size)

    filename = _choose_filename(attachment, download)
    storage_key = _save_attachment_bytes(project.id, filename, raw_bytes)
    text_content = _extract_text_content(filename, download.get("content_type"), raw_bytes)

    document = ResearcherDocument(
        project_id=project.id,
        filename=filename,
        file_path=storage_key,
        mime_type=download.get("content_type") or "application/octet-stream",
        text_content=text_content,
        file_size=file_size,
        source_type="zotero_attachment",
        source_id=attachment_item_key,
        source_url=attachment.get("open_url") or download.get("download_url"),
        imported_at=utcnow_naive(),
    )
    db.session.add(document)
    db.session.flush()

    _promote_primary_document_if_missing(reference, document.id)
    _ensure_reference_document_link(reference, document.id, attachment)
    try:
        quota_service.record_upload(user_id=user_id, file_size_bytes=file_size)
    except Exception as exc:
        logger.warning("quota record_upload failed for imported attachment: %s", exc)

    rag_sync = {
        "attempted": False,
        "synced": False,
        "message": "This file was added to the project. Open it to review or extract text before indexing.",
    }
    if text_content and project.collection_id and is_configured():
        synced, rag_result = sync_document_to_rag(project, document, user_id=user_id)
        rag_sync = {
            "attempted": True,
            "synced": synced,
            "message": "File indexed for library search." if synced else str(rag_result),
        }

    return {
        "created": True,
        "linked": True,
        "document": document,
        "rag_sync": rag_sync,
        "message": "Attachment added to the project files.",
    }


def _get_attachment_or_raise(
    project: ResearchProject,
    reference: Reference,
    attachment_item_key: str,
    *,
    user_id: int,
) -> dict[str, Any]:
    payload = get_project_reference_external_attachments(project, reference, user_id=user_id)
    normalized_item_key = str(attachment_item_key or "").strip()
    attachment = next(
        (
            entry
            for entry in payload.get("attachments") or []
            if str(entry.get("item_key") or "").strip() == normalized_item_key
        ),
        None,
    )
    if attachment is None:
        raise ValueError("The selected attachment could not be found for this reference.")
    if not attachment.get("can_import"):
        raise ValueError("This attachment is linked in Zotero and cannot be imported automatically.")
    return attachment


def _get_existing_attachment_document(project_id: int, attachment_item_key: str) -> ResearcherDocument | None:
    return (
        ResearcherDocument.query
        .filter_by(
            project_id=project_id,
            source_type="zotero_attachment",
            source_id=str(attachment_item_key or "").strip(),
        )
        .first()
    )


def _ensure_reference_document_link(reference: Reference, document_id: int, attachment: dict[str, Any]) -> None:
    link_reference_to_document(
        reference,
        document_id,
        {
            "citation_type": "attachment",
            "citation_context": _build_attachment_context(attachment),
            "citation_count": 1,
            "confidence": 1.0,
        },
    )


def _promote_primary_document_if_missing(reference: Reference, document_id: int) -> None:
    if reference.document_id:
        return
    reference.document_id = document_id


def _build_attachment_context(attachment: dict[str, Any]) -> str:
    attachment_title = str(attachment.get("title") or attachment.get("filename") or "Attachment").strip()
    return f"Imported from external library attachment: {attachment_title}"


def _choose_filename(attachment: dict[str, Any], download: dict[str, Any]) -> str:
    raw_name = (
        str(download.get("filename") or "").strip()
        or str(attachment.get("filename") or "").strip()
        or str(attachment.get("title") or "").strip()
        or "attachment"
    )
    safe_name = Path(raw_name).name or "attachment"

    if Path(safe_name).suffix:
        return safe_name

    guessed_extension = mimetypes.guess_extension(download.get("content_type") or "")
    if guessed_extension:
        return f"{safe_name}{guessed_extension}"
    return safe_name


def _save_attachment_bytes(project_id: int, filename: str, raw_bytes: bytes) -> str:
    safe_key = f"{project_id}_{uuid.uuid4().hex[:8]}_{Path(filename).name}"
    backend = get_storage_backend()
    return backend.save(io.BytesIO(raw_bytes), safe_key)


def _extract_text_content(filename: str, content_type: str | None, raw_bytes: bytes) -> str | None:
    extension = Path(filename).suffix.lower()
    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()
    is_text_content = (
        extension in SUPPORTED_TEXT_EXTENSIONS
        or normalized_content_type in SUPPORTED_TEXT_MIME_TYPES
        or any(normalized_content_type.startswith(prefix) for prefix in SUPPORTED_TEXT_MIME_PREFIXES)
    )
    if not is_text_content:
        return None
    try:
        return raw_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return None
