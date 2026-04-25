"""Advanced search and faceted search routes (Phase A — missing endpoints).

Provides:
- POST /projects/<id>/search/advanced  — Boolean, field-specific, sector-tagged search
- GET  /projects/<id>/search/facets    — Faceted aggregations from the search index
"""
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from app.database import db
from app.models.researcher import ResearchProject
from app.models.researcher.search_cache import SearchIndex
from app.core.time_utils import utcnow_naive
from app.routes.route_entity_lookup import get_entity_or_404

try:
    from app.integrations.search import get_search_manager, SearchFilter
except ImportError:
    get_search_manager = None
    SearchFilter = None

try:
    from app.services.search_cache_manager import SearchCacheManager
except ImportError:
    SearchCacheManager = None

try:
    from app.core.event_bus import get_event_bus
except ImportError:
    get_event_bus = None

logger = logging.getLogger(__name__)

search_advanced_bp = Blueprint('search_advanced', __name__)


def _get_project_or_404(project_id):
    return get_entity_or_404(ResearchProject, project_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_search_manager():
    if not get_search_manager:
        return None
    try:
        return get_search_manager()
    except Exception:
        return None


def _get_cache_manager():
    if not SearchCacheManager:
        return None
    try:
        return SearchCacheManager(search_manager=_get_search_manager())
    except Exception:
        return None


def _run_search_providers(query, sources, search_filter, limit, deduplicate):
    """Invoke the configured search manager; returns empty list if not configured."""
    sm = _get_search_manager()
    if not sm:
        return []
    return sm.search(
        query=query,
        sources=sources or None,
        filters=search_filter,
        limit=limit,
        deduplicate=deduplicate,
    )


def _publish(event_name: str, data: dict):
    if not get_event_bus:
        return
    try:
        get_event_bus().publish(event_name, data)
    except Exception:
        pass


def _build_filter(filter_data: dict):
    """Build a SearchFilter from a dict, returning None if SearchFilter is unavailable."""
    if SearchFilter is None:
        return None
    return SearchFilter(
        from_date=filter_data.get('from_date'),
        to_date=filter_data.get('to_date'),
        publication_type=filter_data.get('publication_type'),
        language=filter_data.get('language'),
        open_access_only=bool(filter_data.get('open_access_only', False)),
        min_citation_count=filter_data.get('min_citation_count'),
        max_citation_count=filter_data.get('max_citation_count'),
        custom_filters=filter_data.get('custom_filters'),
    )


# ---------------------------------------------------------------------------
# Advanced Search
# ---------------------------------------------------------------------------

@search_advanced_bp.route('/<int:project_id>/search/advanced', methods=['POST'])
@login_required
def advanced_search(project_id):
    """Advanced multi-source search with Boolean operators, field targeting, and facet hints.

    Request body:
    {
        "query": "CRISPR AND gene therapy NOT off-target",   // Boolean operators supported
        "title_query": "optional title-specific term",
        "author_query": "Smith",
        "sources": ["pubmed", "arxiv"],          // optional; default: all configured
        "filters": {
            "from_date": "2020-01-01",
            "to_date": "2024-12-31",
            "publication_type": "journal_article",
            "language": "en",
            "open_access_only": true,
            "min_citation_count": 5
        },
        "limit": 50,
        "page": 1,
        "sort": "relevance" | "date" | "citations",
        "deduplicate": true,
        "use_cache": true,
        "sector": "medical" | "legal" | "education" | "real_estate"  // optional tag
    }

    Response:
    {
        "query": "...",
        "results": [...],
        "pagination": {...},
        "facets_hint": { "provider": [...], "result_type": [...] },
        "from_cache": bool,
        "duration_ms": float
    }
    """
    project = _get_project_or_404(project_id)

    data = request.get_json() or {}

    # ── Query ──────────────────────────────────────────────────────────────
    query = (data.get('query') or '').strip()
    if not query:
        return jsonify({'error': 'query is required'}), 400
    if len(query) > 1000:
        return jsonify({'error': 'query exceeds 1000 character limit'}), 400

    # Optional field-specific addons (append to query string for adapter delegation)
    title_q = (data.get('title_query') or '').strip()
    author_q = (data.get('author_query') or '').strip()
    composite_query = query
    if title_q:
        composite_query += f' title:({title_q})'
    if author_q:
        composite_query += f' author:({author_q})'

    # ── Pagination ─────────────────────────────────────────────────────────
    page = max(1, int(data.get('page', 1)))
    limit = min(int(data.get('limit', 50)), 200)
    offset = (page - 1) * limit

    # ── Sources ────────────────────────────────────────────────────────────
    sources = data.get('sources') or []
    if isinstance(sources, str):
        sources = [sources]

    # ── Filters ───────────────────────────────────────────────────────────
    try:
        search_filter = _build_filter(data.get('filters') or {})
    except (ValueError, TypeError) as exc:
        return jsonify({'error': f'Invalid filter: {exc}'}), 400

    use_cache = bool(data.get('use_cache', True))
    deduplicate = bool(data.get('deduplicate', True))
    sort_by = data.get('sort', 'relevance')  # relevance | date | citations

    # ── Log event ─────────────────────────────────────────────────────────
    _publish('search.advanced.started', {
        'project_id': project.id,
        'user_id': current_user.id,
        'query': composite_query,
        'sources': sources,
        'sector': data.get('sector'),
    })

    start_time = utcnow_naive()
    from_cache = False

    try:
        cache_manager = _get_cache_manager()
        if cache_manager and use_cache:
            all_results, from_cache = cache_manager.search_with_cache(
                project_id=project.id,
                query=composite_query,
                sources=sources or None,
                filters=search_filter,
                limit=limit + offset,
                deduplicate=deduplicate,
                cache_enabled=True,
            )
        else:
            all_results = _run_search_providers(
                composite_query, sources, search_filter, limit + offset, deduplicate
            )

        # ── Sort ──────────────────────────────────────────────────────────
        if sort_by == 'date':
            all_results = sorted(
                all_results,
                key=lambda r: getattr(r, 'publication_date', None) or '',
                reverse=True,
            )
        elif sort_by == 'citations':
            all_results = sorted(
                all_results,
                key=lambda r: getattr(r, 'citation_count', 0) or 0,
                reverse=True,
            )
        # default: keep relevance order

        # ── Paginate ──────────────────────────────────────────────────────
        total = len(all_results)
        page_results = all_results[offset:offset + limit]
        duration_ms = (utcnow_naive() - start_time).total_seconds() * 1000

        # ── Facets hint (quick aggregation on already-retrieved results) ───
        provider_counts: dict = {}
        type_counts: dict = {}
        for r in all_results:
            prov = getattr(r, 'source', 'unknown') or 'unknown'
            rtype = getattr(r, 'result_type', 'unknown') or 'unknown'
            provider_counts[prov] = provider_counts.get(prov, 0) + 1
            type_counts[rtype] = type_counts.get(rtype, 0) + 1

        _publish('search.advanced.completed', {
            'project_id': project.id,
            'user_id': current_user.id,
            'total': total,
            'duration_ms': duration_ms,
        })

        return jsonify({
            'query': composite_query,
            'sources': sources or ['all'],
            'results': [r.to_dict() if hasattr(r, 'to_dict') else r for r in page_results],
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'pages': max(1, (total + limit - 1) // limit),
            },
            'facets_hint': {
                'provider': [{'value': k, 'count': v} for k, v in provider_counts.items()],
                'result_type': [{'value': k, 'count': v} for k, v in type_counts.items()],
            },
            'from_cache': from_cache,
            'duration_ms': round(duration_ms, 2),
            'sector': data.get('sector'),
        })

    except Exception as exc:
        logger.exception("Advanced search failed for project %s", project_id)
        _publish('search.advanced.failed', {
            'project_id': project.id,
            'user_id': current_user.id,
            'error': str(exc),
        })
        return jsonify({'error': 'Advanced search failed', 'message': str(exc)}), 500


# ---------------------------------------------------------------------------
# Faceted Search
# ---------------------------------------------------------------------------

@search_advanced_bp.route('/<int:project_id>/search/facets', methods=['GET'])
@login_required
def search_facets(project_id):
    """Return faceted aggregations from the search index for a project.

    Query parameters:
    - provider: filter to a specific provider (optional)
    - from_date: ISO date string (optional)
    - to_date: ISO date string (optional)

    Response:
    {
        "project_id": 1,
        "facets": {
            "provider": [{"value": "pubmed", "count": 42}, ...],
            "result_type": [{"value": "journal_article", "count": 30}, ...],
            "access_type": [{"value": "open_access", "count": 20}, ...],
            "year": [{"value": 2023, "count": 15}, ...]
        },
        "total_indexed": 150
    }
    """
    project = _get_project_or_404(project_id)

    # Base query scoped to project
    base_q = SearchIndex.query.filter_by(project_id=project.id)

    # Optional filters
    provider_filter = request.args.get('provider')
    if provider_filter:
        base_q = base_q.filter(SearchIndex.provider == provider_filter)

    from_date_str = request.args.get('from_date')
    to_date_str = request.args.get('to_date')
    if from_date_str:
        try:
            base_q = base_q.filter(SearchIndex.publication_date >= datetime.fromisoformat(from_date_str))
        except ValueError:
            return jsonify({'error': 'Invalid from_date format (use ISO 8601)'}), 400
    if to_date_str:
        try:
            base_q = base_q.filter(SearchIndex.publication_date <= datetime.fromisoformat(to_date_str))
        except ValueError:
            return jsonify({'error': 'Invalid to_date format (use ISO 8601)'}), 400

    # Total indexed count
    total_indexed = base_q.count()

    # ── Provider facet ────────────────────────────────────────────────────
    provider_rows = db.session.query(
        SearchIndex.provider,
        func.count(SearchIndex.id).label('cnt'),
    ).filter(SearchIndex.project_id == project.id).group_by(
        SearchIndex.provider
    ).order_by(func.count(SearchIndex.id).desc()).all()

    # ── Result-type facet ─────────────────────────────────────────────────
    type_rows = db.session.query(
        SearchIndex.result_type,
        func.count(SearchIndex.id).label('cnt'),
    ).filter(SearchIndex.project_id == project.id).group_by(
        SearchIndex.result_type
    ).order_by(func.count(SearchIndex.id).desc()).all()

    # ── Access-type facet ─────────────────────────────────────────────────
    access_rows = db.session.query(
        SearchIndex.access_type,
        func.count(SearchIndex.id).label('cnt'),
    ).filter(SearchIndex.project_id == project.id).group_by(
        SearchIndex.access_type
    ).order_by(func.count(SearchIndex.id).desc()).all()

    # ── Year facet (from publication_date) ────────────────────────────────
    year_rows = db.session.query(
        func.strftime('%Y', SearchIndex.publication_date).label('year'),
        func.count(SearchIndex.id).label('cnt'),
    ).filter(
        SearchIndex.project_id == project.id,
        SearchIndex.publication_date.isnot(None),
    ).group_by('year').order_by('year').all()

    return jsonify({
        'project_id': project_id,
        'total_indexed': total_indexed,
        'providers': [{'provider': r.provider or 'unknown', 'count': r.cnt} for r in provider_rows],
        'result_types': [{'result_type': r.result_type or 'unknown', 'count': r.cnt} for r in type_rows],
        'access_types': [{'access_type': r.access_type or 'unknown', 'count': r.cnt} for r in access_rows],
        'years': [
            {'year': int(r.year), 'count': r.cnt}
            for r in year_rows if r.year and r.year.isdigit()
        ],
    })
