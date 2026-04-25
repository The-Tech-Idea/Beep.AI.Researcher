"""JSON payload shapers for Phase 1 AI discovery pages."""
from __future__ import annotations

from app.services.ai_discovery_utils import normalize_identifier, split_external_id


def build_external_url(source: str | None, external_id: str | None) -> str | None:
    """Build a best-effort external paper URL from the canonical item id."""
    scheme, identifier = split_external_id(external_id)
    source_key = (scheme or source or "").strip().lower()
    normalized_id = normalize_identifier(identifier)

    if not normalized_id or normalized_id.startswith("title:"):
        return None

    if source_key in {"doi", "crossref"}:
        return f"https://doi.org/{normalized_id}"
    if source_key == "pubmed":
        return f"https://pubmed.ncbi.nlm.nih.gov/{normalized_id}/"
    if source_key == "arxiv":
        return f"https://arxiv.org/abs/{normalized_id}"
    if source_key == "semantic_scholar":
        return f"https://www.semanticscholar.org/paper/{normalized_id}"
    return None


def feed_recommendation_to_payload(item) -> dict:
    payload = dict(item.to_dict())
    payload["is_dismissed"] = bool(payload.get("dismissed"))
    payload["is_saved"] = bool(payload.get("saved"))
    payload["recommended_date"] = payload.get("recommended_date") or payload.get("feed_date")
    payload["url"] = payload.get("url") or build_external_url(
        payload.get("source"), payload.get("external_id")
    )
    return payload


def reading_list_item_to_payload(item) -> dict:
    payload = dict(item.to_dict())
    if not payload.get("source"):
        payload["source"], _ = split_external_id(payload.get("external_id"))
    payload["url"] = payload.get("url") or build_external_url(
        payload.get("source"), payload.get("external_id")
    )
    return payload


def paper_alert_to_payload(item) -> dict:
    payload = dict(item.to_dict())
    payload["matched_at"] = (
        payload.get("matched_at")
        or payload.get("alert_date")
        or payload.get("created_at")
    )
    payload["url"] = payload.get("url") or build_external_url(
        payload.get("source"), payload.get("external_id")
    )
    return payload