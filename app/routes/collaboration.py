"""Phase 3: Collaboration — shared projects, comments."""
from flask import Blueprint, request, jsonify

from app.database import db
from app.models.researcher import ResearchProject, ProjectMember, ProjectComment
from app.models.core import User
from app.routes.route_entity_lookup import get_entity, get_entity_or_404

collab_bp = Blueprint('collaboration', __name__)


def _get_project_or_404(project_id):
    return get_entity_or_404(ResearchProject, project_id)


@collab_bp.route('/<int:project_id>/members', methods=['GET'])
def list_members(project_id):
    project = _get_project_or_404(project_id)
    members = ProjectMember.query.filter_by(project_id=project.id).all()
    out = []
    for m in members:
        u = get_entity(User, m.user_id)
        out.append({
            'id': m.id, 'user_id': m.user_id, 'username': u.username if u else '?',
            'role': m.role, 'created_at': m.created_at.isoformat() if m.created_at else None,
        })
    owner = get_entity(User, project.owner_id)
    out.insert(0, {'user_id': project.owner_id, 'username': owner.username if owner else '?', 'role': 'owner'})
    return jsonify({'members': out})


@collab_bp.route('/<int:project_id>/members', methods=['POST'])
def add_member(project_id):
    project = _get_project_or_404(project_id)
    data = request.get_json() or {}
    user_id = data.get('user_id')
    role = (data.get('role') or 'viewer').lower()

    if not user_id:
        return jsonify({'error': 'user_id required'}), 400
    if role not in ('viewer', 'contributor', 'admin'):
        return jsonify({'error': 'role must be viewer|contributor|admin'}), 400

    existing = ProjectMember.query.filter_by(project_id=project.id, user_id=user_id).first()
    if existing:
        existing.role = role
        db.session.commit()
        return jsonify({'id': existing.id, 'user_id': existing.user_id, 'role': existing.role})

    m = ProjectMember(project_id=project.id, user_id=user_id, role=role)
    db.session.add(m)
    db.session.commit()
    return jsonify({'id': m.id, 'user_id': m.user_id, 'role': m.role}), 201


@collab_bp.route('/<int:project_id>/members/<int:member_id>', methods=['DELETE'])
def remove_member(project_id, member_id):
    project = _get_project_or_404(project_id)
    m = ProjectMember.query.filter_by(project_id=project.id, id=member_id).first_or_404()
    db.session.delete(m)
    db.session.commit()
    return jsonify({'ok': True}), 204


def _comment_to_dict(c):
    u = get_entity(User, c.user_id) if c.user_id else None
    return {
        'id': c.id,
        'content': c.content,
        'document_id': c.document_id,
        'manuscript_section_id': getattr(c, 'manuscript_section_id', None),
        'parent_id': getattr(c, 'parent_id', None),
        'mentions': getattr(c, 'mentions_json', None) or [],
        'username': u.username if u else 'Anonymous',
        'resolved': getattr(c, 'resolved_at', None) is not None,
        'resolved_at': c.resolved_at.isoformat() if getattr(c, 'resolved_at', None) else None,
        'reply_count': c.replies.count() if hasattr(c, 'replies') else 0,
        'created_at': c.created_at.isoformat() if c.created_at else None,
        'updated_at': c.updated_at.isoformat() if getattr(c, 'updated_at', None) else None,
    }


@collab_bp.route('/<int:project_id>/comments', methods=['GET'])
def list_comments(project_id):
    project = _get_project_or_404(project_id)
    # Only return top-level comments (not replies) by default
    doc_id = request.args.get('document_id', type=int)
    section_id = request.args.get('section_id', type=int)
    include_resolved = request.args.get('include_resolved', '1') != '0'
    q = ProjectComment.query.filter_by(project_id=project.id, parent_id=None)
    if doc_id is not None:
        q = q.filter_by(document_id=doc_id)
    if section_id is not None:
        q = q.filter_by(manuscript_section_id=section_id)
    if not include_resolved:
        q = q.filter(ProjectComment.resolved_at.is_(None))
    comments = q.order_by(ProjectComment.created_at.desc()).limit(100).all()
    return jsonify({'comments': [_comment_to_dict(c) for c in comments]})


@collab_bp.route('/<int:project_id>/comments', methods=['POST'])
def add_comment(project_id):
    project = _get_project_or_404(project_id)
    data = request.get_json() or {}
    content = (data.get('content') or '').strip()

    if not content:
        return jsonify({'error': 'content required'}), 400

    parent_id = data.get('parent_id')
    if parent_id:
        # Validate parent exists and belongs to same project
        parent = ProjectComment.query.filter_by(id=parent_id, project_id=project.id).first_or_404()

    c = ProjectComment(
        project_id=project.id,
        user_id=data.get('user_id'),
        content=content,
        document_id=data.get('document_id'),
        manuscript_section_id=data.get('manuscript_section_id'),
        parent_id=parent_id,
        mentions_json=data.get('mentions', []),
    )
    db.session.add(c)
    db.session.commit()
    return jsonify(_comment_to_dict(c)), 201


@collab_bp.route('/<int:project_id>/comments/<int:comment_id>', methods=['GET'])
def get_comment(project_id, comment_id):
    project = _get_project_or_404(project_id)
    c = ProjectComment.query.filter_by(id=comment_id, project_id=project.id).first_or_404()
    d = _comment_to_dict(c)
    # Include immediate replies
    replies = ProjectComment.query.filter_by(parent_id=c.id).order_by(ProjectComment.created_at).all()
    d['replies'] = [_comment_to_dict(r) for r in replies]
    return jsonify(d)


@collab_bp.route('/<int:project_id>/comments/<int:comment_id>', methods=['PUT'])
def edit_comment(project_id, comment_id):
    project = _get_project_or_404(project_id)
    c = ProjectComment.query.filter_by(id=comment_id, project_id=project.id).first_or_404()
    data = request.get_json() or {}
    content = (data.get('content') or '').strip()
    if not content:
        return jsonify({'error': 'content required'}), 400
    c.content = content
    if 'mentions' in data:
        c.mentions_json = data['mentions']
    db.session.commit()
    return jsonify(_comment_to_dict(c))


@collab_bp.route('/<int:project_id>/comments/<int:comment_id>', methods=['DELETE'])
def delete_comment(project_id, comment_id):
    project = _get_project_or_404(project_id)
    c = ProjectComment.query.filter_by(id=comment_id, project_id=project.id).first_or_404()
    db.session.delete(c)
    db.session.commit()
    return jsonify({'ok': True}), 204


@collab_bp.route('/<int:project_id>/comments/<int:comment_id>/resolve', methods=['POST'])
def resolve_comment(project_id, comment_id):
    """Toggle resolved state on a comment thread.

    Request body::

        {"resolved": true}
    """
    project = _get_project_or_404(project_id)
    c = ProjectComment.query.filter_by(id=comment_id, project_id=project.id).first_or_404()
    data = request.get_json() or {}
    resolved = bool(data.get('resolved', True))
    from app.core.time_utils import utcnow_naive
    c.resolved_at = utcnow_naive() if resolved else None
    db.session.commit()
    return jsonify(_comment_to_dict(c))


# ===========================================================================
# Submission checklist
# ===========================================================================


@collab_bp.route('/<int:project_id>/submission-checklist', methods=['GET'])
def get_checklist(project_id):
    """Return the project submission checklist."""
    project = _get_project_or_404(project_id)
    from app.services.collaboration_service import get_submission_checklist
    return jsonify({'checklist': get_submission_checklist(project)})


@collab_bp.route('/<int:project_id>/submission-checklist', methods=['PUT'])
def save_checklist(project_id):
    """Save the full checklist state (replaces current)."""
    project = _get_project_or_404(project_id)
    data = request.get_json() or {}
    from app.services.collaboration_service import save_submission_checklist
    state = save_submission_checklist(project, data)
    return jsonify({'checklist': state})
