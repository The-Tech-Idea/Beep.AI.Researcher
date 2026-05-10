"""Extended search routes — multi-source academic search with filtering (Phase 2.3)."""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from app.database import db
from app.models.researcher import ResearchProject, LibrarySource
from app.models.researcher.library_sources import SourceImportLog
from app.core.time_utils import utcnow_naive
from app.routes.project_api_guard import (
    guard_project_blueprint,
    get_guarded_project_or_404 as get_project_or_404,
)
from app.services.reference_service import create_reference, reference_to_dict

try:
    from app.integrations.search import get_search_manager, SearchFilter
except ImportError:
    get_search_manager = None
    SearchFilter = None

try:
    from app.core.event_bus import get_event_bus
except ImportError:
    get_event_bus = None

extended_search_bp = Blueprint("extended_search", __name__)


def _get_search_manager():
    """Get SearchManager instance if available."""
    if not get_search_manager:
        return None
    try:
        return get_search_manager()
    except Exception:
        return None


def _get_event_bus():
    """Get EventBus instance if available."""
    if not get_event_bus:
        return None
    try:
        return get_event_bus()
    except Exception:
        return None


def _publish_event(event_name, data=None):
    """Publish event to EventBus if available."""
    bus = _get_event_bus()
    if bus and hasattr(bus, "publish"):
        try:
            bus.publish(event_name, data or {})
        except Exception:
            pass  # Fail gracefully


@extended_search_bp.route("/projects/<int:project_id>/web-search", methods=["POST"])
@login_required
def web_search(project_id):
    """Multi-source academic search across configured library sources.

    Request body:
    {
        "query": "string (required)",
        "sources": ["pubmed", "arxiv"] (optional, default: all available),
        "limit": 50 (optional, default: 50),
        "filters": {
            "from_date": "2020-01-01",
            "to_date": "2024-12-31",
            "publication_type": "journal_article",
            "language": "en",
            "open_access_only": true
        },
        "page": 1 (optional, default: 1),
        "deduplicate": true (optional, default: true)
    }
    """
    project = get_project_or_404(project_id)

    search_manager = _get_search_manager()
    if not search_manager:
        return jsonify({"error": "Search system not available"}), 503

    # Parse request
    data = request.get_json() or {}
    query = (data.get("query") or "").strip()

    if not query:
        return jsonify({"error": "Query is required"}), 400

    # Validate query length
    if len(query) < 2:
        return jsonify({"error": "Query must be at least 2 characters"}), 400

    if len(query) > 500:
        return jsonify({"error": "Query exceeded 500 character limit"}), 400

    # Get pagination params
    page = max(1, data.get("page", 1))
    limit = min(data.get("limit", 50), 200)  # Cap at 200
    offset = (page - 1) * limit

    # Parse sources
    requested_sources = data.get("sources", [])
    if isinstance(requested_sources, str):
        requested_sources = [requested_sources]

    # If specific sources requested, validate against configured sources
    if requested_sources:
        configured_sources = LibrarySource.query.filter_by(
            project_id=project.id, is_active=True
        ).all()
        configured_types = {s.source_type for s in configured_sources}
        requested_sources = [s for s in requested_sources if s in configured_types]

        if not requested_sources:
            return jsonify(
                {
                    "error": "No valid sources specified",
                    "available_sources": list(configured_types),
                }
            ), 400

    # Parse filters
    filter_data = data.get("filters", {})
    try:
        search_filter = SearchFilter(
            from_date=filter_data.get("from_date"),
            to_date=filter_data.get("to_date"),
            publication_type=filter_data.get("publication_type"),
            language=filter_data.get("language", "en"),
            open_access_only=filter_data.get("open_access_only", False),
            custom_filters=filter_data.get("custom_filters"),
        )
    except ValueError as e:
        return jsonify({"error": f"Invalid filter: {str(e)}"}), 400

    # Publish search started event
    _publish_event(
        "search.started",
        {
            "project_id": project.id,
            "user_id": current_user.id,
            "query": query,
            "sources": requested_sources,
        },
    )

    # Perform search
    start_time = utcnow_naive()
    try:
        results = search_manager.search(
            query=query,
            sources=requested_sources or None,  # None = all available
            filters=search_filter,
            limit=limit + offset,  # Get extra for pagination
            deduplicate=data.get("deduplicate", True),
        )

        # Paginate results
        total = len(results)
        paginated_results = results[offset : offset + limit]

        search_duration_ms = (utcnow_naive() - start_time).total_seconds() * 1000

        # Publish search completed event
        _publish_event(
            "search.completed",
            {
                "project_id": project.id,
                "user_id": current_user.id,
                "query": query,
                "result_count": total,
                "returned_count": len(paginated_results),
                "duration_ms": search_duration_ms,
            },
        )

        return jsonify(
            {
                "query": query,
                "sources": requested_sources or ["all"],
                "results": [r.to_dict() for r in paginated_results],
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit,  # Ceiling division
                },
                "duration_ms": search_duration_ms,
            }
        )

    except Exception as e:
        # Publish search error event
        _publish_event(
            "search.failed",
            {
                "project_id": project.id,
                "user_id": current_user.id,
                "query": query,
                "error": str(e),
            },
        )

        return jsonify(
            {
                "error": "Search failed",
                "message": str(e),
            }
        ), 500


@extended_search_bp.route(
    "/projects/<int:project_id>/web-search/autocomplete", methods=["GET"]
)
@login_required
def search_autocomplete(project_id):
    """Get search suggestions based on partial query.

    Query parameters:
    - q: partial query (optional)
    - limit: max suggestions (default: 10, max: 50)

    Response:
    {
        "suggestions": ["search term", "another term"],
        "recent": ["recently searched term"]
    }
    """
    project = get_project_or_404(project_id)

    # For now, return empty suggestions
    # Future: could track recent searches per project
    # or integrate with search provider autocomplete APIs

    limit = min(int(request.args.get("limit", 10)), 50)
    partial_q = request.args.get("q", "").strip()

    # Use logged search queries from this project's import history
    source_ids = (
        db.session.query(LibrarySource.id).filter_by(project_id=project.id).subquery()
    )
    log_query = (
        db.session.query(SourceImportLog.query)
        .filter(SourceImportLog.source_id.in_(source_ids))
        .order_by(SourceImportLog.imported_at.desc())
    )
    if partial_q:
        log_query = log_query.filter(SourceImportLog.query.ilike(f"{partial_q}%"))

    recent_queries = [row.query for row in log_query.limit(limit).all()]
    # Deduplicate while preserving order
    seen: set = set()
    unique_recent = [q for q in recent_queries if not (q in seen or seen.add(q))]  # type: ignore[func-returns-value]

    suggestions = (
        [q for q in unique_recent if partial_q.lower() in q.lower()]
        if partial_q
        else []
    )

    return jsonify(
        {
            "suggestions": suggestions[:limit],
            "recent": unique_recent[:limit],
        }
    )


@extended_search_bp.route(
    "/projects/<int:project_id>/web-search/sources", methods=["GET"]
)
@login_required
def list_searchable_sources(project_id):
    """List available library sources for searching in this project.

    Response:
    {
        "sources": [
            {
                "id": 1,
                "name": "PubMed Central",
                "source_type": "pubmed",
                "is_available": true,
                "last_health_check": "2024-01-15T10:30:00",
                "request_count": 42
            }
        ],
        "count": 1
    }
    """
    project = get_project_or_404(project_id)

    sources = LibrarySource.query.filter_by(project_id=project.id, is_active=True).all()

    return jsonify(
        {
            "sources": [s.to_dict_summary() for s in sources],
            "count": len(sources),
        }
    )


@extended_search_bp.route(
    "/projects/<int:project_id>/web-search/available", methods=["GET"]
)
@login_required
def get_available_sources(project_id):
    """Get list of searchable source types (built-in and configured).

    Response:
    {
        "builtin": ["local", "pubmed", "arxiv"],
        "configured": [
            {
                "id": 1,
                "name": "Custom API",
                "source_type": "custom",
                "is_available": true
            }
        ]
    }
    """
    project = get_project_or_404(project_id)

    # Get configured sources
    configured = LibrarySource.query.filter_by(
        project_id=project.id, is_active=True
    ).all()

    return jsonify(
        {
            "builtin": ["local", "pubmed", "arxiv"],  # Always available
            "configured": [
                {
                    "id": s.id,
                    "name": s.name,
                    "source_type": s.source_type,
                    "is_available": s.is_available,
                }
                for s in configured
            ],
        }
    )


@extended_search_bp.route(
    "/projects/<int:project_id>/web-search/popular", methods=["GET"]
)
@login_required
def get_popular_searches(project_id):
    """Get popular or trending search queries for this project.

    Query parameters:
    - limit: max results (default: 20, max: 100)
    - days: lookback period (default: 30)

    Response:
    {
        "popular": [
            {"query": "machine learning", "count": 5},
            {"query": "neural networks", "count": 3}
        ]
    }

    Note: Currently placeholder. Future implementation would track
    searches via Phase 1 JobQueue or EventBus.
    """
    project = get_project_or_404(project_id)

    limit = min(int(request.args.get("limit", 20)), 100)

    # Aggregate query frequency from import logs for this project's sources
    source_ids = (
        db.session.query(LibrarySource.id).filter_by(project_id=project.id).subquery()
    )
    popular = (
        db.session.query(
            SourceImportLog.query,
            func.count(SourceImportLog.id).label("count"),
        )
        .filter(SourceImportLog.source_id.in_(source_ids))
        .group_by(SourceImportLog.query)
        .order_by(func.count(SourceImportLog.id).desc())
        .limit(limit)
        .all()
    )

    return jsonify(
        {
            "popular": [{"query": row.query, "count": row.count} for row in popular],
        }
    )


@extended_search_bp.route(
    "/projects/<int:project_id>/web-search/filters/publication-types", methods=["GET"]
)
@login_required
def get_publication_types(project_id):
    """Get available publication type filters.

    Response:
    {
        "types": [
            {"id": "journal_article", "label": "Journal Article"},
            {"id": "preprint", "label": "Preprint"},
            {"id": "conference_paper", "label": "Conference Paper"}
        ]
    }
    """
    return jsonify(
        {
            "types": [
                {"id": "journal_article", "label": "Journal Article"},
                {"id": "preprint", "label": "Preprint"},
                {"id": "conference_paper", "label": "Conference Paper"},
                {"id": "book", "label": "Book"},
                {"id": "book_chapter", "label": "Book Chapter"},
                {"id": "dataset", "label": "Dataset"},
                {"id": "thesis", "label": "Thesis"},
                {"id": "report", "label": "Report"},
            ]
        }
    )


@extended_search_bp.route(
    "/projects/<int:project_id>/web-search/filters/languages", methods=["GET"]
)
@login_required
def get_languages(project_id):
    """Get available language filters.

    Response:
    {
        "languages": [
            {"code": "en", "label": "English"},
            {"code": "es", "label": "Spanish"},
            {"code": "fr", "label": "French"}
        ]
    }
    """
    return jsonify(
        {
            "languages": [
                {"code": "en", "label": "English"},
                {"code": "es", "label": "Spanish"},
                {"code": "fr", "label": "French"},
                {"code": "de", "label": "German"},
                {"code": "it", "label": "Italian"},
                {"code": "pt", "label": "Portuguese"},
                {"code": "zh", "label": "Chinese"},
                {"code": "ja", "label": "Japanese"},
            ]
        }
    )


@extended_search_bp.route(
    "/projects/<int:project_id>/web-search/add-to-library", methods=["POST"]
)
@login_required
def add_search_result_to_library(project_id):
    """Convert a book / search hit into a project Reference record.

    Accepts the ``to_dict()`` payload of a ``SearchResult`` (or a manually
    assembled dict with at minimum a ``title`` field) and creates a new
    ``Reference`` in the project citation library.

    Request body::

        {
            "title": "...",
            "authors": ["Author One", ...],
            "source_type": "book",          // optional
            "publication_date": "YYYY-MM-DD",
            "url": "https://...",
            "doi": "...",
            "abstract": "...",
            "keywords": ["..."],
            "metadata": { ... },            // SearchResult metadata dict
            "source": "google_books",       // provider name
            "journal": "..."
        }

    Response::

        {"ok": true, "reference": { ... }}
    """
    project = get_project_or_404(project_id)

    data = request.get_json() or {}
    if not data.get("title"):
        return jsonify({"error": "title is required"}), 400

    # Normalise SearchResult fields into create_reference payload
    ref_data = {
        "title": data.get("title"),
        "authors": data.get("authors") or [],
        "source_type": _normalize_book_source_type(
            data.get("source_type") or data.get("result_type")
        ),
        "url": data.get("url") or "",
        "doi": data.get("doi") or "",
        "abstract": data.get("abstract") or "",
        "keywords": data.get("keywords") or [],
        "source": data.get("journal") or data.get("source") or "",
        "metadata": data.get("metadata") or {},
    }

    pub_date = data.get("publication_date") or ""
    if pub_date and len(pub_date) >= 4:
        try:
            ref_data["year"] = int(pub_date[:4])
        except ValueError:
            pass

    try:
        reference = create_reference(project, ref_data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({"ok": True, "reference": reference_to_dict(reference)}), 201


def _normalize_book_source_type(raw: str | None) -> str:
    """Map SearchResult.result_type values to Reference.source_type strings."""
    mapping = {
        "book": "book",
        "book_chapter": "book",
        "book_metadata": "book",
        "journal_article": "journal",
        "preprint": "arxiv",
        "conference_paper": "conference",
        "thesis": "thesis",
        "report": "report",
        "dataset": "other",
        "unknown": "other",
    }
    if not raw:
        return "other"
    return mapping.get(raw.lower(), raw.lower())


guard_project_blueprint(extended_search_bp)
