"""Plain-language graph reading mode contract for AI.Researcher."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


_GRAPH_READING_MODE_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "mode": "library_default",
        "label": "Use library default",
        "graph_extraction_profile_id": "",
        "description": "Follow the default relationship-reading setup already assigned to this document library.",
    },
    {
        "mode": "general_relationships",
        "label": "General relationships",
        "graph_extraction_profile_id": "system-balanced-graph-extraction",
        "description": "Connect people, organizations, topics, and references across different files.",
    },
    {
        "mode": "citations_and_evidence",
        "label": "Citations and evidence",
        "graph_extraction_profile_id": "system-research-citation-graph",
        "description": "Best for papers and reports where you want claims, citations, and evidence chains linked together.",
    },
    {
        "mode": "policies_and_rules",
        "label": "Policies and rules",
        "graph_extraction_profile_id": "system-policy-compliance-graph",
        "description": "Best for policies, standards, obligations, and exception-heavy material.",
    },
]


def get_graph_reading_mode_contract() -> Dict[str, Any]:
    """Return the plain-language graph reading mode contract for Researcher."""
    return {
        "default_mode": "library_default",
        "modes": [dict(item) for item in _GRAPH_READING_MODE_DEFINITIONS],
    }


def _profile_label_from_id(
    profile_id: Optional[str],
    available_profiles: Optional[List[Dict[str, Any]]] = None,
) -> Optional[str]:
    normalized_profile_id = str(profile_id or "").strip()
    if not normalized_profile_id:
        return None

    for item in _GRAPH_READING_MODE_DEFINITIONS:
        if str(item.get("graph_extraction_profile_id") or "").strip() == normalized_profile_id:
            return str(item.get("label") or "").strip() or normalized_profile_id

    for profile in available_profiles or []:
        candidate_id = str(profile.get("profile_id") or profile.get("id") or "").strip()
        if candidate_id != normalized_profile_id:
            continue
        return (
            str(profile.get("name") or "").strip()
            or str(profile.get("label") or "").strip()
            or normalized_profile_id
        )

    return normalized_profile_id


def resolve_graph_reading_mode(
    *,
    collection_graph_extraction_profile_id: Optional[str],
    database_default_graph_extraction_profile_id: Optional[str],
    effective_graph_extraction_profile_id: Optional[str],
    available_profiles: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Resolve the plain-language graph mode for the current effective profile chain."""
    collection_override = str(collection_graph_extraction_profile_id or "").strip()
    database_default = str(database_default_graph_extraction_profile_id or "").strip()
    effective_profile = str(effective_graph_extraction_profile_id or "").strip()
    database_default_label = _profile_label_from_id(database_default, available_profiles)
    effective_profile_label = _profile_label_from_id(effective_profile, available_profiles)
    collection_override_label = _profile_label_from_id(collection_override, available_profiles)

    if not collection_override:
        return {
            "mode": "library_default",
            "label": "Use library default",
            "graph_extraction_profile_id": "",
            "effective_graph_extraction_profile_id": effective_profile,
            "effective_graph_extraction_profile_label": effective_profile_label,
            "database_default_graph_extraction_profile_id": database_default,
            "database_default_graph_extraction_profile_label": database_default_label,
            "is_library_default": True,
            "is_custom": False,
        }

    for item in _GRAPH_READING_MODE_DEFINITIONS:
        profile_id = str(item.get("graph_extraction_profile_id") or "").strip()
        if profile_id and profile_id == collection_override:
            return {
                **dict(item),
                "effective_graph_extraction_profile_id": effective_profile,
                "effective_graph_extraction_profile_label": effective_profile_label,
                "database_default_graph_extraction_profile_id": database_default,
                "database_default_graph_extraction_profile_label": database_default_label,
                "collection_graph_extraction_profile_label": collection_override_label,
                "is_library_default": False,
                "is_custom": False,
            }

    return {
        "mode": "custom",
        "label": "Current advanced setup",
        "graph_extraction_profile_id": collection_override,
        "effective_graph_extraction_profile_id": effective_profile,
        "effective_graph_extraction_profile_label": effective_profile_label,
        "database_default_graph_extraction_profile_id": database_default,
        "database_default_graph_extraction_profile_label": database_default_label,
        "collection_graph_extraction_profile_label": collection_override_label,
        "is_library_default": False,
        "is_custom": True,
        "description": "This project is using an administrator-defined relationship-reading setup.",
    }
