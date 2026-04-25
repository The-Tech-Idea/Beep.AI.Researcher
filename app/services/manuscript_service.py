"""Manuscript service — CRUD, reorder, and Markdown export (Phase 04)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.database import db
from app.core.time_utils import utcnow_naive
from app.models.researcher.manuscripts import Manuscript, ManuscriptSection


# ---------------------------------------------------------------------------
# Manuscript CRUD
# ---------------------------------------------------------------------------

def create_manuscript(project, title: str) -> Manuscript:
    """Create a new manuscript for *project* and commit."""
    ms = Manuscript(
        project_id=project.id,
        title=title.strip() or "Untitled Manuscript",
        created_at=utcnow_naive(),
    )
    db.session.add(ms)
    db.session.commit()
    return ms


def get_manuscript(manuscript_id: int, project_id: int) -> Optional[Manuscript]:
    return Manuscript.query.filter_by(id=manuscript_id, project_id=project_id).first()


def list_manuscripts(project_id: int) -> List[Manuscript]:
    return (
        Manuscript.query.filter_by(project_id=project_id)
        .order_by(Manuscript.created_at)
        .all()
    )


def update_manuscript_title(manuscript: Manuscript, title: str) -> Manuscript:
    manuscript.title = title.strip() or manuscript.title
    db.session.commit()
    return manuscript


def delete_manuscript(manuscript: Manuscript) -> None:
    db.session.delete(manuscript)
    db.session.commit()


# ---------------------------------------------------------------------------
# Section CRUD
# ---------------------------------------------------------------------------

def _next_sort_order(manuscript_id: int, parent_id: Optional[int] = None) -> int:
    """Return one past the maximum existing sort_order under *parent_id*."""
    q = ManuscriptSection.query.filter_by(
        manuscript_id=manuscript_id, parent_id=parent_id
    )
    last = q.order_by(ManuscriptSection.sort_order.desc()).first()
    return (last.sort_order + 1) if last else 0


def create_section(
    manuscript: Manuscript,
    *,
    title: str = "Untitled Section",
    parent_id: Optional[int] = None,
    content: str = "",
    status: str = ManuscriptSection.STATUS_DRAFT,
    synopsis: str = "",
) -> ManuscriptSection:
    """Append a new section to *manuscript* (or under *parent_id*)."""
    if status not in ManuscriptSection.STATUS_VALUES:
        status = ManuscriptSection.STATUS_DRAFT

    # Validate parent belongs to same manuscript
    if parent_id is not None:
        parent = ManuscriptSection.query.filter_by(
            id=parent_id, manuscript_id=manuscript.id
        ).first()
        if parent is None:
            parent_id = None

    sort_order = _next_sort_order(manuscript.id, parent_id)
    section = ManuscriptSection(
        manuscript_id=manuscript.id,
        parent_id=parent_id,
        sort_order=sort_order,
        title=title.strip() or "Untitled Section",
        content=content,
        status=status,
        synopsis=synopsis,
        linked_reference_ids_json="[]",
    )
    db.session.add(section)
    db.session.commit()
    return section


def get_section(
    section_id: int, manuscript_id: int
) -> Optional[ManuscriptSection]:
    return ManuscriptSection.query.filter_by(
        id=section_id, manuscript_id=manuscript_id
    ).first()


def update_section(section: ManuscriptSection, data: Dict[str, Any]) -> ManuscriptSection:
    """Apply *data* dict to *section*; commit and return."""
    if "title" in data and data["title"]:
        section.title = data["title"].strip()
    if "content" in data:
        section.content = data["content"]
    if "status" in data and data["status"] in ManuscriptSection.STATUS_VALUES:
        section.status = data["status"]
    if "synopsis" in data:
        section.synopsis = data["synopsis"]
    if "linked_reference_ids" in data:
        ids = data["linked_reference_ids"]
        if isinstance(ids, list):
            section.set_linked_reference_ids(ids)
    db.session.commit()
    return section


def delete_section(section: ManuscriptSection) -> None:
    db.session.delete(section)
    db.session.commit()


# ---------------------------------------------------------------------------
# Reorder
# ---------------------------------------------------------------------------

def reorder_sections(
    manuscript: Manuscript, ordered_ids: List[int]
) -> List[ManuscriptSection]:
    """Set sort_order on top-level sections to match *ordered_ids*.

    Only sibling sections (parent_id=None) are considered; pass a flat list
    of IDs in the desired display order.  Returns the updated sections.
    """
    sections_by_id: Dict[int, ManuscriptSection] = {
        s.id: s
        for s in ManuscriptSection.query.filter_by(
            manuscript_id=manuscript.id, parent_id=None
        ).all()
    }
    updated: List[ManuscriptSection] = []
    for position, sid in enumerate(ordered_ids):
        section = sections_by_id.get(int(sid))
        if section is None:
            continue
        section.sort_order = position
        updated.append(section)
    db.session.commit()
    return updated


def reorder_children(
    parent_section: ManuscriptSection, ordered_ids: List[int]
) -> List[ManuscriptSection]:
    """Reorder child sections of *parent_section*."""
    children_by_id: Dict[int, ManuscriptSection] = {
        s.id: s for s in parent_section.children
    }
    updated: List[ManuscriptSection] = []
    for position, sid in enumerate(ordered_ids):
        section = children_by_id.get(int(sid))
        if section is None:
            continue
        section.sort_order = position
        updated.append(section)
    db.session.commit()
    return updated


# ---------------------------------------------------------------------------
# Markdown export
# ---------------------------------------------------------------------------

def export_manuscript_markdown(manuscript: Manuscript) -> str:
    """Merge all sections top-down into a single Markdown string."""
    lines: List[str] = [f"# {manuscript.title}", ""]

    def _render(sections: List[ManuscriptSection], depth: int = 2) -> None:
        heading = "#" * min(depth, 6)
        for section in sorted(sections, key=lambda s: s.sort_order):
            lines.append(f"{heading} {section.title}")
            lines.append("")
            if section.content:
                lines.append(section.content.strip())
                lines.append("")
            for child in sorted(section.children, key=lambda s: s.sort_order):
                child_heading = "#" * min(depth + 1, 6)
                lines.append(f"{child_heading} {child.title}")
                lines.append("")
                if child.content:
                    lines.append(child.content.strip())
                    lines.append("")

    top_level = [s for s in manuscript.sections if s.parent_id is None]
    _render(top_level, depth=2)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section list helper
# ---------------------------------------------------------------------------

def list_sections_tree(manuscript: Manuscript) -> List[Dict[str, Any]]:
    """Return a flat list of top-level sections with nested ``children`` dicts."""
    top_level = [s for s in manuscript.sections if s.parent_id is None]
    result = []
    for s in sorted(top_level, key=lambda x: x.sort_order):
        d = s.to_dict(include_content=False)
        d["children"] = [
            c.to_dict(include_content=False)
            for c in sorted(s.children, key=lambda x: x.sort_order)
        ]
        result.append(d)
    return result
