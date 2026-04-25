"""Litmaps-style: Document/theme network map."""
from flask import Blueprint, request, jsonify

from app.models.researcher import (
    ResearchProject, ResearcherDocument, Code, CodedReference
)
from app.routes.route_entity_lookup import get_entity_or_404

document_map_bp = Blueprint('document_map', __name__)


def _get_project_or_404(project_id):
    return get_entity_or_404(ResearchProject, project_id)


@document_map_bp.route('/<int:project_id>/map', methods=['GET'])
def get_map(project_id):
    """Document/theme network graph. Nodes: docs + codes. Edges: code-doc links."""
    project = _get_project_or_404(project_id)

    docs = ResearcherDocument.query.filter_by(project_id=project.id).all()
    codes = Code.query.filter_by(project_id=project.id).all()

    nodes = []
    node_ids = {}

    for d in docs:
        nid = f'doc-{d.id}'
        node_ids[nid] = len(nodes)
        nodes.append({'id': nid, 'label': d.filename, 'type': 'document'})

    for c in codes:
        nid = f'code-{c.id}'
        node_ids[nid] = len(nodes)
        nodes.append({'id': nid, 'label': c.name, 'type': 'code', 'color': c.color})

    edges = []
    refs = CodedReference.query.join(Code).filter(Code.project_id == project.id).all()
    seen = set()
    for r in refs:
        doc_nid = f'doc-{r.document_id}'
        code_nid = f'code-{r.code_id}'
        key = (doc_nid, code_nid)
        if key not in seen:
            seen.add(key)
            edges.append({'source': doc_nid, 'target': code_nid})

    return jsonify({'nodes': nodes, 'edges': edges})
