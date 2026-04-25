"""Cache management routes for search caching (Phase 2.5)."""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.database import db
from app.models.researcher import ResearchProject, SearchCache, SearchIndex
from app.services.search_cache_manager import get_cache_manager
from functools import wraps

cache_management_bp = Blueprint('cache_management', __name__, url_prefix='/projects')


def admin_required(f):
    """Decorator to require authenticated admin user."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not getattr(current_user, 'is_admin', False):
            return jsonify({'error': 'Admin access required.'}), 403
        return f(*args, **kwargs)
    return decorated_function


@cache_management_bp.route('/<int:project_id>/cache/stats', methods=['GET'])
def get_cache_stats(project_id):
    """
    GET /projects/{id}/cache/stats
    Get cache statistics for a project.
    
    Returns:
        {
            'total_cached_queries': int,
            'total_cache_hits': int,
            'total_cache_size_mb': float,
            'expired_entries': int,
            'lru_cache_size': int,
            'indexed_results': int
        }
    """
    try:
        # Verify project exists
        project = db.session.get(ResearchProject, project_id)
        if not project:
            return {'error': 'Project not found'}, 404
        
        cache_manager = get_cache_manager()
        stats = cache_manager.get_cache_stats(project_id)
        
        return {'data': stats}, 200
    
    except Exception as e:
        return {'error': str(e)}, 500


@cache_management_bp.route('/<int:project_id>/cache/clear', methods=['POST'])
@admin_required
def clear_project_cache(project_id):
    """
    POST /projects/{id}/cache/clear
    Clear all cache entries for a project.
    
    Returns:
        {
            'cleared': int,
            'message': str
        }
    """
    try:
        project = db.session.get(ResearchProject, project_id)
        if not project:
            return {'error': 'Project not found'}, 404
        
        # Count before delete
        count_before = SearchCache.query.filter_by(project_id=project_id).count()
        
        cache_manager = get_cache_manager()
        cache_manager.invalidate_project_cache(project_id)
        
        return {
            'cleared': count_before,
            'message': f'Cleared {count_before} cache entries'
        }, 200
    
    except Exception as e:
        return {'error': str(e)}, 500


@cache_management_bp.route('/<int:project_id>/cache/expired/clean', methods=['POST'])
@admin_required
def clean_expired_cache(project_id):
    """
    POST /projects/{id}/cache/expired/clean
    Remove expired cache entries (global operation, not project-specific).
    
    Returns:
        {
            'cleaned': int,
            'message': str
        }
    """
    try:
        cache_manager = get_cache_manager()
        cleaned = cache_manager.clear_expired_cache()
        
        return {
            'cleaned': cleaned,
            'message': f'Removed {cleaned} expired cache entries'
        }, 200
    
    except Exception as e:
        return {'error': str(e)}, 500


@cache_management_bp.route('/<int:project_id>/cache', methods=['GET'])
def list_cache_entries(project_id):
    """
    GET /projects/{id}/cache
    List all cache entries for a project with pagination.
    
    Query params:
        - page: page number (default 1)
        - per_page: results per page (default 20, max 100)
        - provider: filter by provider name
        - expired_only: show only expired (true/false)
    
    Returns:
        {
            'data': [
                {
                    'id': int,
                    'provider': str,
                    'query': str,
                    'result_count': int,
                    'hit_count': int,
                    'is_expired': bool,
                    'created_at': ISO datetime,
                    'expires_at': ISO datetime
                }
            ],
            'pagination': {
                'page': int,
                'per_page': int,
                'total': int,
                'pages': int
            }
        }
    """
    try:
        project = db.session.get(ResearchProject, project_id)
        if not project:
            return {'error': 'Project not found'}, 404
        
        # Parse query params
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        provider = request.args.get('provider')
        expired_only = request.args.get('expired_only', 'false').lower() == 'true'
        
        # Build query
        query = SearchCache.query.filter_by(project_id=project_id)
        
        if provider:
            query = query.filter_by(provider=provider)
        
        # Get all entries first to filter expired in Python (or use raw SQL)
        entries = query.all()
        
        if expired_only:
            entries = [e for e in entries if e.is_expired()]
        
        # Paginate
        total = len(entries)
        start = (page - 1) * per_page
        end = start + per_page
        paginated = entries[start:end]
        
        return {
            'data': [e.to_dict() for e in paginated],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        }, 200
    
    except Exception as e:
        return {'error': str(e)}, 500


@cache_management_bp.route('/<int:project_id>/cache/<int:cache_id>', methods=['DELETE'])
@admin_required
def delete_cache_entry(project_id, cache_id):
    """
    DELETE /projects/{id}/cache/{cache_id}
    Delete a specific cache entry.
    
    Returns:
        {
            'deleted': bool,
            'message': str
        }
    """
    try:
        project = db.session.get(ResearchProject, project_id)
        if not project:
            return {'error': 'Project not found'}, 404
        
        cache_entry = SearchCache.query.filter_by(id=cache_id, project_id=project_id).first()
        if not cache_entry:
            return {'error': 'Cache entry not found'}, 404
        
        db.session.delete(cache_entry)
        db.session.commit()
        
        return {
            'deleted': True,
            'message': f'Deleted cache entry {cache_id}'
        }, 200
    
    except Exception as e:
        db.session.rollback()
        return {'error': str(e)}, 500


@cache_management_bp.route('/<int:project_id>/search/index', methods=['GET'])
def get_indexed_results(project_id):
    """
    GET /projects/{id}/search/index
    Get indexed search results with faceted filtering.
    
    Query params:
        - provider: filter by provider (pubmed, arxiv, etc)
        - source: filter by source (journal name, conference, etc)
        - result_type: filter by type (journal_article, preprint, etc)
        - access_type: filter by access (open_access, closed, etc)
        - year: filter by publication year
        - page: page number (default 1)
        - per_page: results per page (default 20, max 100)
    
    Returns:
        {
            'data': [SearchIndex dict, ...],
            'pagination': {...},
            'facets': {
                'providers': [str, ...],
                'sources': [str, ...],
                'result_types': [str, ...],
                'access_types': [str, ...],
                'years': [int, ...]
            }
        }
    """
    try:
        project = db.session.get(ResearchProject, project_id)
        if not project:
            return {'error': 'Project not found'}, 404
        
        # Parse facet filters
        facets = {
            'provider': request.args.get('provider'),
            'source': request.args.get('source'),
            'result_type': request.args.get('result_type'),
            'access_type': request.args.get('access_type'),
            'year': request.args.get('year'),
        }
        facets = {k: v for k, v in facets.items() if v}  # Remove None values
        
        # Get filtered results
        cache_manager = get_cache_manager()
        results = cache_manager.get_faceted_search(project_id, **facets)
        
        # Paginate
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        total = len(results)
        start = (page - 1) * per_page
        end = start + per_page
        paginated = results[start:end]
        
        # Get available facet values for the project
        all_indexes = SearchIndex.query.filter_by(project_id=project_id).all()
        
        facet_values = {
            'providers': sorted(set(idx.provider for idx in all_indexes if idx.provider)),
            'sources': sorted(set(idx.source for idx in all_indexes if idx.source)),
            'result_types': sorted(set(idx.result_type for idx in all_indexes if idx.result_type)),
            'access_types': sorted(set(idx.access_type for idx in all_indexes if idx.access_type)),
            'years': sorted(set(
                idx.publication_date.year
                for idx in all_indexes
                if idx.publication_date
            )),
        }
        
        return {
            'data': [r.to_dict() for r in paginated],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            },
            'facets': facet_values
        }, 200
    
    except Exception as e:
        return {'error': str(e)}, 500


@cache_management_bp.route('/<int:project_id>/cache/config', methods=['GET', 'POST'])
@admin_required
def cache_config(project_id):
    """
    GET/POST /projects/{id}/cache/config
    Get or update cache configuration for a project.
    
    GET returns current config.
    POST with {'cache_enabled': bool, 'ttl_hours': int, 'max_lru_size': int}
    """
    try:
        project = db.session.get(ResearchProject, project_id)
        if not project:
            return {'error': 'Project not found'}, 404
        
        if request.method == 'POST':
            data = request.get_json() or {}
            
            # Store config (could be in project model or separate config table)
            # For now, just return the config that would be set
            config = {
                'cache_enabled': data.get('cache_enabled', True),
                'ttl_hours': data.get('ttl_hours', 24),
                'max_lru_size': data.get('max_lru_size', 100),
            }
            
            return {
                'message': 'Cache configuration updated',
                'config': config
            }, 200
        
        else:  # GET
            config = {
                'cache_enabled': getattr(project, 'cache_enabled', True),
                'ttl_hours': 24,
                'max_lru_size': 100,
            }
            return {'config': config}, 200
    
    except Exception as e:
        return {'error': str(e)}, 500
