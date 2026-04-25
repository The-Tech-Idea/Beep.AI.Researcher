"""Project bibliography preview and export helpers."""
from __future__ import annotations

import json
import re

from app.models.researcher import ResearchProject
from app.services.citation_library_service import build_project_citation_library
from app.services.reference_service import reference_to_dict

DEFAULT_BIBLIOGRAPHY_PREVIEW_LIMIT = 25

_BIBLIOGRAPHY_STYLE_OPTIONS = (
    ("apa", "APA"),
    ("mla", "MLA"),
    ("chicago", "Chicago"),
    ("bibtex", "BibTeX"),
    ("ris", "RIS"),
    ("json", "JSON"),
)
_RAW_BIBLIOGRAPHY_STYLES = {"bibtex", "ris", "json"}
_SUPPORTED_BIBLIOGRAPHY_STYLES = {key for key, _ in _BIBLIOGRAPHY_STYLE_OPTIONS}


def get_bibliography_style_options() -> list[dict]:
    return [
        {
            "key": key,
            "label": label,
            "preview_mode": _get_preview_mode(key),
        }
        for key, label in _BIBLIOGRAPHY_STYLE_OPTIONS
    ]


def normalize_bibliography_style(style: str | None) -> str:
    value = (style or "apa").strip().lower()
    if value in _SUPPORTED_BIBLIOGRAPHY_STYLES:
        return value
    return "apa"


def build_project_bibliography_preview(
    project: ResearchProject,
    *,
    style: str = "apa",
    collection: str | None = None,
    tag: str | None = None,
    query: str | None = None,
    limit: int = DEFAULT_BIBLIOGRAPHY_PREVIEW_LIMIT,
) -> dict:
    bibliography_style = normalize_bibliography_style(style)
    preview_limit = _normalize_preview_limit(limit)
    references = _get_project_bibliography_references(
        project,
        collection=collection,
        tag=tag,
        query=query,
    )
    total_count = len(references)
    preview_references = references[:preview_limit]
    preview_mode = _get_preview_mode(bibliography_style)
    content, mimetype, filename = _build_bibliography_content(
        project,
        references,
        bibliography_style,
    )

    preview = {
        "style": bibliography_style,
        "preview_mode": preview_mode,
        "total_count": total_count,
        "preview_count": len(preview_references),
        "truncated": total_count > len(preview_references),
        "filename": filename,
        "mimetype": mimetype,
        "content": content,
    }

    if preview_mode == "raw":
        preview_content, _, _ = _build_bibliography_content(
            project,
            preview_references,
            bibliography_style,
        )
        preview["preview_content"] = preview_content
        preview["entries"] = []
        return preview

    entries = [
        format_bibliography_entry(reference, bibliography_style)
        for reference in preview_references
    ]
    preview["entries"] = entries
    preview["preview_content"] = "\n\n".join(entries)
    return preview


def export_project_bibliography(
    project: ResearchProject,
    *,
    style: str = "apa",
    collection: str | None = None,
    tag: str | None = None,
    query: str | None = None,
) -> tuple[str, str, str]:
    bibliography_style = normalize_bibliography_style(style)
    references = _get_project_bibliography_references(
        project,
        collection=collection,
        tag=tag,
        query=query,
    )
    return _build_bibliography_content(project, references, bibliography_style)


def format_bibliography_entry(reference, style: str = "apa") -> str:
    bibliography_style = normalize_bibliography_style(style)
    if bibliography_style == "apa":
        return reference.to_apa()
    if bibliography_style == "mla":
        return reference.to_mla()
    if bibliography_style == "chicago":
        return reference.to_chicago()
    if bibliography_style == "bibtex":
        return reference.to_bibtex()
    if bibliography_style == "ris":
        return reference.to_ris()
    if bibliography_style == "json":
        return json.dumps(reference_to_dict(reference), ensure_ascii=False)

    return reference.to_apa()


def _build_bibliography_content(
    project: ResearchProject,
    references: list,
    style: str,
) -> tuple[str, str, str]:
    project_slug = _sanitize_filename_segment(project.name)
    if style == "json":
        content = json.dumps(
            [reference_to_dict(reference) for reference in references],
            indent=2,
            ensure_ascii=False,
        )
        return content or "[]", "application/json", f"{project_slug}_references.json"

    if style == "bibtex":
        content = "\n\n".join(reference.to_bibtex() for reference in references)
        return (
            content or "% No references yet.",
            "text/x-bibtex",
            f"{project_slug}_references.bib",
        )

    if style == "ris":
        content = "\n".join(reference.to_ris().strip() for reference in references)
        if content:
            content += "\n"
        else:
            content = "TY  - GEN\nER  - \n"
        return (
            content,
            "application/x-research-info-systems",
            f"{project_slug}_references.ris",
        )

    lines = [format_bibliography_entry(reference, style) for reference in references]
    text = "\n".join(lines) or "No references yet."
    return text, "text/plain", f"{project_slug}_references_{style}.txt"


def _get_project_bibliography_references(
    project: ResearchProject,
    *,
    collection: str | None = None,
    tag: str | None = None,
    query: str | None = None,
) -> list:
    library_view = build_project_citation_library(
        project,
        collection=collection,
        tag=tag,
        query=query,
    )
    return list(library_view["references"])


def _normalize_preview_limit(limit: int | str | None) -> int:
    try:
        value = int(limit or DEFAULT_BIBLIOGRAPHY_PREVIEW_LIMIT)
    except (TypeError, ValueError):
        value = DEFAULT_BIBLIOGRAPHY_PREVIEW_LIMIT
    return max(1, min(value, 50))


def _get_preview_mode(style: str) -> str:
    return "raw" if style in _RAW_BIBLIOGRAPHY_STYLES else "list"


def _sanitize_filename_segment(value: str | None) -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", (value or "").strip())
    return text.strip("._") or "project"
