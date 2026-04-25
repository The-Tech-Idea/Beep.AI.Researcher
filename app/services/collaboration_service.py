"""Collaboration service — section-anchored comment CRUD (Phase 05)."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.database import db
from app.core.time_utils import utcnow_naive
from app.models.researcher.researcher_projects import ProjectComment


# ---------------------------------------------------------------------------
# Comment CRUD
# ---------------------------------------------------------------------------

def _comment_to_dict(comment: ProjectComment) -> Dict[str, Any]:
    return {
        "id": comment.id,
        "project_id": comment.project_id,
        "manuscript_section_id": comment.manuscript_section_id,
        "document_id": comment.document_id,
        "parent_id": comment.parent_id,
        "user_id": comment.user_id,
        "content": comment.content,
        "mentions": comment.mentions_json or [],
        "resolved": comment.resolved_at is not None,
        "resolved_at": comment.resolved_at.isoformat() if comment.resolved_at else None,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
    }


def create_comment(
    project,
    body: str,
    *,
    user_id: Optional[int] = None,
    manuscript_section_id: Optional[int] = None,
    document_id: Optional[int] = None,
    parent_id: Optional[int] = None,
    mentions: Optional[List[Dict]] = None,
) -> ProjectComment:
    """Create and commit a new comment on a project (optionally anchored to a section)."""
    comment = ProjectComment(
        project_id=project.id,
        user_id=user_id,
        content=body.strip(),
        manuscript_section_id=manuscript_section_id,
        document_id=document_id,
        parent_id=parent_id,
        mentions_json=mentions or [],
    )
    db.session.add(comment)
    db.session.commit()
    return comment


def get_comment(comment_id: int, project_id: int) -> Optional[ProjectComment]:
    return ProjectComment.query.filter_by(id=comment_id, project_id=project_id).first()


def list_comments(
    project_id: int,
    *,
    manuscript_section_id: Optional[int] = None,
    document_id: Optional[int] = None,
    include_resolved: bool = True,
) -> List[ProjectComment]:
    """Return top-level comments (no parent) ordered by creation time."""
    q = ProjectComment.query.filter_by(project_id=project_id, parent_id=None)
    if manuscript_section_id is not None:
        q = q.filter_by(manuscript_section_id=manuscript_section_id)
    if document_id is not None:
        q = q.filter_by(document_id=document_id)
    if not include_resolved:
        q = q.filter(ProjectComment.resolved_at.is_(None))
    return q.order_by(ProjectComment.created_at).all()


def list_replies(comment_id: int) -> List[ProjectComment]:
    return (
        ProjectComment.query.filter_by(parent_id=comment_id)
        .order_by(ProjectComment.created_at)
        .all()
    )


def update_comment(comment: ProjectComment, body: str) -> ProjectComment:
    comment.content = body.strip()
    db.session.commit()
    return comment


def resolve_comment(comment: ProjectComment) -> ProjectComment:
    comment.resolved_at = utcnow_naive()
    db.session.commit()
    return comment


def unresolve_comment(comment: ProjectComment) -> ProjectComment:
    comment.resolved_at = None
    db.session.commit()
    return comment


def delete_comment(comment: ProjectComment) -> None:
    db.session.delete(comment)
    db.session.commit()


def comment_to_dict(comment: ProjectComment) -> Dict[str, Any]:
    return _comment_to_dict(comment)


def thread_to_dict(comment: ProjectComment) -> Dict[str, Any]:
    """Return a comment with its immediate replies."""
    data = _comment_to_dict(comment)
    data["replies"] = [_comment_to_dict(r) for r in list_replies(comment.id)]
    return data


# ---------------------------------------------------------------------------
# Submission checklist
# ---------------------------------------------------------------------------

_DEFAULT_CHECKLIST_STEPS = [
    "authorship",
    "ethics",
    "data_availability",
    "conflicts_of_interest",
    "funding",
    "cover_letter",
]


def get_submission_checklist(project) -> Dict[str, Any]:
    """Return the checklist state for *project*, initialising missing steps."""
    raw = project.submission_checklist_json
    try:
        state = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        state = {}
    # Ensure all default steps are present
    for step in _DEFAULT_CHECKLIST_STEPS:
        if step not in state:
            state[step] = {"checked": False, "note": ""}
    return state


def save_submission_checklist(project, state: Dict[str, Any]) -> Dict[str, Any]:
    """Persist *state* dict to *project.submission_checklist_json* and commit."""
    # Only keep known string-keyed entries with checked/note
    cleaned = {}
    for key, val in state.items():
        if isinstance(key, str) and isinstance(val, dict):
            cleaned[key] = {
                "checked": bool(val.get("checked", False)),
                "note": str(val.get("note", "")),
            }
    project.submission_checklist_json = json.dumps(cleaned)
    db.session.commit()
    return cleaned
