"""Tests for contradiction detection (contradiction.py)."""
import json
import pytest
from unittest.mock import patch


class TestContradictionBlueprintStructure:
    def test_blueprint_importable(self):
        from app.routes.contradiction import contradiction_bp
        assert contradiction_bp is not None

    def test_detect_contradictions_callable(self):
        from app.routes.contradiction import detect_contradictions
        assert callable(detect_contradictions)

    def test_negation_regex_defined(self):
        from app.routes.contradiction import _NEGATION_RE
        import re
        assert _NEGATION_RE.search('This does not support the claim')
        assert _NEGATION_RE.search('There is no evidence')
        assert not _NEGATION_RE.search('The study confirms the hypothesis')

    def test_jaccard_helper(self):
        from app.routes.contradiction import _jaccard
        assert _jaccard({'a', 'b', 'c'}, {'b', 'c', 'd'}) == pytest.approx(0.5)
        assert _jaccard(set(), set()) == 0.0
        assert _jaccard({'x'}, {'y'}) == 0.0


class TestContradictionMissingParams:
    def test_missing_query_returns_400(self, client, app_context, test_project):
        resp = client.post(
            f'/projects/{test_project.id}/contradictions',
            json={},
        )
        assert resp.status_code == 400

    def test_project_not_found(self, client, app_context):
        resp = client.post(
            '/projects/999999/contradictions',
            json={'query': 'test'},
        )
        assert resp.status_code == 404


class TestContradictionHeuristicFallback:
    """Tests for the local heuristic path (no LLM server)."""

    @pytest.fixture
    def two_docs(self, app_context, test_project):
        from app.database import db
        from app.models.researcher import ResearcherDocument
        doc_a = ResearcherDocument(
            project_id=test_project.id,
            filename='doc_a.pdf',
            file_path='',
            text_content='The drug significantly reduces blood pressure. It does not cause side effects.',
            file_size=100, source_type='test',
        )
        doc_b = ResearcherDocument(
            project_id=test_project.id,
            filename='doc_b.pdf',
            file_path='',
            text_content='The drug does not reduce blood pressure. Side effects were observed.',
            file_size=100, source_type='test',
        )
        db.session.add_all([doc_a, doc_b])
        db.session.commit()
        return [doc_a, doc_b]

    def test_returns_200_with_method_field(self, client, app_context, test_project, two_docs):
        with patch('app.routes.contradiction.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/contradictions',
                json={'query': 'blood pressure drug'},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'method' in data
        assert data['method'] == 'local_heuristic'

    def test_response_has_contradictions_list(self, client, app_context, test_project, two_docs):
        with patch('app.routes.contradiction.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/contradictions',
                json={'query': 'blood pressure'},
            )
        data = resp.get_json()
        assert isinstance(data['contradictions'], list)

    def test_response_has_total_sources_checked(self, client, app_context, test_project, two_docs):
        with patch('app.routes.contradiction.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/contradictions',
                json={'query': 'drug'},
            )
        data = resp.get_json()
        assert 'total_sources_checked' in data
        assert data['total_sources_checked'] >= 0

    def test_document_ids_filter(self, client, app_context, test_project, two_docs):
        with patch('app.routes.contradiction.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/contradictions',
                json={'query': 'drug', 'document_ids': [two_docs[0].id]},
            )
        assert resp.status_code == 200

    def test_no_documents_returns_empty(self, client, app_context, test_project):
        with patch('app.routes.contradiction.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/contradictions',
                json={'query': 'nonexistent term'},
            )
        data = resp.get_json()
        assert data['contradictions'] == []


class TestContradictionLLMPath:
    _LLM_RESPONSE = {
        'contradictions': [
            {
                'source_a': 'drug reduces pressure',
                'source_b': 'drug does not reduce pressure',
                'explanation': 'Opposite claims about drug efficacy',
                'confidence': 0.91,
            }
        ],
        'total_sources_checked': 2,
    }

    def test_llm_path_used_when_configured(self, client, app_context, test_project):
        with patch('app.routes.contradiction.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.contradiction.beep_ai_client.detect_contradictions',
                   return_value=(True, self._LLM_RESPONSE)):
            resp = client.post(
                f'/projects/{test_project.id}/contradictions',
                json={'query': 'drug blood pressure'},
            )
        data = resp.get_json()
        assert data['method'] == 'llm'
        assert len(data['contradictions']) == 1

    def test_llm_contradiction_has_explanation(self, client, app_context, test_project):
        with patch('app.routes.contradiction.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.contradiction.beep_ai_client.detect_contradictions',
                   return_value=(True, self._LLM_RESPONSE)):
            resp = client.post(
                f'/projects/{test_project.id}/contradictions',
                json={'query': 'drug'},
            )
        item = resp.get_json()['contradictions'][0]
        assert 'explanation' in item

    def test_llm_failure_falls_back_to_heuristic(self, client, app_context, test_project):
        with patch('app.routes.contradiction.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.contradiction.beep_ai_client.detect_contradictions',
                   return_value=(False, 'timeout')):
            resp = client.post(
                f'/projects/{test_project.id}/contradictions',
                json={'query': 'drug'},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['method'] == 'local_heuristic'
