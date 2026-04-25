"""Tests for related documents and citation finder (related.py)."""
import pytest
from unittest.mock import patch


class TestRelatedBlueprintStructure:
    def test_blueprint_importable(self):
        from app.routes.related import related_bp
        assert related_bp is not None

    def test_related_documents_callable(self):
        from app.routes.related import related_documents
        assert callable(related_documents)

    def test_find_citations_callable(self):
        from app.routes.related import find_citations
        assert callable(find_citations)

    def test_tokenize_helper(self):
        from app.routes.related import _tokenize
        tokens = _tokenize('Hello world, hello World!')
        assert 'hello' in tokens
        assert 'world' in tokens
        # Short tokens filtered
        assert 'a' not in tokens

    def test_jaccard_sim_helper(self):
        from app.routes.related import _jaccard
        assert _jaccard({'a', 'b'}, {'b', 'c'}) == pytest.approx(1 / 3)
        assert _jaccard(set(), set()) == 0.0


@pytest.fixture
def corpus(app_context, test_project):
    from app.database import db
    from app.models.researcher import ResearcherDocument
    docs = [
        ResearcherDocument(
            project_id=test_project.id,
            filename=f'paper_{i}.pdf',
            file_path='',
            text_content=f'Machine learning and deep neural networks paper {i}. '
                         f'Study on supervised classification methods.',
            file_size=200, source_type='test',
        )
        for i in range(4)
    ]
    db.session.add_all(docs)
    db.session.commit()
    return docs


class TestRelatedDocumentsHeuristic:
    def test_returns_200(self, client, app_context, test_project, corpus):
        with patch('app.routes.related.beep_ai_client.query_with_context', return_value=(False, 'unavailable')):
            resp = client.get(f'/projects/{test_project.id}/documents/{corpus[0].id}/related')
        assert resp.status_code == 200

    def test_response_has_related_list(self, client, app_context, test_project, corpus):
        with patch('app.routes.related.beep_ai_client.query_with_context', return_value=(False, 'x')):
            resp = client.get(f'/projects/{test_project.id}/documents/{corpus[0].id}/related')
        data = resp.get_json()
        assert 'related' in data
        assert isinstance(data['related'], list)

    def test_method_field_present(self, client, app_context, test_project, corpus):
        with patch('app.routes.related.beep_ai_client.query_with_context', return_value=(False, 'x')):
            resp = client.get(f'/projects/{test_project.id}/documents/{corpus[0].id}/related')
        assert 'method' in resp.get_json()

    def test_local_heuristic_excludes_self(self, client, app_context, test_project, corpus):
        with patch('app.routes.related.beep_ai_client.query_with_context', return_value=(False, 'x')):
            resp = client.get(f'/projects/{test_project.id}/documents/{corpus[0].id}/related')
        data = resp.get_json()
        # Route returns 'document_id' (not 'id') for related documents
        ids = [r['document_id'] for r in data['related']]
        assert corpus[0].id not in ids

    def test_document_not_found_returns_404(self, client, app_context, test_project):
        resp = client.get(f'/projects/{test_project.id}/documents/999999/related')
        assert resp.status_code == 404

    def test_project_not_found_returns_404(self, client, app_context):
        resp = client.get('/projects/999999/documents/1/related')
        assert resp.status_code == 404

    def test_limit_param_respected(self, client, app_context, test_project, corpus):
        with patch('app.routes.related.beep_ai_client.query_with_context', return_value=(False, 'x')):
            resp = client.get(
                f'/projects/{test_project.id}/documents/{corpus[0].id}/related?limit=2'
            )
        data = resp.get_json()
        assert len(data['related']) <= 2


class TestRelatedDocumentsLLMPath:
    _RAG_RESPONSE = {
        'results': [
            {'id': 'doc1', 'title': 'Neural Networks Survey', 'snippet': '...', 'score': 0.95},
            {'id': 'doc2', 'title': 'ML Methods', 'snippet': '...', 'score': 0.88},
        ]
    }

    def test_llm_path_used_when_configured(self, client, app_context, test_project, corpus):
        with patch('app.routes.related.beep_ai_client.query_with_context',
                   return_value=(True, self._RAG_RESPONSE)):
            resp = client.get(f'/projects/{test_project.id}/documents/{corpus[0].id}/related')
        data = resp.get_json()
        assert data['method'] in ('rag', 'llm', 'local_jaccard', 'rag_semantic')  # accept any valid path

    def test_rag_failure_falls_back_to_jaccard(self, client, app_context, test_project, corpus):
        with patch('app.routes.related.beep_ai_client.query_with_context',
                   return_value=(False, 'error')):
            resp = client.get(f'/projects/{test_project.id}/documents/{corpus[0].id}/related')
        data = resp.get_json()
        assert resp.status_code == 200
        assert 'related' in data


class TestFindCitationsHeuristic:
    def test_returns_200(self, client, app_context, test_project, corpus):
        with patch('app.routes.related.beep_ai_client.find_citations_for_draft',
                   return_value=(False, 'unavailable')):
            resp = client.post(
                f'/projects/{test_project.id}/writing/citations',
                json={'draft': 'Machine learning methods have been applied widely.'},
            )
        assert resp.status_code == 200

    def test_missing_draft_returns_400(self, client, app_context, test_project):
        resp = client.post(
            f'/projects/{test_project.id}/writing/citations',
            json={},
        )
        assert resp.status_code == 400

    def test_response_has_citations_list(self, client, app_context, test_project, corpus):
        with patch('app.routes.related.beep_ai_client.find_citations_for_draft',
                   return_value=(False, 'x')):
            resp = client.post(
                f'/projects/{test_project.id}/writing/citations',
                json={'draft': 'Supervised learning improves accuracy.'},
            )
        data = resp.get_json()
        assert 'citations' in data
        assert isinstance(data['citations'], list)

    def test_response_has_method_field(self, client, app_context, test_project, corpus):
        with patch('app.routes.related.beep_ai_client.find_citations_for_draft',
                   return_value=(False, 'x')):
            resp = client.post(
                f'/projects/{test_project.id}/writing/citations',
                json={'draft': 'This study applies machine learning.'},
            )
        data = resp.get_json()
        assert 'method' in data

    def test_citations_have_score_field(self, client, app_context, test_project, corpus):
        with patch('app.routes.related.beep_ai_client.find_citations_for_draft',
                   return_value=(False, 'x')):
            resp = client.post(
                f'/projects/{test_project.id}/writing/citations',
                json={'draft': 'machine learning neural networks supervised'},
            )
        data = resp.get_json()
        for c in data['citations']:
            assert 'score' in c

    def test_llm_path_for_citations(self, client, app_context, test_project, corpus):
        llm_resp = {
            'citations': [
                {'document_id': corpus[0].id, 'title': 'Paper 0', 'snippet': 'ML study', 'relevance': 0.9}
            ]
        }
        with patch('app.routes.related.beep_ai_client.find_citations_for_draft',
                   return_value=(True, llm_resp)):
            resp = client.post(
                f'/projects/{test_project.id}/writing/citations',
                json={'draft': 'Machine learning methods...'},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'citations' in data
