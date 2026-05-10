"""Library sources admin routes — CRUD and health checks for external search sources (Phase 2.2)."""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from app.database import db
from app.models.researcher import (
    ResearchProject,
    LibrarySource,
    SourceConnection,
    SourceImportLog,
)
from app.core.time_utils import utcnow_naive
from app.routes.route_entity_lookup import get_entity_or_404, get_project_or_404

try:
    from app.integrations.search import get_search_manager
except ImportError:
    get_search_manager = None

library_sources_bp = Blueprint("library_sources", __name__)


# Permission check: require project admin or owner
def _require_project_admin(project_id):
    """Check if current user is project owner."""
    project = get_project_or_404(project_id)
    if project.owner_id != current_user.id:
        return None, {"error": "Not project owner"}, 403
    return project, None, None


@library_sources_bp.route("/projects/<int:project_id>/library-sources", methods=["GET"])
@login_required
def list_sources(project_id):
    """List all library sources for a project."""
    project, error, status = _require_project_admin(project_id)
    if error:
        return jsonify(error), status

    sources = LibrarySource.query.filter_by(project_id=project.id).all()
    return jsonify(
        {
            "sources": [s.to_dict_summary() for s in sources],
            "count": len(sources),
        }
    )


@library_sources_bp.route(
    "/projects/<int:project_id>/library-sources", methods=["POST"]
)
@login_required
def create_source(project_id):
    """Create a new library source."""
    project, error, status = _require_project_admin(project_id)
    if error:
        return jsonify(error), status

    data = request.get_json() or {}

    # Validate required fields
    required = ["name", "source_type"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"Missing required field: {field}"}), 400

    source_type = data.get("source_type")
    valid_types = ["pubmed", "arxiv", "semantic_scholar", "crossref", "custom"]
    if source_type not in valid_types:
        return jsonify(
            {"error": f"Invalid source_type. Must be: {', '.join(valid_types)}"}
        ), 400

    # Check for duplicate name in project
    existing = LibrarySource.query.filter_by(
        project_id=project.id, name=data.get("name")
    ).first()
    if existing:
        return jsonify(
            {"error": f'Source "{data.get("name")}" already exists in this project'}
        ), 409

    # Create source
    source = LibrarySource(
        project_id=project.id,
        name=data.get("name"),
        source_type=source_type,
        description=data.get("description"),
        api_endpoint=data.get("api_endpoint"),
        api_key=data.get("api_key"),
        auth_token=data.get("auth_token"),
        rate_limit_per_hour=data.get("rate_limit_per_hour", 100),
        timeout_seconds=data.get("timeout_seconds", 30),
        headers_json=data.get("headers_json"),
        auto_import=data.get("auto_import", False),
        max_results_per_query=data.get("max_results_per_query", 50),
        min_confidence=data.get("min_confidence", 0.0),
    )

    db.session.add(source)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to create source"}), 500

    return jsonify(
        {
            "message": "Source created",
            "source": source.to_dict(),
        }
    ), 201


@library_sources_bp.route(
    "/projects/<int:project_id>/library-sources/<int:source_id>", methods=["GET"]
)
@login_required
def get_source(project_id, source_id):
    """Get library source details."""
    project, error, status = _require_project_admin(project_id)
    if error:
        return jsonify(error), status

    source = LibrarySource.query.filter_by(
        id=source_id, project_id=project.id
    ).first_or_404()

    return jsonify(
        {
            "source": source.to_dict(include_sensitive=True),
        }
    )


@library_sources_bp.route(
    "/projects/<int:project_id>/library-sources/<int:source_id>", methods=["PUT"]
)
@login_required
def update_source(project_id, source_id):
    """Update a library source."""
    project, error, status = _require_project_admin(project_id)
    if error:
        return jsonify(error), status

    source = LibrarySource.query.filter_by(
        id=source_id, project_id=project.id
    ).first_or_404()

    data = request.get_json() or {}

    # Update fields
    if "name" in data:
        source.name = data["name"]
    if "description" in data:
        source.description = data["description"]
    if "api_endpoint" in data:
        source.api_endpoint = data["api_endpoint"]
    if "api_key" in data:
        source.api_key = data["api_key"]
    if "auth_token" in data:
        source.auth_token = data["auth_token"]
    if "rate_limit_per_hour" in data:
        source.rate_limit_per_hour = data["rate_limit_per_hour"]
    if "timeout_seconds" in data:
        source.timeout_seconds = data["timeout_seconds"]
    if "is_active" in data:
        source.is_active = data["is_active"]
    if "auto_import" in data:
        source.auto_import = data["auto_import"]
    if "max_results_per_query" in data:
        source.max_results_per_query = data["max_results_per_query"]
    if "min_confidence" in data:
        source.min_confidence = data["min_confidence"]
    if "headers_json" in data:
        source.headers_json = data["headers_json"]

    source.updated_at = utcnow_naive()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to update source"}), 500

    return jsonify(
        {
            "message": "Source updated",
            "source": source.to_dict(),
        }
    )


@library_sources_bp.route(
    "/projects/<int:project_id>/library-sources/<int:source_id>", methods=["DELETE"]
)
@login_required
def delete_source(project_id, source_id):
    """Delete a library source."""
    project, error, status = _require_project_admin(project_id)
    if error:
        return jsonify(error), status

    source = LibrarySource.query.filter_by(
        id=source_id, project_id=project.id
    ).first_or_404()

    name = source.name
    db.session.delete(source)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to delete source"}), 500

    return jsonify(
        {
            "message": f'Source "{name}" deleted',
        }
    )


@library_sources_bp.route(
    "/projects/<int:project_id>/library-sources/<int:source_id>/test", methods=["POST"]
)
@login_required
def test_source(project_id, source_id):
    """Test connection to a library source."""
    project, error, status = _require_project_admin(project_id)
    if error:
        return jsonify(error), status

    source = LibrarySource.query.filter_by(
        id=source_id, project_id=project.id
    ).first_or_404()

    # For now, test with SearchManager if available
    if not get_search_manager:
        return jsonify(
            {
                "successful": False,
                "error": "Search system not available",
            }
        ), 503

    search_manager = get_search_manager()

    test_query = request.json.get("query", "test") if request.json else "test"
    start_time = utcnow_naive()

    try:
        # Attempt a test search
        results = search_manager.search(
            query=test_query, sources=[source.source_type], limit=1, deduplicate=False
        )

        is_successful = len(results) >= 0  # Any response is success (even 0 results)
        response_time_ms = (utcnow_naive() - start_time).total_seconds() * 1000
        error_msg = None
        result_count = len(results)

    except Exception as e:
        is_successful = False
        response_time_ms = (utcnow_naive() - start_time).total_seconds() * 1000
        error_msg = str(e)
        result_count = 0

    # Record connection test
    connection = SourceConnection(
        source_id=source.id,
        is_successful=is_successful,
        response_time_ms=response_time_ms,
        error_message=error_msg,
        test_query=test_query,
        test_result_count=result_count,
    )

    source.last_health_check = utcnow_naive()
    source.is_available = is_successful
    if error_msg:
        source.last_error = error_msg

    db.session.add(connection)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify(
            {"successful": False, "error": "Failed to save connection test"}
        ), 500

    return jsonify(
        {
            "successful": is_successful,
            "response_time_ms": response_time_ms,
            "result_count": result_count,
            "error": error_msg,
            "tested_at": connection.tested_at.isoformat(),
        }
    )


@library_sources_bp.route(
    "/projects/<int:project_id>/library-sources/<int:source_id>/connections",
    methods=["GET"],
)
@login_required
def get_source_connections(project_id, source_id):
    """Get connection test history for a source."""
    project, error, status = _require_project_admin(project_id)
    if error:
        return jsonify(error), status

    source = LibrarySource.query.filter_by(
        id=source_id, project_id=project.id
    ).first_or_404()

    limit = request.args.get("limit", 20, type=int)
    connections = (
        SourceConnection.query.filter_by(source_id=source.id)
        .order_by(SourceConnection.tested_at.desc())
        .limit(limit)
        .all()
    )

    return jsonify(
        {
            "source_id": source.id,
            "connections": [c.to_dict() for c in connections],
            "count": len(connections),
        }
    )


@library_sources_bp.route(
    "/projects/<int:project_id>/library-sources/<int:source_id>/imports",
    methods=["GET"],
)
@login_required
def get_source_imports(project_id, source_id):
    """Get import history for a source."""
    project, error, status = _require_project_admin(project_id)
    if error:
        return jsonify(error), status

    source = LibrarySource.query.filter_by(
        id=source_id, project_id=project.id
    ).first_or_404()

    limit = request.args.get("limit", 50, type=int)
    imports = (
        SourceImportLog.query.filter_by(source_id=source.id)
        .order_by(SourceImportLog.imported_at.desc())
        .limit(limit)
        .all()
    )

    return jsonify(
        {
            "source_id": source.id,
            "imports": [imp.to_dict() for imp in imports],
            "count": len(imports),
            "total_imported": sum(imp.documents_imported for imp in imports),
        }
    )


@library_sources_bp.route(
    "/projects/<int:project_id>/library-sources/health", methods=["GET"]
)
@login_required
def get_all_sources_health(project_id):
    """Get health status of all sources."""
    project, error, status = _require_project_admin(project_id)
    if error:
        return jsonify(error), status

    sources = LibrarySource.query.filter_by(project_id=project.id).all()

    health = []
    for source in sources:
        last_conn = (
            SourceConnection.query.filter_by(source_id=source.id)
            .order_by(SourceConnection.tested_at.desc())
            .first()
        )

        health.append(
            {
                "id": source.id,
                "name": source.name,
                "source_type": source.source_type,
                "is_available": source.is_available,
                "last_health_check": source.last_health_check.isoformat()
                if source.last_health_check
                else None,
                "last_connection": last_conn.to_dict() if last_conn else None,
                "request_count": source.request_count,
                "error_count": source.error_count,
            }
        )

    return jsonify(
        {
            "health": health,
            "count": len(health),
        }
    )
