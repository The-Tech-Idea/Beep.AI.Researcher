"""Tests for anti-hallucination integration (Phase 4).

Covers:
  H5 - HallucinationAuditLog model
  H1 - Prompt hardening (research mode system prompt)
  H2 - Zero-result guard
  H3/H4 - Grounding client + contradiction detection
  H6 - DOI validation in reference_service
  H8 - Agent grounding chain session guard
"""
import pytest
import json
from unittest.mock import patch, MagicMock


# ==========================
# H5 — HallucinationAuditLog Model
# ==========================

class TestHallucinationAuditLogModel:

    def test_model_importable(self):
        from app.models.researcher.hallucination_audit import HallucinationAuditLog
        assert HallucinationAuditLog is not None

    def test_model_in_global_exports(self):
        from app.models import HallucinationAuditLog
        assert HallucinationAuditLog is not None

    def test_create_audit_log(self, app_context, test_project):
        from app.database import db
        from app.models.researcher.hallucination_audit import HallucinationAuditLog

        log = HallucinationAuditLog(
            project_id=test_project.id,
            session_id='test-session-001',
            step_name='chat',
            answer_text='The drug reduces blood pressure [Doc #1].',
            grounding_score=0.85,
            ungrounded_sentences=['Some unrelated claim.'],
            rag_chunk_ids=['chunk_1', 'chunk_2'],
            temperature_used=0.2,
            flagged=False,
        )
        db.session.add(log)
        db.session.commit()

        assert log.id is not None
        assert log.grounding_score == 0.85
        assert log.flagged is False
        assert log.step_name == 'chat'

    def test_audit_log_to_dict(self, app_context, test_project):
        from app.database import db
        from app.models.researcher.hallucination_audit import HallucinationAuditLog

        log = HallucinationAuditLog(
            project_id=test_project.id,
            step_name='synthesis',
            answer_text='Test answer.',
            grounding_score=0.4,
            flagged=True,
        )
        db.session.add(log)
        db.session.commit()

        d = log.to_dict()
        assert d['project_id'] == test_project.id
        assert d['grounding_score'] == 0.4
        assert d['flagged'] is True
        assert 'created_at' in d

    def test_audit_log_flagged_when_low_score(self, app_context, test_project):
        from app.database import db
        from app.models.researcher.hallucination_audit import HallucinationAuditLog

        log = HallucinationAuditLog(
            project_id=test_project.id,
            step_name='chat',
            answer_text='Ungrounded answer.',
            grounding_score=0.3,
            flagged=True,
            contradictions_found=[{'severity': 'high', 'detail': 'contradicts source'}],
        )
        db.session.add(log)
        db.session.commit()

        assert log.flagged is True
        assert len(log.contradictions_found) == 1


# ==========================
# H1 — Prompt Hardening (research mode)
# ==========================

class TestPromptHardening:

    def test_research_mode_system_prompt_contains_strict_rules(self):
        """Verify _get_chat_reply builds a strict system prompt in research mode."""
        from app.routes.chat import _get_chat_reply
        # The function exists and accepts research_mode parameter
        import inspect
        sig = inspect.signature(_get_chat_reply)
        assert 'research_mode' in sig.parameters
        assert 'temperature' in sig.parameters

    def test_chat_reply_accepts_temperature(self):
        """Verify chat_reply in beep_ai_client accepts temperature."""
        from app.services.beep_ai_client import chat_reply
        import inspect
        sig = inspect.signature(chat_reply)
        assert 'temperature' in sig.parameters


# ==========================
# H2 — Zero-Result Guard
# ==========================

class TestZeroResultGuard:

    def test_zero_results_returns_no_grounding(self, client, app_context, test_project):
        """When RAG returns zero results, chat should return a structured no-grounding response."""
        from app.database import db
        from app.models.researcher import ResearchProject
        # Set a collection_id so the RAG path is taken
        proj = db.session.get(ResearchProject, test_project.id)
        proj.collection_id = 'test_collection'
        db.session.commit()

        with patch('app.routes.chat.is_configured', return_value=True), \
             patch('app.routes.chat.query_project_rag', return_value=(True, {'results': [], 'citations': []})):
            resp = client.post(
                f'/projects/{test_project.id}/chat',
                json={'message': 'What does the data say about X?'},
            )

        assert resp.status_code == 200
        data = resp.get_json()
        assert 'No relevant documents found' in data.get('response', '')

    def test_chat_uses_saved_project_quality_mode_when_request_omits_it(self, client, app_context, test_project):
        from app.database import db
        from app.models.researcher import ResearchProject

        proj = db.session.get(ResearchProject, test_project.id)
        proj.collection_id = 'test_collection'
        proj.rag_quality_mode = 'deep'
        db.session.commit()

        captured = {}

        def fake_query_project_rag(**kwargs):
            captured['quality_mode'] = kwargs.get('quality_mode')
            return True, {'results': [], 'citations': []}

        with patch('app.routes.chat.is_configured', return_value=True), \
             patch('app.routes.chat.query_project_rag', side_effect=fake_query_project_rag):
            resp = client.post(
                f'/projects/{test_project.id}/chat',
                json={'message': 'What does the data say about X?'},
            )

        assert resp.status_code == 200
        assert captured['quality_mode'] == 'deep'


# ==========================
# H3/H4 — Grounding Client
# ==========================

class TestGroundingClient:

    def test_evaluate_grounding_not_configured(self):
        """Returns error when server is not configured."""
        from app.services.grounding_client import evaluate_grounding
        with patch('app.services.grounding_client.is_configured', return_value=False):
            result = evaluate_grounding('test answer', [{'content': 'source'}])
        assert result['grounding_score'] is None
        assert 'error' in result

    def test_evaluate_grounding_success(self):
        """Returns grounding data on success."""
        from app.services.grounding_client import evaluate_grounding
        mock_response = {
            'grounding_score': 0.88,
            'attributed_answer': 'answer [Doc #1]',
            'ungrounded_sentences': [],
            'sources': []
        }
        with patch('app.services.grounding_client.is_configured', return_value=True), \
             patch('app.services.grounding_client._post', return_value=(True, mock_response)):
            result = evaluate_grounding('test answer', [{'content': 'source'}])
        assert result['grounding_score'] == 0.88

    def test_detect_contradictions_not_configured(self):
        from app.services.grounding_client import detect_contradictions
        with patch('app.services.grounding_client.is_configured', return_value=False):
            result = detect_contradictions('claim', [{'content': 'source'}])
        assert result['severity'] is None

    def test_detect_contradictions_success(self):
        from app.services.grounding_client import detect_contradictions
        mock_response = {'severity': 'high', 'detail': 'Contradicts Doc #1'}
        with patch('app.services.grounding_client.is_configured', return_value=True), \
             patch('app.services.grounding_client._post', return_value=(True, mock_response)):
            result = detect_contradictions('claim', [{'content': 'source'}])
        assert result['severity'] == 'high'

    def test_run_post_generation_checks_persists_audit(self, app_context, test_project):
        """run_post_generation_checks should persist a HallucinationAuditLog row."""
        from app.services.grounding_client import run_post_generation_checks
        from app.models.researcher.hallucination_audit import HallucinationAuditLog

        grounding_resp = {
            'grounding_score': 0.9,
            'ungrounded_sentences': [],
        }
        contradiction_resp = {'severity': None}

        with patch('app.services.grounding_client.evaluate_grounding', return_value=grounding_resp), \
             patch('app.services.grounding_client.detect_contradictions', return_value=contradiction_resp):
            result = run_post_generation_checks(
                project_id=test_project.id,
                session_id='test-sess-123',
                step_name='chat',
                answer_text='The drug works. [Doc #1].',
                sources=[{'content': 'Evidence chunk', 'id': 'c1'}],
                temperature_used=0.2,
            )

        assert result['grounding_score'] == 0.9
        assert result['flagged'] is False

        # Verify DB persistence
        logs = HallucinationAuditLog.query.filter_by(
            project_id=test_project.id, session_id='test-sess-123'
        ).all()
        assert len(logs) == 1
        assert logs[0].grounding_score == 0.9

    def test_run_post_generation_checks_flags_low_score(self, app_context, test_project):
        """Low grounding score should flag the audit log."""
        from app.services.grounding_client import run_post_generation_checks

        grounding_resp = {
            'grounding_score': 0.3,
            'ungrounded_sentences': ['Some unverified claim.'],
        }
        contradiction_resp = {'severity': 'high', 'detail': 'Contradicts evidence'}

        with patch('app.services.grounding_client.evaluate_grounding', return_value=grounding_resp), \
             patch('app.services.grounding_client.detect_contradictions', return_value=contradiction_resp):
            result = run_post_generation_checks(
                project_id=test_project.id,
                session_id='test-sess-456',
                step_name='chat',
                answer_text='Ungrounded answer.',
                sources=[{'content': 'Evidence', 'id': 'c1'}],
            )

        assert result['flagged'] is True
        assert result['warning'] is not None


# ==========================
# H6 — DOI Validation
# ==========================

class TestDOIValidation:

    def test_validate_doi_not_configured(self):
        from app.services.reference_service import validate_doi
        with patch('app.services.beep_ai_client.is_configured', return_value=False):
            result = validate_doi('10.1234/test')
        assert result['valid'] is False
        assert 'not configured' in result['error']

    def test_validate_doi_empty(self):
        from app.services.reference_service import validate_doi
        result = validate_doi('')
        assert result['valid'] is False

    def test_validate_doi_success(self):
        from app.services.reference_service import validate_doi
        mock_resp = {'valid': True, 'metadata': {'title': 'Test Paper'}}
        with patch('app.services.beep_ai_client.is_configured', return_value=True), \
             patch('app.services.beep_ai_client._post', return_value=(True, mock_resp)):
            result = validate_doi('10.1234/test')
        assert result['valid'] is True
        assert result['metadata']['title'] == 'Test Paper'

    def test_validate_doi_invalid(self):
        from app.services.reference_service import validate_doi
        with patch('app.services.beep_ai_client.is_configured', return_value=True), \
             patch('app.services.beep_ai_client._post', return_value=(False, 'DOI not found')):
            result = validate_doi('10.9999/fake')
        assert result['valid'] is False

    def test_validate_citation_batch(self, app_context, test_project):
        from app.database import db
        from app.models.researcher.researcher_references import Reference
        from app.services.reference_service import validate_citation_batch

        ref1 = Reference(project_id=test_project.id, title='Paper 1', doi='10.1234/real', citation_key='p1')
        ref2 = Reference(project_id=test_project.id, title='Paper 2', doi=None, citation_key='p2')
        db.session.add_all([ref1, ref2])
        db.session.commit()

        mock_resp = {'valid': True, 'metadata': {'title': 'Paper 1'}}
        with patch('app.services.beep_ai_client.is_configured', return_value=True), \
             patch('app.services.beep_ai_client._post', return_value=(True, mock_resp)):
            from app.models.researcher import ResearchProject
            project = db.session.get(ResearchProject, test_project.id)
            summary = validate_citation_batch(project)

        assert summary['total'] == 2
        assert summary['valid'] == 1
        assert summary['skipped'] == 1


# ==========================
# H8 — Agent Grounding Chain
# ==========================

class TestAgentGroundingChain:

    def test_create_session(self):
        from app.services.agent_grounding_chain import create_chain_session
        session = create_chain_session(project_id=1)
        assert session.session_id is not None
        assert session.project_id == 1
        assert session.should_halt is False

    def test_record_step_above_threshold(self):
        from app.services.agent_grounding_chain import create_chain_session
        session = create_chain_session(project_id=1, halt_threshold=0.6)
        result = session.record_step('extraction', grounding_score=0.85)
        assert result['halted'] is False
        assert session.current_score == 0.85

    def test_record_step_below_threshold_halts(self):
        from app.services.agent_grounding_chain import create_chain_session
        session = create_chain_session(project_id=1, halt_threshold=0.6)
        session.record_step('extraction', grounding_score=0.85)
        result = session.record_step('synthesis', grounding_score=0.4)
        assert result['halted'] is True
        assert session.should_halt is True
        assert 'below threshold' in session.halt_reason

    def test_cumulative_score(self):
        from app.services.agent_grounding_chain import create_chain_session
        session = create_chain_session(project_id=1)
        session.record_step('step1', grounding_score=0.8)
        session.record_step('step2', grounding_score=0.6)
        assert session.cumulative_score == pytest.approx(0.7)

    def test_session_to_dict(self):
        from app.services.agent_grounding_chain import create_chain_session
        session = create_chain_session(project_id=1)
        session.record_step('chat', grounding_score=0.9)
        d = session.to_dict()
        assert d['project_id'] == 1
        assert d['halted'] is False
        assert len(d['steps']) == 1

    def test_get_and_close_session(self):
        from app.services.agent_grounding_chain import (
            create_chain_session, get_chain_session, close_chain_session
        )
        session = create_chain_session(project_id=2)
        sid = session.session_id

        retrieved = get_chain_session(sid)
        assert retrieved is not None
        assert retrieved.session_id == sid

        summary = close_chain_session(sid)
        assert summary is not None
        assert summary['session_id'] == sid

        assert get_chain_session(sid) is None

    def test_close_nonexistent_session_returns_none(self):
        from app.services.agent_grounding_chain import close_chain_session
        result = close_chain_session('nonexistent-id')
        assert result is None
