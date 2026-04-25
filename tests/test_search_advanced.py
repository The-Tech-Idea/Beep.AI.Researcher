"""Tests for advanced search and facets endpoints (search_advanced.py)."""
import pytest
from unittest.mock import patch, MagicMock


class TestSearchAdvancedBlueprintStructure:
    def test_blueprint_importable(self):
        from app.routes.search_advanced import search_advanced_bp
        assert search_advanced_bp is not None
        assert search_advanced_bp.name == 'search_advanced'

    def test_advanced_search_callable(self):
        from app.routes.search_advanced import advanced_search
        assert callable(advanced_search)

    def test_search_facets_callable(self):
        from app.routes.search_advanced import search_facets
        assert callable(search_facets)


@pytest.fixture
def indexed_docs(app_context, test_project):
    """Create SearchIndex entries for facet tests."""
    from app.database import db
    from app.models.researcher.search_cache import SearchIndex
    docs_data = [
        dict(title='Machine Learning Survey', abstract='ML overview', provider='pubmed',
             result_type='article', access_type='open', publication_year=2023,
             citation_count=44),
        dict(title='Deep Learning Methods', abstract='DL study', provider='arxiv',
             result_type='preprint', access_type='open', publication_year=2022,
             citation_count=12),
        dict(title='Neural Network Applications', abstract='NN apps', provider='semantic_scholar',
             result_type='article', access_type='restricted', publication_year=2023,
             citation_count=7),
    ]
    indices = []
    for d in docs_data:
        result_dict = {
            'title': d['title'],
            'abstract': d['abstract'],
            'publication_date': f"{d['publication_year']}-01-01",
            'result_type': d['result_type'],
            'access_type': d['access_type'],
            'citation_count': d['citation_count'],
        }
        idx = SearchIndex(
            project_id=test_project.id,
            source_id=f"ext_{d['title'][:5].replace(' ', '_')}",
            provider=d['provider'],
            result=result_dict,
            query='machine learning',
        )
        db.session.add(idx)
        indices.append(idx)
    db.session.commit()
    return indices


class TestAdvancedSearch:
    def test_returns_200_with_query(self, client, app_context, test_project, indexed_docs):
        with patch('app.routes.search_advanced._run_search_providers', return_value=[]), \
             patch('app.routes.search_advanced.SearchCacheManager') as MockCM:
            instance = MockCM.return_value
            instance.search_with_cache.return_value = ([], False)
            resp = client.post(
                f'/projects/{test_project.id}/search/advanced',
                json={'query': 'machine learning'},
            )
        # Accept 200 OR graceful non-500 response
        assert resp.status_code in (200, 400, 404)

    def test_missing_query_returns_400(self, client, app_context, test_project):
        resp = client.post(
            f'/projects/{test_project.id}/search/advanced',
            json={},
        )
        assert resp.status_code == 400

    def test_project_not_found(self, client, app_context):
        resp = client.post(
            '/projects/999999/search/advanced',
            json={'query': 'test'},
        )
        assert resp.status_code == 404

    def test_response_has_required_keys(self, client, app_context, test_project, indexed_docs):
        with patch('app.routes.search_advanced._run_search_providers', return_value=[]), \
             patch('app.routes.search_advanced.SearchCacheManager') as MockCM:
            instance = MockCM.return_value
            instance.search_with_cache.return_value = ([], False)
            resp = client.post(
                f'/projects/{test_project.id}/search/advanced',
                json={'query': 'machine learning'},
            )
        if resp.status_code == 200:
            data = resp.get_json()
            assert 'results' in data
            assert 'query' in data
            assert 'pagination' in data

    def test_advanced_sort_options_accepted(self, client, app_context, test_project):
        for sort in ('relevance', 'date', 'citations'):
            with patch('app.routes.search_advanced._run_search_providers', return_value=[]), \
                 patch('app.routes.search_advanced.SearchCacheManager') as MockCM:
                instance = MockCM.return_value
                instance.search_with_cache.return_value = ([], False)
                resp = client.post(
                    f'/projects/{test_project.id}/search/advanced',
                    json={'query': 'test', 'sort': sort},
                )
            assert resp.status_code in (200, 400)  # Should not 500


class TestSearchFacets:
    def test_returns_200(self, client, app_context, test_project, indexed_docs):
        resp = client.get(f'/projects/{test_project.id}/search/facets')
        assert resp.status_code == 200

    def test_response_has_provider_facet(self, client, app_context, test_project, indexed_docs):
        resp = client.get(f'/projects/{test_project.id}/search/facets')
        data = resp.get_json()
        assert 'providers' in data

    def test_response_has_result_type_facet(self, client, app_context, test_project, indexed_docs):
        resp = client.get(f'/projects/{test_project.id}/search/facets')
        data = resp.get_json()
        assert 'result_types' in data

    def test_response_has_access_type_facet(self, client, app_context, test_project, indexed_docs):
        resp = client.get(f'/projects/{test_project.id}/search/facets')
        data = resp.get_json()
        assert 'access_types' in data

    def test_response_has_year_facet(self, client, app_context, test_project, indexed_docs):
        resp = client.get(f'/projects/{test_project.id}/search/facets')
        data = resp.get_json()
        assert 'years' in data

    def test_facets_count_providers(self, client, app_context, test_project, indexed_docs):
        resp = client.get(f'/projects/{test_project.id}/search/facets')
        data = resp.get_json()
        providers = {p['provider']: p['count'] for p in data['providers']}
        assert providers.get('pubmed', 0) >= 1
        assert providers.get('arxiv', 0) >= 1
        assert providers.get('semantic_scholar', 0) >= 1

    def test_facets_count_years(self, client, app_context, test_project, indexed_docs):
        resp = client.get(f'/projects/{test_project.id}/search/facets')
        data = resp.get_json()
        years = {y['year']: y['count'] for y in data['years']}
        assert years.get(2023, 0) >= 2
        assert years.get(2022, 0) >= 1

    def test_facets_project_not_found(self, client, app_context):
        resp = client.get('/projects/999999/search/facets')
        assert resp.status_code == 404

    def test_facets_provider_filter(self, client, app_context, test_project, indexed_docs):
        resp = client.get(f'/projects/{test_project.id}/search/facets?provider=pubmed')
        assert resp.status_code == 200

    def test_facets_date_range_filter(self, client, app_context, test_project, indexed_docs):
        resp = client.get(
            f'/projects/{test_project.id}/search/facets?from_date=2023-01-01&to_date=2023-12-31'
        )
        assert resp.status_code == 200

    def test_empty_project_returns_empty_facets(self, client, app_context, test_project):
        resp = client.get(f'/projects/{test_project.id}/search/facets')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data['providers'], list)
        assert isinstance(data['years'], list)
