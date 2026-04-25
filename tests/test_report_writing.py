"""Tests for LLM-powered writing assistance (report_writing.py)."""
import pytest
from unittest.mock import patch


class TestReportWritingBlueprintStructure:
    def test_blueprint_importable(self):
        from app.routes.report_writing import report_bp
        assert report_bp is not None

    def test_writing_assist_callable(self):
        from app.routes.report_writing import assist_writing
        assert callable(assist_writing)

    def test_all_actions_defined(self):
        from app.routes.report_writing import _ACTION_PROMPTS
        expected = {
            'grammar', 'paraphrase', 'tone', 'summarize',
            'expand', 'academic_rewrite', 'simplify',
            'legal_plain', 'medical_lay',
        }
        assert expected.issubset(set(_ACTION_PROMPTS.keys()))


class TestWritingAssistHeuristicFallback:
    """When LLM is not configured the route must still return a safe response."""

    def test_grammar_returns_200(self, client, app_context, test_project):
        with patch('app.routes.report_writing.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/writing/assist',
                json={'text': 'This are a test sentence.', 'action': 'grammar'},
            )
        assert resp.status_code == 200

    def test_fallback_returns_original_text(self, client, app_context, test_project):
        with patch('app.routes.report_writing.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/writing/assist',
                json={'text': 'Hello world.', 'action': 'paraphrase'},
            )
        data = resp.get_json()
        assert data['original'] == 'Hello world.'
        assert 'suggested' in data

    def test_response_has_word_counts(self, client, app_context, test_project):
        with patch('app.routes.report_writing.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/writing/assist',
                json={'text': 'One two three.', 'action': 'summarize'},
            )
        data = resp.get_json()
        assert 'word_count_original' in data
        assert data['word_count_original'] == 3

    def test_missing_text_returns_400(self, client, app_context, test_project):
        resp = client.post(
            f'/projects/{test_project.id}/writing/assist',
            json={'action': 'grammar'},
        )
        assert resp.status_code == 400

    def test_missing_action_defaults_to_paraphrase(self, client, app_context, test_project):
        # action is optional; defaults to 'paraphrase' when missing
        with patch('app.routes.report_writing.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/writing/assist',
                json={'text': 'Some text'},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get('action') == 'paraphrase'

    def test_invalid_action_returns_400(self, client, app_context, test_project):
        resp = client.post(
            f'/projects/{test_project.id}/writing/assist',
            json={'text': 'xyz', 'action': 'teleport'},
        )
        assert resp.status_code == 400

    def test_project_not_found(self, client, app_context):
        resp = client.post(
            '/projects/999999/writing/assist',
            json={'text': 'x', 'action': 'grammar'},
        )
        assert resp.status_code == 404


class TestWritingAssistLLMPath:
    def test_llm_suggested_text_returned(self, client, app_context, test_project):
        with patch('app.routes.report_writing.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.report_writing.beep_ai_client.chat_reply',
                   return_value=(True, 'This is a corrected sentence.')):
            resp = client.post(
                f'/projects/{test_project.id}/writing/assist',
                json={'text': 'This are incorrect.', 'action': 'grammar'},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['suggested'] == 'This is a corrected sentence.'
        assert data['method'] == 'llm'

    def test_llm_failure_falls_back_gracefully(self, client, app_context, test_project):
        with patch('app.routes.report_writing.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.report_writing.beep_ai_client.chat_reply',
                   return_value=(False, 'server error')):
            resp = client.post(
                f'/projects/{test_project.id}/writing/assist',
                json={'text': 'Test text here.', 'action': 'expand'},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'suggested' in data

    def test_tone_action_passes_tone_parameter(self, client, app_context, test_project):
        captured = {}

        def mock_chat_reply(messages, model=None, temperature=None):
            captured['messages'] = messages
            return (True, 'Formal rewrite.')

        with patch('app.routes.report_writing.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.report_writing.beep_ai_client.chat_reply', side_effect=mock_chat_reply):
            resp = client.post(
                f'/projects/{test_project.id}/writing/assist',
                json={'text': 'Hey mate!', 'action': 'tone', 'tone': 'formal'},
            )
        assert resp.status_code == 200
        assert 'formal' in str(captured.get('messages', '')).lower()

    def test_response_has_action_field(self, client, app_context, test_project):
        with patch('app.routes.report_writing.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.report_writing.beep_ai_client.chat_reply',
                   return_value=(True, 'Simplified.')):
            resp = client.post(
                f'/projects/{test_project.id}/writing/assist',
                json={'text': 'Complex terminology.', 'action': 'simplify'},
            )
        assert resp.get_json()['action'] == 'simplify'

    def test_legal_plain_action_works(self, client, app_context, test_project):
        with patch('app.routes.report_writing.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.report_writing.beep_ai_client.chat_reply',
                   return_value=(True, 'Plain English version.')):
            resp = client.post(
                f'/projects/{test_project.id}/writing/assist',
                json={'text': 'Pursuant to the aforementioned clause...', 'action': 'legal_plain'},
            )
        assert resp.status_code == 200
        assert resp.get_json()['action'] == 'legal_plain'

    def test_medical_lay_action_works(self, client, app_context, test_project):
        with patch('app.routes.report_writing.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.report_writing.beep_ai_client.chat_reply',
                   return_value=(True, 'In simple terms...')):
            resp = client.post(
                f'/projects/{test_project.id}/writing/assist',
                json={'text': 'Myocardial infarction diagnosis.', 'action': 'medical_lay'},
            )
        assert resp.status_code == 200

    @pytest.mark.parametrize('action', [
        'grammar', 'paraphrase', 'summarize', 'expand',
        'academic_rewrite', 'simplify',
    ])
    def test_all_standard_actions_return_200(self, client, app_context, test_project, action):
        with patch('app.routes.report_writing.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.report_writing.beep_ai_client.chat_reply',
                   return_value=(True, f'{action} result.')):
            resp = client.post(
                f'/projects/{test_project.id}/writing/assist',
                json={'text': 'Test sentence to process.', 'action': action},
            )
        assert resp.status_code == 200

    def test_word_count_suggested_computed(self, client, app_context, test_project):
        with patch('app.routes.report_writing.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.report_writing.beep_ai_client.chat_reply',
                   return_value=(True, 'One two three four five.')):
            resp = client.post(
                f'/projects/{test_project.id}/writing/assist',
                json={'text': 'Short.', 'action': 'expand'},
            )
        data = resp.get_json()
        assert data['word_count_suggested'] == 5

    def test_assist_writing_uses_saved_project_quality_temperature(self, client, app_context, test_project):
        from app.database import db
        from app.models.researcher import ResearchProject

        project = db.session.get(ResearchProject, test_project.id)
        project.rag_quality_mode = 'deep'
        db.session.commit()

        captured = {}

        def mock_chat_reply(messages, model=None, temperature=None):
            captured['temperature'] = temperature
            return (True, 'Formal rewrite.')

        with patch('app.routes.report_writing.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.report_writing.beep_ai_client.chat_reply', side_effect=mock_chat_reply):
            resp = client.post(
                f'/projects/{test_project.id}/writing/assist',
                json={'text': 'Hey mate!', 'action': 'tone'},
            )

        assert resp.status_code == 200
        assert captured['temperature'] == 0.1

    def test_assist_writing_includes_grounded_library_evidence(self, client, app_context, test_project):
        captured = {}

        def mock_chat_reply(messages, model=None, temperature=None):
            captured['messages'] = messages
            return (True, 'Formal rewrite.')

        with patch('app.routes.report_writing.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.report_writing.build_project_grounded_context', return_value={
                 'context_text': 'Supporting library evidence:\n[1] Paper A [Doc 10]: Grounded rewrite evidence.',
                 'sources': [{'source': 'Paper A', 'document_id': '10', 'snippet': 'Grounded rewrite evidence.'}],
             }), \
             patch('app.routes.report_writing.beep_ai_client.chat_reply', side_effect=mock_chat_reply):
            resp = client.post(
                f'/projects/{test_project.id}/writing/assist',
                json={'text': 'Hey mate!', 'action': 'tone'},
            )

        assert resp.status_code == 200
        assert 'Supporting library evidence:' in captured['messages'][1]['content']
        assert resp.get_json()['supporting_sources'][0]['document_id'] == '10'
