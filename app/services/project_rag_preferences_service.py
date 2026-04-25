"""Resolve project-level RAG behavior defaults for Researcher."""

from typing import Optional


DEFAULT_PROJECT_QUALITY_MODE = "balanced"

_QUALITY_MODE_TEMPERATURES = {
    "fast": 0.35,
    "balanced": 0.2,
    "deep": 0.1,
    "high": 0.1,
}


def _normalize_quality_mode(value: Optional[str]) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    return normalized or None


def resolve_project_quality_mode(
    project,
    requested_quality_mode: Optional[str] = None,
) -> tuple[str, str]:
    """Return the effective project quality mode and its ownership source."""
    normalized_requested = _normalize_quality_mode(requested_quality_mode)
    if normalized_requested:
        return normalized_requested, "saved_project_choice"

    saved_quality_mode = _normalize_quality_mode(getattr(project, "rag_quality_mode", None))
    if saved_quality_mode:
        return saved_quality_mode, "saved_project_choice"

    return DEFAULT_PROJECT_QUALITY_MODE, "project_default"


def resolve_project_generation_temperature(
    project,
    requested_quality_mode: Optional[str] = None,
    explicit_temperature: Optional[float] = None,
    research_mode: bool = True,
) -> Optional[float]:
    """Return the effective generation temperature for project-backed assistance."""
    if explicit_temperature is not None:
        return explicit_temperature

    if not research_mode:
        return None

    quality_mode, _ = resolve_project_quality_mode(project, requested_quality_mode)
    return _QUALITY_MODE_TEMPERATURES.get(
        quality_mode,
        _QUALITY_MODE_TEMPERATURES[DEFAULT_PROJECT_QUALITY_MODE],
    )
