"""Document annotation routes."""

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.models.researcher import ResearchProject, ResearcherDocument
from app.routes.route_entity_lookup import get_entity_or_404, get_project_or_404
from app.services.document_annotation_service import (
    DocumentAnnotationValidationError,
    create_document_annotation,
    delete_document_annotation,
    list_document_annotations,
)

annotations_bp = Blueprint("annotations", __name__)


def _get_document_or_404(project_id, doc_id):
    project = get_project_or_404(project_id)
    return ResearcherDocument.query.filter_by(
        project_id=project.id,
        id=doc_id,
    ).first_or_404()


@annotations_bp.route(
    "/<int:project_id>/documents/<int:doc_id>/annotations", methods=["GET"]
)
@login_required
def list_annotations(project_id, doc_id):
    document = _get_document_or_404(project_id, doc_id)
    return jsonify({"annotations": list_document_annotations(document)})


@annotations_bp.route(
    "/<int:project_id>/documents/<int:doc_id>/annotations", methods=["POST"]
)
@login_required
def add_annotation(project_id, doc_id):
    document = _get_document_or_404(project_id, doc_id)
    payload = request.get_json(silent=True) or {}
    try:
        annotation = create_document_annotation(
            document,
            created_by_id=getattr(current_user, "id", None),
            chunk_id=payload.get("chunk_id"),
            start_offset=payload.get("start_offset"),
            end_offset=payload.get("end_offset"),
            note=payload.get("note"),
            highlight_color=payload.get("highlight_color"),
        )
    except DocumentAnnotationValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(annotation), 201


@annotations_bp.route(
    "/<int:project_id>/documents/<int:doc_id>/annotations/<int:ann_id>",
    methods=["DELETE"],
)
@login_required
def delete_annotation(project_id, doc_id, ann_id):
    document = _get_document_or_404(project_id, doc_id)
    deleted = delete_document_annotation(document, ann_id)
    if not deleted:
        return jsonify({"error": "annotation not found"}), 404
    return jsonify({"ok": True}), 200
