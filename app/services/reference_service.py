"""Helper utilities for references and citation exports."""

from __future__ import annotations

import re
import time

from app.core.time_utils import utcnow_naive
from app.database import db
from app.models.researcher import DocumentReference, Reference, ResearchProject
from app.services.citation_library_service import set_reference_tags


def clean_value(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_source_type(raw_type: str | None) -> str:
    value = (clean_value(raw_type) or "other").lower()
    mapping = {
        "article": "journal",
        "inproceedings": "conference",
        "proceedings": "conference",
        "misc": "other",
        "online": "website",
        "web": "website",
    }
    return mapping.get(value, value)


def _parse_authors(raw_authors):
    if not raw_authors:
        return []
    if isinstance(raw_authors, list):
        return [str(a).strip() for a in raw_authors if str(a).strip()]
    if isinstance(raw_authors, str):
        if ";" in raw_authors:
            return [a.strip() for a in raw_authors.split(";") if a.strip()]
        if " and " in raw_authors.lower():
            parts = re.split(r"\s+[Aa][Nn][Dd]\s+", raw_authors)
            return [a.strip() for a in parts if a.strip()]
        return [raw_authors.strip()] if raw_authors.strip() else []
    return []


def _parse_keywords(raw_keywords):
    if not raw_keywords:
        return []
    if isinstance(raw_keywords, list):
        return [str(k).strip() for k in raw_keywords if str(k).strip()]
    if isinstance(raw_keywords, str):
        return [k.strip() for k in re.split(r"[;,]", raw_keywords) if k.strip()]
    return []


def _ensure_unique_citation_key(project_id: int, preferred_key: str | None) -> str:
    base = clean_value(preferred_key) or f"ref_{project_id}_{int(time.time())}"
    key = base
    i = 1
    while Reference.query.filter_by(project_id=project_id, citation_key=key).first():
        i += 1
        key = f"{base}_{i}"
    return key


def create_reference(
    project: ResearchProject, data: dict, *, commit: bool = True
) -> Reference:
    """Persist a reference record for a project."""
    source = clean_value(data.get("source") or data.get("publication"))
    reference = Reference(
        project_id=project.id,
        document_id=int(data.get("document_id")) if data.get("document_id") else None,
        title=clean_value(data.get("title")) or project.name,
        source=source,
        publication=source,
        source_type=_normalize_source_type(data.get("source_type")),
        citation_key=_ensure_unique_citation_key(project.id, data.get("citation_key")),
        year=int(data.get("year"))
        if data.get("year") and str(data.get("year")).isdigit()
        else None,
        doi=clean_value(data.get("doi")),
        url=clean_value(data.get("url")),
        abstract=clean_value(data.get("abstract")),
        volume=clean_value(data.get("volume")),
        issue=clean_value(data.get("issue")),
        pages=clean_value(data.get("pages")),
        citation=clean_value(data.get("citation")),
        notes=clean_value(data.get("notes")),
    )

    # Use setter methods for JSON fields
    authors = _parse_authors(data.get("authors"))
    if authors:
        reference.set_authors(authors)

    keywords = _parse_keywords(data.get("keywords"))
    if keywords:
        reference.set_keywords(keywords)

    metadata = data.get("metadata")
    if isinstance(metadata, dict):
        reference.set_metadata_dict(metadata)
    set_reference_tags(reference, data.get("tags"))

    db.session.add(reference)
    if commit:
        db.session.commit()
    return reference


def reference_to_dict(reference: Reference) -> dict:
    return {
        "id": reference.id,
        "project_id": reference.project_id,
        "project_name": reference.project.name if reference.project else None,
        "document_id": reference.document_id,
        "document_filename": reference.document.filename
        if reference.document
        else None,
        "title": reference.title,
        "authors": reference.get_authors(),
        "keywords": reference.get_keywords(),
        "source": reference.source,
        "source_type": reference.source_type,
        "citation_key": reference.citation_key,
        "year": reference.year,
        "doi": reference.doi,
        "url": reference.url,
        "abstract": reference.abstract,
        "notes": reference.notes,
        "tags": reference.get_metadata_dict().get("tags", []),
        "citation_count": reference.citation_count,
        "linked_documents": len(reference.document_links or []),
        "created_at": reference.created_at.isoformat()
        if reference.created_at
        else None,
        "updated_at": reference.updated_at.isoformat()
        if reference.updated_at
        else None,
    }


def link_reference_to_document(
    reference: Reference, document_id: int, payload: dict | None = None
) -> DocumentReference:
    data = payload or {}
    link = DocumentReference.query.filter_by(
        reference_id=reference.id, document_id=document_id
    ).first()
    if not link:
        link = DocumentReference(reference_id=reference.id, document_id=document_id)
        db.session.add(link)
    link.citation_context = clean_value(data.get("citation_context"))
    if data.get("citation_count") is not None:
        try:
            link.citation_count = max(1, int(data.get("citation_count")))
        except (TypeError, ValueError):
            pass
    if data.get("confidence") is not None:
        try:
            link.confidence = float(data.get("confidence"))
        except (TypeError, ValueError):
            pass
    if data.get("citation_type"):
        link.citation_type = clean_value(data.get("citation_type")) or "direct"

    db.session.flush()
    reference.citation_count = DocumentReference.query.filter_by(
        reference_id=reference.id
    ).count()
    reference.last_citation_date = utcnow_naive()
    db.session.commit()
    return link


def unlink_reference_from_document(reference: Reference, document_id: int) -> bool:
    link = DocumentReference.query.filter_by(
        reference_id=reference.id, document_id=document_id
    ).first()
    if not link:
        return False
    db.session.delete(link)
    db.session.flush()
    reference.citation_count = DocumentReference.query.filter_by(
        reference_id=reference.id
    ).count()
    reference.last_citation_date = utcnow_naive() if reference.citation_count else None
    db.session.commit()
    return True


# =====================
# DOI / Citation Validation (H6)
# =====================


def validate_doi(doi: str) -> dict:
    """
    Validate a DOI by calling the Beep.AI.Server's /api/tools/validate-doi endpoint.

    Returns:
        dict with 'valid' (bool), 'metadata' (dict), or 'error' (str).
    """
    from app.services.beep_ai_client import _post, is_configured

    if not doi:
        return {"valid": False, "error": "No DOI provided"}
    if not is_configured():
        return {"valid": False, "error": "Beep.AI.Server not configured"}

    ok, result = _post("/api/tools/validate-doi", json_data={"doi": doi})
    if not ok:
        return {"valid": False, "error": str(result)}

    return result


def validate_citation_batch(project: ResearchProject) -> dict:
    """
    Bulk validate all DOIs in a project's references.

    Returns:
        dict with 'total', 'valid', 'invalid', 'skipped', 'details'.
    """
    references = Reference.query.filter_by(project_id=project.id).all()
    summary = {
        "total": len(references),
        "valid": 0,
        "invalid": 0,
        "skipped": 0,
        "details": [],
    }

    for ref in references:
        if not ref.doi:
            summary["skipped"] += 1
            continue

        result = validate_doi(ref.doi)
        detail = {
            "reference_id": ref.id,
            "doi": ref.doi,
            "title": ref.title,
            "valid": result.get("valid", False),
        }
        if result.get("error"):
            detail["error"] = result["error"]

        if detail["valid"]:
            summary["valid"] += 1
        else:
            summary["invalid"] += 1

        summary["details"].append(detail)

    return summary
