"""Helpers for grounded prompt assembly and supporting-source summaries."""

from typing import Any, Dict, List, Optional


def build_grounded_user_prompt(
    base_prompt: str,
    grounded_context: Optional[Dict[str, Any]],
    guidance_text: str,
) -> str:
    """Append grounded library context to a prompt when evidence is available."""
    prompt = str(base_prompt or "")
    context_text = str((grounded_context or {}).get("context_text") or "").strip()
    if not context_text:
        return prompt
    return f"{prompt}\n\n{guidance_text}\n{context_text}"


def merge_supporting_sources(
    current_sources: Optional[List[Dict[str, Any]]],
    grounded_context: Optional[Dict[str, Any]],
    max_items: int = 8,
) -> List[Dict[str, Any]]:
    """Merge and deduplicate supporting source summaries for API responses."""
    merged: List[Dict[str, Any]] = []
    seen_keys = set()

    for source in current_sources or []:
        if not isinstance(source, dict):
            continue
        normalized = _normalize_source(source)
        if not normalized:
            continue
        key = _source_key(normalized)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merged.append(normalized)
        if len(merged) >= max_items:
            return merged

    for source in (grounded_context or {}).get("sources") or []:
        if not isinstance(source, dict):
            continue
        normalized = _normalize_source(source)
        if not normalized:
            continue
        key = _source_key(normalized)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merged.append(normalized)
        if len(merged) >= max_items:
            break

    return merged


def _normalize_source(source: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    name = str(source.get("source") or source.get("filename") or "").strip()
    document_id = str(source.get("document_id") or "").strip()
    snippet = str(source.get("snippet") or "").strip()
    if not (name or document_id or snippet):
        return None
    return {
        "source": name,
        "document_id": document_id,
        "snippet": snippet,
    }


def _source_key(source: Dict[str, Any]) -> str:
    return "|".join(
        [
            str(source.get("document_id") or "").strip().lower(),
            str(source.get("source") or "").strip().lower(),
            str(source.get("snippet") or "").strip().lower(),
        ]
    )
