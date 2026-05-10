"""Phase 3 Knowledge Map routes."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.config_manager import is_feature_enabled
from app.models.researcher import ResearchProject
from app.routes.route_entity_lookup import get_entity_or_404

logger = logging.getLogger(__name__)

knowledge_map_bp = Blueprint("knowledge_map", __name__)


def _require_feature():
    if not is_feature_enabled("knowledge_map_enabled"):
        from flask import abort

        abort(404)


@knowledge_map_bp.route("/knowledge-map", methods=["GET"])
@login_required
def global_map():
    """Global citation map page."""
    _require_feature()
    from flask import render_template

    return render_template("knowledge_map/global_map.html")


@knowledge_map_bp.route("/knowledge-map/data", methods=["GET"])
@login_required
def global_map_data():
    """Global graph data across all user projects."""
    _require_feature()
    from app.services.knowledge_graph_service import KnowledgeGraphService

    projects = ResearchProject.query.filter_by(owner_id=current_user.id).all()
    all_nodes = []
    all_edges = []

    for proj in projects:
        try:
            graph = KnowledgeGraphService().build_graph(
                proj, current_user.id, max_nodes=100
            )
            for n in graph.get("nodes", []):
                n["project_id"] = proj.id
                n["project_name"] = proj.name
            all_nodes.extend(graph.get("nodes", []))
            all_edges.extend(graph.get("edges", []))
        except Exception as exc:
            logger.warning("Global map: project %d failed: %s", proj.id, exc)

    return jsonify(
        {"nodes": all_nodes, "edges": all_edges, "project_count": len(projects)}
    )


@knowledge_map_bp.route("/projects/<int:project_id>/knowledge-map", methods=["GET"])
@login_required
def project_map(project_id):
    """Project citation map page."""
    _require_feature()
    project = get_entity_or_404(ResearchProject, project_id)
    from flask import render_template

    return render_template("knowledge_map/knowledge_map.html", project=project)


@knowledge_map_bp.route(
    "/projects/<int:project_id>/knowledge-map/data", methods=["GET"]
)
@login_required
def project_map_data(project_id):
    """Project graph data."""
    _require_feature()
    project = get_entity_or_404(ResearchProject, project_id)
    if project.owner_id != current_user.id:
        return jsonify({"error": "Not authorized"}), 403

    from app.services.knowledge_graph_service import KnowledgeGraphService

    try:
        graph = KnowledgeGraphService().build_graph(project, current_user.id)
        return jsonify(graph)
    except Exception as exc:
        logger.exception("Knowledge map data failed")
        return jsonify({"error": str(exc)}), 500


@knowledge_map_bp.route(
    "/projects/<int:project_id>/knowledge-map/expand", methods=["POST"]
)
@login_required
def expand_node(project_id):
    """Expand a graph node to fetch 1-hop neighbours."""
    _require_feature()
    get_entity_or_404(ResearchProject, project_id)

    data = request.get_json() or {}
    doi = (data.get("doi") or "").strip()
    if not doi:
        return jsonify({"error": "doi required"}), 400

    from app.services.knowledge_graph_service import KnowledgeGraphService

    result = KnowledgeGraphService().expand_node(doi)
    return jsonify(result)


@knowledge_map_bp.route(
    "/projects/<int:project_id>/knowledge-map/export", methods=["GET"]
)
@login_required
def export_map(project_id):
    """Export graph as JSON."""
    _require_feature()
    project = get_entity_or_404(ResearchProject, project_id)

    from app.services.knowledge_graph_service import KnowledgeGraphService

    graph = KnowledgeGraphService().build_graph(project, current_user.id)
    return jsonify(graph)
