"""Phase 3: Coding matrices — cross-tabulate codes × documents."""

from flask import Blueprint, request, jsonify
from flask_login import login_required

from app.models.researcher import (
    ResearchProject,
    Code,
    CodedReference,
    ResearcherDocument,
)
from app.routes.route_entity_lookup import get_entity_or_404, get_project_or_404

matrices_bp = Blueprint("coding_matrices", __name__)


@matrices_bp.route("/<int:project_id>/matrices", methods=["GET"])
@login_required
def get_coding_matrix(project_id):
    """Cross-tabulate codes × documents (reference counts)."""
    project = get_project_or_404(project_id)
    codes = Code.query.filter_by(project_id=project.id, parent_id=None).all()
    docs = ResearcherDocument.query.filter_by(project_id=project.id).all()

    rows = [c.name for c in codes]
    cols = [d.filename for d in docs]
    matrix = []
    for c in codes:
        row = []
        for d in docs:
            cnt = CodedReference.query.filter_by(code_id=c.id, document_id=d.id).count()
            row.append(cnt)
        matrix.append(row)

    return jsonify(
        {
            "rows": rows,
            "columns": cols,
            "matrix": matrix,
        }
    )
