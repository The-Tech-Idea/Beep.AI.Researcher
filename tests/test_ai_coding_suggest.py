"""Tests for AI-assisted qualitative code suggestions (ai_coding.py)."""
import json
import pytest
from unittest.mock import patch


class TestAICodingBlueprintStructure:
    def test_blueprint_importable(self):
        from app.routes.ai_coding import ai_coding_bp
        assert ai_coding_bp is not None

    def test_suggest_codes_callable(self):
        from app.routes.ai_coding import suggest_codes
        assert callable(suggest_codes)

    def test_auto_suggest_codes_callable(self):
        from app.routes.ai_coding import auto_suggest_codes
        assert callable(auto_suggest_codes)

    def test_codebook_summary_helper(self):
        from app.routes.ai_coding import _codebook_summary
        from types import SimpleNamespace
        codes = [
            SimpleNamespace(id=1, name='Theme A', description='About A'),
            SimpleNamespace(id=2, name='Theme B', description=None),
        ]
        summary = _codebook_summary(codes)
        assert 'Theme A' in summary
        assert 'Theme B' in summary

    def test_chunk_text_with_offsets(self):
        from app.routes.ai_coding import _chunk_text_with_offsets
        # The function yields (text, start_offset, chunk_id) tuples
        chunks = list(_chunk_text_with_offsets('abcde', size=2))
        assert len(chunks) > 0
        assert chunks[0][1] == 0          # start offset
        assert chunks[0][0] == 'ab'       # chunk text
        assert chunks[0][2] == 'chunk-0'  # chunk id


@pytest.fixture
def codebook(app_context, test_project):
    from app.database import db
    from app.models.researcher import Code
    codes = [
        Code(project_id=test_project.id, name='Economic Factors', description='About economics'),
        Code(project_id=test_project.id, name='Social Issues', description='Social aspects'),
        Code(project_id=test_project.id, name='Policy', description='Government policy'),
    ]
    db.session.add_all(codes)
    db.session.commit()
    return codes


@pytest.fixture
def coded_doc(app_context, test_project):
    from app.database import db
    from app.models.researcher import ResearcherDocument
    doc = ResearcherDocument(
        project_id=test_project.id,
        filename='interview.pdf',
        file_path='',
        text_content=(
            'The economic downturn has significantly impacted local communities. '
            'Social inequality has risen and government policy has not addressed disparity. '
            'Policy reform is urgently needed to restore economic stability.'
        ),
        file_size=300, source_type='test',
    )
    db.session.add(doc)
    db.session.commit()
    return doc


class TestSuggestCodesHeuristic:
    def test_returns_200_without_llm(self, client, app_context, test_project, codebook, coded_doc):
        with patch('app.routes.ai_coding.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/codes/suggest',
                json={'document_id': coded_doc.id, 'text': 'economic downturn communities'},
            )
        assert resp.status_code == 200

    def test_response_has_suggestions(self, client, app_context, test_project, codebook, coded_doc):
        with patch('app.routes.ai_coding.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/codes/suggest',
                json={'document_id': coded_doc.id, 'text': 'economic policy'},
            )
        data = resp.get_json()
        assert 'suggestions' in data
        assert isinstance(data['suggestions'], list)

    def test_text_required(self, client, app_context, test_project):
        """Missing text/selected_text should return 400."""
        resp = client.post(
            f'/projects/{test_project.id}/codes/suggest',
            json={},
        )
        assert resp.status_code == 400

    def test_document_id_optional(self, client, app_context, test_project, codebook):
        """document_id is optional; valid text alone returns 200."""
        with patch('app.routes.ai_coding.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/codes/suggest',
                json={'text': 'some text about economics'},
            )
        assert resp.status_code == 200

    def test_project_not_found(self, client, app_context):
        resp = client.post(
            '/projects/999999/codes/suggest',
            json={'text': 'test'},
        )
        assert resp.status_code == 404

    def test_heuristic_uses_frequency_fallback(self, client, app_context, test_project, codebook, coded_doc):
        from app.database import db
        from app.models.researcher import CodedReference
        # Create several coded references to one code
        for _ in range(3):
            db.session.add(CodedReference(
                code_id=codebook[0].id,
                document_id=coded_doc.id,
                chunk_id='c0',
                start_offset=0,
                end_offset=10,
            ))
        db.session.commit()

        with patch('app.routes.ai_coding.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/codes/suggest',
                json={'document_id': coded_doc.id, 'text': 'economic downturn'},
            )
        assert resp.status_code == 200


class TestSuggestCodesLLMPath:
    _LLM_REPLY = json.dumps({'suggestions': [
        {'name': 'Economic Factors', 'rationale': 'Relevant to economic topics', 'is_new': False},
        {'name': 'Policy', 'rationale': 'Clear policy reference', 'is_new': False},
    ]})

    def test_llm_path_used_when_configured(self, client, app_context, test_project, codebook, coded_doc):
        with patch('app.routes.ai_coding.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.ai_coding.beep_ai_client.chat_reply',
                   return_value=(True, self._LLM_REPLY)):
            resp = client.post(
                f'/projects/{test_project.id}/codes/suggest',
                json={'document_id': coded_doc.id, 'text': 'economic policy reform'},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['method'] == 'llm'

    def test_llm_suggestions_have_code_id(self, client, app_context, test_project, codebook, coded_doc):
        with patch('app.routes.ai_coding.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.ai_coding.beep_ai_client.chat_reply',
                   return_value=(True, self._LLM_REPLY)):
            resp = client.post(
                f'/projects/{test_project.id}/codes/suggest',
                json={'document_id': coded_doc.id, 'text': 'economic policy reform'},
            )
        data = resp.get_json()
        # Route returns 'id' (not 'code_id') for matched existing codes
        matched = [s for s in data['suggestions'] if s.get('id') is not None]
        assert len(matched) >= 1  # At least one suggestion matched to existing code

    def test_llm_failure_falls_back(self, client, app_context, test_project, codebook, coded_doc):
        with patch('app.routes.ai_coding.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.ai_coding.beep_ai_client.chat_reply',
                   return_value=(False, 'timeout')):
            resp = client.post(
                f'/projects/{test_project.id}/codes/suggest',
                json={'document_id': coded_doc.id, 'text': 'policy'},
            )
        assert resp.status_code == 200
        assert 'suggestions' in resp.get_json()

    def test_llm_prompt_includes_grounded_library_evidence(self, client, app_context, test_project, codebook, coded_doc):
        captured = {}

        def fake_chat_reply(messages):
            captured['messages'] = messages
            return (True, self._LLM_REPLY)

        with patch('app.routes.ai_coding.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.ai_coding.build_project_grounded_context', return_value={
                 'context_text': 'Supporting library evidence:\n[1] Interview source [Doc 9]: Context for the coding suggestion.',
                 'sources': [{'source': 'Interview source', 'document_id': '9', 'snippet': 'Context for the coding suggestion.'}],
             }), \
             patch('app.routes.ai_coding.beep_ai_client.chat_reply', side_effect=fake_chat_reply):
            resp = client.post(
                f'/projects/{test_project.id}/codes/suggest',
                json={'document_id': coded_doc.id, 'text': 'economic policy reform'},
            )

        assert resp.status_code == 200
        assert 'Supporting library evidence:' in captured['messages'][1]['content']
        assert resp.get_json()['supporting_sources'][0]['document_id'] == '9'


class TestAutoSuggestCodes:
    _LLM_REPLY = json.dumps({'codes': [
        {'name': 'Economic Factors', 'rationale': 'Economic topic present'},
    ]})

    def test_auto_suggest_returns_200(self, client, app_context, test_project, codebook, coded_doc):
        with patch('app.routes.ai_coding.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.ai_coding.beep_ai_client.chat_reply',
                   return_value=(True, self._LLM_REPLY)):
            resp = client.post(
                f'/projects/{test_project.id}/codes/auto-suggest',
                json={'document_id': coded_doc.id},
            )
        assert resp.status_code == 200

    def test_auto_suggest_document_id_required(self, client, app_context, test_project):
        resp = client.post(
            f'/projects/{test_project.id}/codes/auto-suggest',
            json={},
        )
        assert resp.status_code == 400

    def test_auto_suggest_response_has_proposals(self, client, app_context, test_project, codebook, coded_doc):
        with patch('app.routes.ai_coding.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.ai_coding.beep_ai_client.chat_reply',
                   return_value=(True, self._LLM_REPLY)):
            resp = client.post(
                f'/projects/{test_project.id}/codes/auto-suggest',
                json={'document_id': coded_doc.id},
            )
        data = resp.get_json()
        assert 'proposals' in data
        assert isinstance(data['proposals'], list)

    def test_auto_suggest_doc_not_found(self, client, app_context, test_project):
        resp = client.post(
            f'/projects/{test_project.id}/codes/auto-suggest',
            json={'document_id': 999999},
        )
        assert resp.status_code == 404

    def test_auto_suggest_project_not_found(self, client, app_context):
        resp = client.post(
            '/projects/999999/codes/auto-suggest',
            json={'document_id': 1},
        )
        assert resp.status_code == 404

    def test_auto_suggest_without_llm(self, client, app_context, test_project, codebook, coded_doc):
        with patch('app.routes.ai_coding.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/codes/auto-suggest',
                json={'document_id': coded_doc.id},
            )
        assert resp.status_code == 200

    def test_auto_suggest_prompt_includes_grounded_library_evidence(self, client, app_context, test_project, codebook, coded_doc):
        captured = {}

        def fake_chat_reply(messages):
            captured['messages'] = messages
            return (True, self._LLM_REPLY)

        with patch('app.routes.ai_coding.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.ai_coding.build_project_grounded_context', return_value={
                 'context_text': 'Supporting library evidence:\n[1] Interview source [Doc 9]: Context for the bulk coding pass.',
                 'sources': [{'source': 'Interview source', 'document_id': '9', 'snippet': 'Context for the bulk coding pass.'}],
             }), \
             patch('app.routes.ai_coding.beep_ai_client.chat_reply', side_effect=fake_chat_reply):
            resp = client.post(
                f'/projects/{test_project.id}/codes/auto-suggest',
                json={'document_id': coded_doc.id},
            )

        assert resp.status_code == 200
        assert 'Supporting library evidence:' in captured['messages'][1]['content']
        assert resp.get_json()['supporting_sources'][0]['document_id'] == '9'
