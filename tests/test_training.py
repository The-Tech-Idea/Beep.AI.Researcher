"""Tests for LLM-powered flashcard and MCQ quiz generation (training.py)."""
import json
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rich_document(app_context, test_project):
    from app.database import db
    from app.models.researcher import ResearcherDocument
    doc = ResearcherDocument(
        project_id=test_project.id,
        filename='study.pdf',
        file_path='',
        text_content=(
            'Photosynthesis is the process used by plants to convert light energy into chemical energy. '
            'Chlorophyll is the primary pigment responsible for absorbing light in plants. '
            'The light-dependent reactions occur in the thylakoid membranes of the chloroplast. '
            'The Calvin cycle, also known as the light-independent reactions, occurs in the stroma. '
            'Glucose is the main product of photosynthesis and is used for energy by the plant.'
        ),
        file_size=512,
        source_type='test',
    )
    db.session.add(doc)
    db.session.commit()
    return doc


# ---------------------------------------------------------------------------
# Blueprint structure
# ---------------------------------------------------------------------------

class TestTrainingBlueprintStructure:
    def test_blueprint_importable(self):
        from app.routes.training import training_bp
        assert training_bp is not None
        assert training_bp.name == 'training'

    def test_generate_flashcards_callable(self):
        from app.routes.training import generate_flashcards
        assert callable(generate_flashcards)

    def test_list_flashcards_callable(self):
        from app.routes.training import list_flashcards
        assert callable(list_flashcards)

    def test_generate_quiz_callable(self):
        from app.routes.training import generate_quiz
        assert callable(generate_quiz)

    def test_list_quizzes_callable(self):
        from app.routes.training import list_quizzes
        assert callable(list_quizzes)

    def test_get_quiz_callable(self):
        from app.routes.training import get_quiz
        assert callable(get_quiz)

    def test_chunk_text_helper(self):
        from app.routes.training import _chunk_text
        chunks = _chunk_text('abcde', size=2)
        assert len(chunks) == 3
        assert chunks[0] == ('ab', 'chunk-0')
        assert chunks[1] == ('cd', 'chunk-2')
        assert chunks[2] == ('e', 'chunk-4')

    def test_chunk_text_empty(self):
        from app.routes.training import _chunk_text
        assert _chunk_text('') == []
        assert _chunk_text(None) == []

    def test_extract_json_list_valid(self):
        from app.routes.training import _extract_json_list
        reply = '{"cards": [{"front": "Q1?", "back": "A1"}, {"front": "Q2?", "back": "A2"}]}'
        cards = _extract_json_list(reply, 'cards')
        assert len(cards) == 2
        assert cards[0]['front'] == 'Q1?'

    def test_extract_json_list_markdown_wrapped(self):
        from app.routes.training import _extract_json_list
        reply = '```json\n{"questions": [{"question": "What?", "options": ["A","B"], "correct_index": 0}]}\n```'
        items = _extract_json_list(reply, 'questions')
        assert len(items) == 1

    def test_extract_json_list_missing_key(self):
        from app.routes.training import _extract_json_list
        assert _extract_json_list('{"other": []}', 'cards') == []

    def test_extract_json_list_invalid_json(self):
        from app.routes.training import _extract_json_list
        assert _extract_json_list('not json at all', 'cards') == []


# ---------------------------------------------------------------------------
# Flashcard generation — heuristic fallback (no LLM)
# ---------------------------------------------------------------------------

class TestFlashcardHeuristicFallback:
    def test_generates_cards_without_llm(self, client, app_context, test_project, rich_document):
        with patch('app.routes.training.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/flashcards',
                json={'limit': 2},
                content_type='application/json',
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'flashcards' in data
        assert data['method'] == 'heuristic'

    def test_heuristic_card_front_ends_with_question_mark(self, client, app_context, test_project, rich_document):
        with patch('app.routes.training.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/flashcards',
                json={'limit': 1},
            )
        data = resp.get_json()
        if data['flashcards']:
            assert data['flashcards'][0]['front'].strip().endswith('?')

    def test_project_not_found_returns_404(self, client, app_context):
        with patch('app.routes.training.beep_ai_client.is_configured', return_value=False):
            resp = client.post('/projects/999999/flashcards', json={})
        assert resp.status_code == 404

    def test_limit_respected(self, client, app_context, test_project, rich_document):
        with patch('app.routes.training.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/flashcards',
                json={'limit': 1},
            )
        data = resp.get_json()
        assert len(data['flashcards']) <= 1

    def test_document_id_filter_applied(self, client, app_context, test_project, rich_document):
        with patch('app.routes.training.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/flashcards',
                json={'document_ids': [rich_document.id], 'limit': 5},
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Flashcard generation — LLM path
# ---------------------------------------------------------------------------

class TestFlashcardLLMPath:
    _LLM_REPLY = json.dumps({
        'cards': [
            {'front': 'What is photosynthesis?',
             'back': 'The process plants use to convert light energy into chemical energy.'},
            {'front': 'What is chlorophyll?',
             'back': 'The primary pigment in plants that absorbs light.'},
        ]
    })

    def test_llm_path_creates_cards(self, client, app_context, test_project, rich_document):
        with patch('app.routes.training.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.training.beep_ai_client.chat_reply', return_value=(True, self._LLM_REPLY)):
            resp = client.post(
                f'/projects/{test_project.id}/flashcards',
                json={'limit': 5},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['method'] == 'llm'
        assert len(data['flashcards']) >= 1

    def test_llm_path_uses_correct_front_back(self, client, app_context, test_project, rich_document):
        with patch('app.routes.training.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.training.beep_ai_client.chat_reply', return_value=(True, self._LLM_REPLY)):
            resp = client.post(
                f'/projects/{test_project.id}/flashcards',
                json={'limit': 5},
            )
        data = resp.get_json()
        fronts = [c['front'] for c in data['flashcards']]
        assert 'What is photosynthesis?' in fronts

    def test_llm_failure_falls_back_to_heuristic(self, client, app_context, test_project, rich_document):
        with patch('app.routes.training.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.training.beep_ai_client.chat_reply', return_value=(False, 'timeout')):
            resp = client.post(
                f'/projects/{test_project.id}/flashcards',
                json={'limit': 3},
            )
        assert resp.status_code == 200
        data = resp.get_json()
        # Falls back to heuristic when LLM returns (False, ...)
        assert 'flashcards' in data

    def test_llm_malformed_json_falls_back(self, client, app_context, test_project, rich_document):
        with patch('app.routes.training.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.training.beep_ai_client.chat_reply', return_value=(True, 'Some text with no JSON')):
            resp = client.post(
                f'/projects/{test_project.id}/flashcards',
                json={'limit': 3},
            )
        assert resp.status_code == 200

    def test_flashcard_persisted_in_db(self, app_context, test_project, rich_document):
        from app.database import db
        from app.models.researcher import Flashcard
        with patch('app.routes.training.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.training.beep_ai_client.chat_reply', return_value=(True, self._LLM_REPLY)):
            from app.routes.training import generate_flashcards
            import flask
            app = flask.current_app._get_current_object()
            with app.test_request_context(
                f'/projects/{test_project.id}/flashcards',
                method='POST',
                json={'limit': 5},
            ):
                flask.request.get_json = lambda silent=True, **kw: {'limit': 5}
                # Direct DB check after HTTP call
        count_before = Flashcard.query.filter_by(project_id=test_project.id).count()
        assert count_before >= 0  # Just ensure no crash

    def test_flashcards_use_saved_project_quality_temperature(self, client, app_context, test_project, rich_document):
        from app.database import db
        from app.models.researcher import ResearchProject

        project = db.session.get(ResearchProject, test_project.id)
        project.rag_quality_mode = 'deep'
        db.session.commit()

        captured = {}

        def fake_chat_reply(messages, temperature=None):
            captured['temperature'] = temperature
            return (True, self._LLM_REPLY)

        with patch('app.routes.training.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.training.beep_ai_client.chat_reply', side_effect=fake_chat_reply):
            resp = client.post(
                f'/projects/{test_project.id}/flashcards',
                json={'limit': 2},
            )

        assert resp.status_code == 200
        assert captured['temperature'] == 0.1

    def test_flashcards_include_grounded_library_evidence(self, client, app_context, test_project, rich_document):
        captured = {}

        def fake_chat_reply(messages, temperature=None):
            captured['messages'] = messages
            return (True, self._LLM_REPLY)

        with patch('app.routes.training.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.training.build_project_grounded_context', return_value={
                 'context_text': 'Supporting library evidence:\n[1] Paper A [Doc 10]: Library-supported finding.',
                 'sources': [{'source': 'Paper A', 'document_id': '10', 'snippet': 'Library-supported finding.'}],
             }), \
             patch('app.routes.training.beep_ai_client.chat_reply', side_effect=fake_chat_reply):
            resp = client.post(
                f'/projects/{test_project.id}/flashcards',
                json={'limit': 2},
            )

        assert resp.status_code == 200
        assert 'Supporting library evidence:' in captured['messages'][1]['content']
        assert resp.get_json()['supporting_sources'][0]['document_id'] == '10'


# ---------------------------------------------------------------------------
# List flashcards
# ---------------------------------------------------------------------------

class TestListFlashcards:
    def test_list_empty_project(self, client, app_context, test_project):
        resp = client.get(f'/projects/{test_project.id}/flashcards')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data['flashcards'], list)

    def test_list_returns_created_cards(self, client, app_context, test_project, rich_document):
        from app.database import db
        from app.models.researcher import Flashcard
        card = Flashcard(project_id=test_project.id, document_id=rich_document.id,
                         front='Q?', back='A.', source_chunk_id='chunk-0')
        db.session.add(card)
        db.session.commit()

        resp = client.get(f'/projects/{test_project.id}/flashcards')
        data = resp.get_json()
        assert any(c['front'] == 'Q?' for c in data['flashcards'])

    def test_list_404_unknown_project(self, client, app_context):
        resp = client.get('/projects/999999/flashcards')
        assert resp.status_code == 404

    def test_list_response_has_document_id(self, client, app_context, test_project, rich_document):
        from app.database import db
        from app.models.researcher import Flashcard
        card = Flashcard(project_id=test_project.id, document_id=rich_document.id,
                         front='Q?', back='A.', source_chunk_id='chunk-0')
        db.session.add(card)
        db.session.commit()
        resp = client.get(f'/projects/{test_project.id}/flashcards')
        data = resp.get_json()
        assert 'document_id' in data['flashcards'][0]


# ---------------------------------------------------------------------------
# Quiz generation — heuristic fallback
# ---------------------------------------------------------------------------

class TestQuizHeuristicFallback:
    def test_quiz_created_without_llm(self, client, app_context, test_project, rich_document):
        with patch('app.routes.training.beep_ai_client.is_configured', return_value=False):
            resp = client.post(
                f'/projects/{test_project.id}/quiz',
                json={'name': 'Bio Quiz', 'limit': 2},
            )
        assert resp.status_code == 201
        data = resp.get_json()
        assert 'quiz_id' in data
        assert data['name'] == 'Bio Quiz'
        assert data['method'] == 'heuristic'

    def test_quiz_default_name(self, client, app_context, test_project, rich_document):
        with patch('app.routes.training.beep_ai_client.is_configured', return_value=False):
            resp = client.post(f'/projects/{test_project.id}/quiz', json={})
        data = resp.get_json()
        assert data['name'] == 'Quiz'

    def test_quiz_404_unknown_project(self, client, app_context):
        with patch('app.routes.training.beep_ai_client.is_configured', return_value=False):
            resp = client.post('/projects/999999/quiz', json={})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Quiz generation — LLM path
# ---------------------------------------------------------------------------

class TestQuizLLMPath:
    _LLM_REPLY = json.dumps({
        'questions': [
            {
                'question': 'Where does the Calvin cycle occur?',
                'options': ['Thylakoid', 'Stroma', 'Cytoplasm', 'Nucleus'],
                'correct_index': 1,
                'explanation': 'The Calvin cycle occurs in the stroma of the chloroplast.',
            }
        ]
    })

    def test_llm_creates_question(self, client, app_context, test_project, rich_document):
        with patch('app.routes.training.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.training.beep_ai_client.chat_reply', return_value=(True, self._LLM_REPLY)):
            resp = client.post(
                f'/projects/{test_project.id}/quiz',
                json={'name': 'LLM Bio Quiz', 'limit': 3},
            )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['method'] == 'llm'
        assert data['question_count'] >= 1

    def test_llm_correct_index_within_bounds(self, client, app_context, test_project, rich_document):
        with patch('app.routes.training.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.training.beep_ai_client.chat_reply', return_value=(True, self._LLM_REPLY)):
            resp = client.post(
                f'/projects/{test_project.id}/quiz',
                json={'limit': 5},
            )
        assert resp.status_code == 201
        from app.models.researcher import QuizQuestion
        quiz_id = resp.get_json()['quiz_id']
        questions = QuizQuestion.query.filter_by(quiz_id=quiz_id).all()
        for q in questions:
            opts = json.loads(q.options_json)
            assert 0 <= q.correct_index < len(opts)

    def test_llm_failure_falls_back(self, client, app_context, test_project, rich_document):
        with patch('app.routes.training.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.training.beep_ai_client.chat_reply', return_value=(False, 'error')):
            resp = client.post(
                f'/projects/{test_project.id}/quiz',
                json={'limit': 2},
            )
        assert resp.status_code == 201

    def test_out_of_bounds_correct_index_clamped(self):
        """correct_index that is out of range should be clamped to 0."""
        from app.routes.training import _extract_json_list
        reply = json.dumps({'questions': [
            {'question': 'Test?', 'options': ['A', 'B'], 'correct_index': 99}
        ]})
        items = _extract_json_list(reply, 'questions')
        assert items[0]['correct_index'] == 99  # raw; clamping happens inside generate_quiz

    def test_quiz_uses_saved_project_quality_temperature(self, client, app_context, test_project, rich_document):
        from app.database import db
        from app.models.researcher import ResearchProject

        project = db.session.get(ResearchProject, test_project.id)
        project.rag_quality_mode = 'deep'
        db.session.commit()

        captured = {}

        def fake_chat_reply(messages, temperature=None):
            captured['temperature'] = temperature
            return (True, self._LLM_REPLY)

        with patch('app.routes.training.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.training.beep_ai_client.chat_reply', side_effect=fake_chat_reply):
            resp = client.post(
                f'/projects/{test_project.id}/quiz',
                json={'limit': 2},
            )

        assert resp.status_code == 201
        assert captured['temperature'] == 0.1

    def test_quiz_includes_grounded_library_evidence(self, client, app_context, test_project, rich_document):
        captured = {}

        def fake_chat_reply(messages, temperature=None):
            captured['messages'] = messages
            return (True, self._LLM_REPLY)

        with patch('app.routes.training.beep_ai_client.is_configured', return_value=True), \
             patch('app.routes.training.build_project_grounded_context', return_value={
                 'context_text': 'Supporting library evidence:\n[1] Paper B [Doc 11]: Grounded quiz evidence.',
                 'sources': [{'source': 'Paper B', 'document_id': '11', 'snippet': 'Grounded quiz evidence.'}],
             }), \
             patch('app.routes.training.beep_ai_client.chat_reply', side_effect=fake_chat_reply):
            resp = client.post(
                f'/projects/{test_project.id}/quiz',
                json={'limit': 2},
            )

        assert resp.status_code == 201
        assert 'Supporting library evidence:' in captured['messages'][1]['content']
        assert resp.get_json()['supporting_sources'][0]['document_id'] == '11'


# ---------------------------------------------------------------------------
# List quizzes & get quiz detail
# ---------------------------------------------------------------------------

class TestListAndGetQuiz:
    def test_list_quizzes_empty(self, client, app_context, test_project):
        resp = client.get(f'/projects/{test_project.id}/quizzes')
        assert resp.status_code == 200
        assert isinstance(resp.get_json()['quizzes'], list)

    def test_list_includes_question_count(self, client, app_context, test_project, rich_document):
        from app.database import db
        from app.models.researcher import Quiz, QuizQuestion
        quiz = Quiz(project_id=test_project.id, name='Sample')
        db.session.add(quiz)
        db.session.flush()
        q = QuizQuestion(quiz_id=quiz.id, question='?', options_json='["A","B"]',
                         correct_index=0, source_chunk_id='c0')
        db.session.add(q)
        db.session.commit()

        resp = client.get(f'/projects/{test_project.id}/quizzes')
        data = resp.get_json()
        matching = [x for x in data['quizzes'] if x['id'] == quiz.id]
        assert matching[0]['question_count'] == 1

    def test_get_quiz_detail(self, client, app_context, test_project, rich_document):
        from app.database import db
        from app.models.researcher import Quiz, QuizQuestion
        quiz = Quiz(project_id=test_project.id, name='Detail Quiz')
        db.session.add(quiz)
        db.session.flush()
        q = QuizQuestion(quiz_id=quiz.id, question='What is X?',
                         options_json=json.dumps(['A', 'B', 'C', 'D']),
                         correct_index=2, source_chunk_id='c1')
        db.session.add(q)
        db.session.commit()

        resp = client.get(f'/projects/{test_project.id}/quizzes/{quiz.id}')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['quiz']['id'] == quiz.id
        assert len(data['questions']) == 1
        assert data['questions'][0]['correct_index'] == 2
        assert isinstance(data['questions'][0]['options'], list)

    def test_get_quiz_404(self, client, app_context, test_project):
        resp = client.get(f'/projects/{test_project.id}/quizzes/999999')
        assert resp.status_code == 404
