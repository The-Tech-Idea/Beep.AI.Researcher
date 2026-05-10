"""Code CRUD + coded reference routes."""

from flask import Blueprint, request, jsonify
from flask_login import login_required

from app.database import db
from app.models.researcher import (
    ResearchProject,
    Code,
    CodedReference,
    ResearcherDocument,
)
from app.decorators.permissions import require_permission
from app.routes.route_entity_lookup import (
    get_entity,
    get_entity_or_404,
    get_project_or_404,
)

codes_bp = Blueprint("codes", __name__)


@codes_bp.route("/<int:project_id>/codes", methods=["GET"])
@login_required
def list_codes(project_id):
    project = get_project_or_404(project_id)
    codes = Code.query.filter_by(project_id=project.id, parent_id=None).all()
    out = []
    for c in codes:
        ref_count = CodedReference.query.filter_by(code_id=c.id).count()
        out.append(
            {
                **code_to_dict(c),
                "reference_count": ref_count,
                "children": [code_to_dict(ch) for ch in c.children],
            }
        )
    return jsonify({"codes": out})


@codes_bp.route("/<int:project_id>/codes", methods=["POST"])
@login_required
def create_code(project_id):
    project = get_project_or_404(project_id)
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400

    code = Code(
        project_id=project.id,
        name=name,
        description=data.get("description", ""),
        parent_id=data.get("parent_id"),
        color=data.get("color", "#6366f1"),
    )
    try:
        db.session.add(code)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to create code"}), 500
    return jsonify(code_to_dict(code)), 201


@codes_bp.route("/<int:project_id>/codes/<int:code_id>", methods=["PUT"])
@login_required
def update_code(project_id, code_id):
    project = get_project_or_404(project_id)
    code = Code.query.filter_by(project_id=project.id, id=code_id).first_or_404()
    data = request.get_json() or {}
    if "name" in data:
        code.name = (data["name"] or "").strip() or code.name
    if "description" in data:
        code.description = data["description"]
    if "color" in data:
        code.color = data["color"]
    if "parent_id" in data:
        code.parent_id = data["parent_id"]
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to update code"}), 500
    return jsonify(code_to_dict(code))


@codes_bp.route("/<int:project_id>/codes/<int:code_id>", methods=["DELETE"])
@login_required
def delete_code(project_id, code_id):
    project = get_project_or_404(project_id)
    code = Code.query.filter_by(project_id=project.id, id=code_id).first_or_404()
    try:
        db.session.delete(code)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to delete code"}), 500
    return jsonify({"ok": True}), 204


@codes_bp.route("/<int:project_id>/code", methods=["POST"])
@login_required
def apply_code(project_id):
    project = get_project_or_404(project_id)
    data = request.get_json() or {}
    code_id = data.get("code_id")
    document_id = data.get("document_id")
    chunk_id = data.get("chunk_id", "chunk-0")
    start_offset = data.get("start_offset", 0)
    end_offset = data.get("end_offset", 0)

    if not code_id or not document_id:
        return jsonify({"error": "code_id and document_id required"}), 400

    doc = ResearcherDocument.query.filter_by(
        project_id=project.id, id=document_id
    ).first_or_404()
    code = Code.query.filter_by(project_id=project.id, id=code_id).first_or_404()

    ref = CodedReference(
        code_id=code.id,
        document_id=doc.id,
        chunk_id=chunk_id,
        start_offset=start_offset,
        end_offset=end_offset,
        memo=data.get("memo", ""),
    )
    try:
        db.session.add(ref)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to apply code"}), 500
    return jsonify(
        {"id": ref.id, "code_id": ref.code_id, "document_id": ref.document_id}
    ), 201


@codes_bp.route("/<int:project_id>/code/<int:ref_id>", methods=["DELETE"])
@login_required
def remove_code(project_id, ref_id):
    project = get_project_or_404(project_id)
    ref = (
        CodedReference.query.join(Code)
        .filter(Code.project_id == project.id, CodedReference.id == ref_id)
        .first_or_404()
    )
    try:
        db.session.delete(ref)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to remove code"}), 500
    return jsonify({"ok": True}), 204


@codes_bp.route("/<int:project_id>/codes/<int:code_id>/references", methods=["GET"])
@login_required
def list_references(project_id, code_id):
    project = get_project_or_404(project_id)
    code = Code.query.filter_by(project_id=project.id, id=code_id).first_or_404()
    refs = CodedReference.query.filter_by(code_id=code.id).all()
    out = []
    for r in refs:
        doc = get_entity(ResearcherDocument, r.document_id)
        snippet = ""
        if doc and doc.text_content:
            text = doc.text_content
            start = max(0, r.start_offset - 20)
            end = min(len(text), r.end_offset + 20)
            snippet = text[start:end].replace("\n", " ")
        out.append(
            {
                "id": r.id,
                "document_id": r.document_id,
                "filename": doc.filename if doc else None,
                "chunk_id": r.chunk_id,
                "start_offset": r.start_offset,
                "end_offset": r.end_offset,
                "snippet": snippet,
                "memo": r.memo,
            }
        )
    return jsonify({"references": out})


def code_to_dict(c):
    return {
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "parent_id": c.parent_id,
        "color": c.color,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
