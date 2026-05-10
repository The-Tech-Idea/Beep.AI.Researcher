"""Manuscript routes — binder CRUD, section reorder, and Markdown export (Phase 04)."""

from __future__ import annotations

from flask import Blueprint, jsonify, request, make_response
from flask_login import current_user, login_required

from app.routes.route_entity_lookup import get_entity_or_404, get_project_or_404
from app.models.researcher import ResearchProject

manuscripts_bp = Blueprint("manuscripts", __name__)


def _auth_project(project: ResearchProject):
    if project.owner_id != current_user.id:
        return jsonify({"error": "Not authorized"}), 403
    return None


# ===========================================================================
# Manuscripts
# ===========================================================================


@manuscripts_bp.route("/projects/<int:project_id>/manuscripts", methods=["GET"])
@login_required
def list_manuscripts(project_id: int):
    """List all manuscripts for the project.

    Response::

        {"manuscripts": [{"id": 1, "title": "...", "section_count": 5, ...}]}
    """
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    from app.services.manuscript_service import list_manuscripts as svc_list

    manuscripts = svc_list(project_id)
    return jsonify({"manuscripts": [m.to_dict() for m in manuscripts]})


@manuscripts_bp.route("/projects/<int:project_id>/manuscripts", methods=["POST"])
@login_required
def create_manuscript(project_id: int):
    """Create a new manuscript.

    Request body::

        {"title": "My Thesis"}

    Response: manuscript dict, 201.
    """
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    data = request.get_json() or {}
    title = (data.get("title") or "Untitled Manuscript").strip()

    from app.services.manuscript_service import create_manuscript as svc_create

    manuscript = svc_create(project, title)
    return jsonify(manuscript.to_dict()), 201


@manuscripts_bp.route(
    "/projects/<int:project_id>/manuscripts/<int:manuscript_id>", methods=["GET"]
)
@login_required
def get_manuscript(project_id: int, manuscript_id: int):
    """Get manuscript detail with sections tree (content excluded for speed)."""
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    from app.services.manuscript_service import (
        get_manuscript as svc_get,
        list_sections_tree,
    )

    manuscript = svc_get(manuscript_id, project_id)
    if manuscript is None:
        return jsonify({"error": "Manuscript not found"}), 404

    data = manuscript.to_dict()
    data["sections"] = list_sections_tree(manuscript)
    return jsonify(data)


@manuscripts_bp.route(
    "/projects/<int:project_id>/manuscripts/<int:manuscript_id>", methods=["PATCH"]
)
@login_required
def update_manuscript(project_id: int, manuscript_id: int):
    """Rename a manuscript.

    Request body::

        {"title": "New Title"}
    """
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    from app.services.manuscript_service import (
        get_manuscript as svc_get,
        update_manuscript_title,
    )

    manuscript = svc_get(manuscript_id, project_id)
    if manuscript is None:
        return jsonify({"error": "Manuscript not found"}), 404

    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400

    manuscript = update_manuscript_title(manuscript, title)
    return jsonify(manuscript.to_dict())


@manuscripts_bp.route(
    "/projects/<int:project_id>/manuscripts/<int:manuscript_id>", methods=["DELETE"]
)
@login_required
def delete_manuscript(project_id: int, manuscript_id: int):
    """Delete a manuscript and all its sections."""
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    from app.services.manuscript_service import (
        get_manuscript as svc_get,
        delete_manuscript as svc_delete,
    )

    manuscript = svc_get(manuscript_id, project_id)
    if manuscript is None:
        return jsonify({"error": "Manuscript not found"}), 404

    svc_delete(manuscript)
    return jsonify({"ok": True})


@manuscripts_bp.route(
    "/projects/<int:project_id>/manuscripts/<int:manuscript_id>/export",
    methods=["GET"],
)
@login_required
def export_manuscript(project_id: int, manuscript_id: int):
    """Export the full manuscript as a Markdown file download."""
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    from app.services.manuscript_service import (
        get_manuscript as svc_get,
        export_manuscript_markdown,
    )

    manuscript = svc_get(manuscript_id, project_id)
    if manuscript is None:
        return jsonify({"error": "Manuscript not found"}), 404

    md_text = export_manuscript_markdown(manuscript)
    safe_title = "".join(
        c if c.isalnum() or c in " _-" else "-" for c in manuscript.title
    )
    filename = f"{safe_title[:80]}.md"
    response = make_response(md_text)
    response.headers["Content-Type"] = "text/markdown; charset=utf-8"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# ===========================================================================
# Sections
# ===========================================================================


def _get_manuscript_or_404(manuscript_id: int, project_id: int):
    from app.services.manuscript_service import get_manuscript as svc_get

    manuscript = svc_get(manuscript_id, project_id)
    if manuscript is None:
        from flask import abort

        abort(404)
    return manuscript


@manuscripts_bp.route(
    "/projects/<int:project_id>/manuscripts/<int:manuscript_id>/sections",
    methods=["POST"],
)
@login_required
def create_section(project_id: int, manuscript_id: int):
    """Create a new section in the manuscript.

    Request body::

        {
            "title": "Introduction",
            "parent_id": null,
            "content": "",
            "status": "draft",
            "synopsis": ""
        }
    """
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    manuscript = _get_manuscript_or_404(manuscript_id, project_id)
    data = request.get_json() or {}

    from app.services.manuscript_service import create_section as svc_create

    section = svc_create(
        manuscript,
        title=data.get("title", "Untitled Section"),
        parent_id=data.get("parent_id"),
        content=data.get("content", ""),
        status=data.get("status", "draft"),
        synopsis=data.get("synopsis", ""),
    )
    return jsonify(section.to_dict()), 201


@manuscripts_bp.route(
    "/projects/<int:project_id>/manuscripts/<int:manuscript_id>/sections/<int:section_id>",
    methods=["GET"],
)
@login_required
def get_section(project_id: int, manuscript_id: int, section_id: int):
    """Return a single section including full content."""
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    _get_manuscript_or_404(manuscript_id, project_id)

    from app.services.manuscript_service import get_section as svc_get

    section = svc_get(section_id, manuscript_id)
    if section is None:
        return jsonify({"error": "Section not found"}), 404
    return jsonify(section.to_dict(include_content=True))


@manuscripts_bp.route(
    "/projects/<int:project_id>/manuscripts/<int:manuscript_id>/sections/<int:section_id>",
    methods=["PATCH"],
)
@login_required
def update_section(project_id: int, manuscript_id: int, section_id: int):
    """Partial update on a section (title, content, status, synopsis, linked_reference_ids)."""
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    _get_manuscript_or_404(manuscript_id, project_id)

    from app.services.manuscript_service import (
        get_section as svc_get,
        update_section as svc_update,
    )

    section = svc_get(section_id, manuscript_id)
    if section is None:
        return jsonify({"error": "Section not found"}), 404

    data = request.get_json() or {}
    section = svc_update(section, data)
    return jsonify(section.to_dict(include_content=True))


@manuscripts_bp.route(
    "/projects/<int:project_id>/manuscripts/<int:manuscript_id>/sections/<int:section_id>",
    methods=["DELETE"],
)
@login_required
def delete_section(project_id: int, manuscript_id: int, section_id: int):
    """Delete a section (and its children, via cascade)."""
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    _get_manuscript_or_404(manuscript_id, project_id)

    from app.services.manuscript_service import (
        get_section as svc_get,
        delete_section as svc_delete,
    )

    section = svc_get(section_id, manuscript_id)
    if section is None:
        return jsonify({"error": "Section not found"}), 404

    svc_delete(section)
    return jsonify({"ok": True})


@manuscripts_bp.route(
    "/projects/<int:project_id>/manuscripts/<int:manuscript_id>/sections/reorder",
    methods=["POST"],
)
@login_required
def reorder_sections(project_id: int, manuscript_id: int):
    """Reorder top-level sections of the manuscript.

    Request body::

        {"ordered_ids": [3, 1, 2]}   // section IDs in new order
    """
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    manuscript = _get_manuscript_or_404(manuscript_id, project_id)
    data = request.get_json() or {}
    ordered_ids = data.get("ordered_ids") or []
    if not isinstance(ordered_ids, list):
        return jsonify({"error": "ordered_ids must be a list"}), 400

    from app.services.manuscript_service import reorder_sections as svc_reorder

    updated = svc_reorder(manuscript, ordered_ids)
    return jsonify({"ok": True, "updated": [s.id for s in updated]})


@manuscripts_bp.route(
    "/projects/<int:project_id>/manuscripts/<int:manuscript_id>/sections/<int:section_id>/reorder-children",
    methods=["POST"],
)
@login_required
def reorder_children(project_id: int, manuscript_id: int, section_id: int):
    """Reorder child sections of a parent section.

    Request body::

        {"ordered_ids": [7, 5, 6]}
    """
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    _get_manuscript_or_404(manuscript_id, project_id)

    from app.services.manuscript_service import (
        get_section as svc_get,
        reorder_children as svc_reorder_children,
    )

    parent = svc_get(section_id, manuscript_id)
    if parent is None:
        return jsonify({"error": "Section not found"}), 404

    data = request.get_json() or {}
    ordered_ids = data.get("ordered_ids") or []
    if not isinstance(ordered_ids, list):
        return jsonify({"error": "ordered_ids must be a list"}), 400

    updated = svc_reorder_children(parent, ordered_ids)
    return jsonify({"ok": True, "updated": [s.id for s in updated]})


# ===========================================================================
# Phase 4 — Writing Assistant Routes
# ===========================================================================


@manuscripts_bp.route(
    "/projects/<int:project_id>/manuscripts/<int:manuscript_id>/sections/<int:section_id>/readability",
    methods=["GET"],
)
@login_required
def section_readability(project_id: int, manuscript_id: int, section_id: int):
    """Return readability metrics for a manuscript section."""
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    from app.models.researcher import Manuscript, ManuscriptSection
    from app.services.readability_service import ReadabilityService

    manuscript = Manuscript.query.filter_by(
        id=manuscript_id, project_id=project_id
    ).first()
    if manuscript is None:
        return jsonify({"error": "Manuscript not found"}), 404

    section = ManuscriptSection.query.filter_by(
        id=section_id, manuscript_id=manuscript_id
    ).first()
    if section is None:
        return jsonify({"error": "Section not found"}), 404

    result = ReadabilityService().analyse(section.content or "", use_cache=True)
    return jsonify(result)


@manuscripts_bp.route(
    "/projects/<int:project_id>/manuscripts/<int:manuscript_id>/sections/<int:section_id>/apply-fix",
    methods=["POST"],
)
@login_required
def apply_fix(project_id: int, manuscript_id: int, section_id: int):
    """Apply a single writing fix to a manuscript section.

    Request body::

        {"issue": {"offset": 12, "length": 13, "suggestion": "found"}}
    """
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    from app.models.researcher import Manuscript, ManuscriptSection
    from app.services.writing_quality_service import WritingQualityService

    manuscript = Manuscript.query.filter_by(
        id=manuscript_id, project_id=project_id
    ).first()
    if manuscript is None:
        return jsonify({"error": "Manuscript not found"}), 404

    section = ManuscriptSection.query.filter_by(
        id=section_id, manuscript_id=manuscript_id
    ).first()
    if section is None:
        return jsonify({"error": "Section not found"}), 404

    data = request.get_json() or {}
    issue = data.get("issue")
    if not issue:
        return jsonify({"error": "issue object required"}), 400

    patched = WritingQualityService().apply_fix(section.content or "", issue)
    if patched is None:
        return jsonify(
            {"error": "Could not apply fix — invalid offset or suggestion"}
        ), 400

    section.content = patched
    from app.database import db

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to apply fix"}), 500

    return jsonify({"ok": True, "content": patched})


@manuscripts_bp.route(
    "/projects/<int:project_id>/manuscripts/<int:manuscript_id>/sections/<int:section_id>/citation-draft",
    methods=["POST"],
)
@login_required
def citation_draft(project_id: int, manuscript_id: int, section_id: int):
    """Generate a themed paragraph draft with inline citation markers.

    Request body::

        {"theme": "Impact of X on Y"}
    """
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    from app.models.researcher import Manuscript, ManuscriptSection, Reference
    from app.services.citation_draft_service import CitationDraftService

    manuscript = Manuscript.query.filter_by(
        id=manuscript_id, project_id=project_id
    ).first()
    if manuscript is None:
        return jsonify({"error": "Manuscript not found"}), 404

    section = ManuscriptSection.query.filter_by(
        id=section_id, manuscript_id=manuscript_id
    ).first()
    if section is None:
        return jsonify({"error": "Section not found"}), 404

    data = request.get_json() or {}
    theme = (data.get("theme") or "").strip()
    if not theme:
        return jsonify({"error": "theme is required"}), 400

    # Gather project references as sources
    references = Reference.query.filter_by(project_id=project_id).all()
    sources = [
        {
            "doi": r.doi or "",
            "title": r.title or "",
            "abstract": r.abstract or "",
        }
        for r in references
        if r.doi or r.title
    ][:20]

    if not sources:
        return jsonify(
            {"error": "No references with DOI or title in this project"}
        ), 400

    payload, status_code = CitationDraftService().draft(theme, sources)
    return jsonify(payload), status_code


@manuscripts_bp.route(
    "/projects/<int:project_id>/manuscripts/<int:manuscript_id>/sections/<int:section_id>/insert-draft",
    methods=["POST"],
)
@login_required
def insert_draft(project_id: int, manuscript_id: int, section_id: int):
    """Insert a generated draft into the section content.

    Request body::

        {"draft": "The paragraph text…"}
    """
    project = get_project_or_404(project_id)
    denied = _auth_project(project)
    if denied:
        return denied

    from app.models.researcher import Manuscript, ManuscriptSection

    manuscript = Manuscript.query.filter_by(
        id=manuscript_id, project_id=project_id
    ).first()
    if manuscript is None:
        return jsonify({"error": "Manuscript not found"}), 404

    section = ManuscriptSection.query.filter_by(
        id=section_id, manuscript_id=manuscript_id
    ).first()
    if section is None:
        return jsonify({"error": "Section not found"}), 404

    data = request.get_json() or {}
    draft = (data.get("draft") or "").strip()
    if not draft:
        return jsonify({"error": "draft text is required"}), 400

    # Append draft to existing content
    existing = section.content or ""
    section.content = (existing + "\n\n" + draft).strip() if existing else draft

    from app.database import db

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to insert draft"}), 500

    return jsonify({"ok": True, "content": section.content})
