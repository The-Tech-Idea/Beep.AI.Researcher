"""Grounding client — calls Beep.AI.Server anti-hallucination endpoints.

Provides wrappers for:
  - POST /v1/rag/evaluate-grounding
  - POST /v1/rag/contradiction
"""
import hashlib
import logging
from typing import Optional, List, Dict, Any

from app.services.beep_ai_client import _post_v1, is_configured

logger = logging.getLogger(__name__)


def evaluate_grounding(
    answer_text: str,
    sources: List[Dict[str, Any]],
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """
    Call the Server's evaluate_grounding endpoint.

    Args:
        answer_text: The LLM-generated answer string.
        sources: List of RAG source chunks (each with at least 'content').
        threshold: Minimum overlap score to consider a sentence grounded.

    Returns:
        dict with grounding_score, attributed_answer, ungrounded_sentences, sources.
        On error returns a dict with grounding_score=None and error message.
    """
    if not is_configured():
        return {'grounding_score': None, 'error': 'Server not configured'}

    ok, result = _post_v1('/v1/rag/evaluate-grounding', json_data={
        'answer': answer_text,
        'sources': sources,
        'threshold': threshold,
    })

    if not ok:
        logger.warning(f'[GroundingClient] evaluate_grounding failed: {result}')
        return {'grounding_score': None, 'error': str(result)}

    return result


def detect_contradictions(
    statement: str,
    sources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Call the Server's contradiction detection endpoint.

    Args:
        statement: A claim or sentence to check.
        sources: RAG source chunks to compare against.

    Returns:
        dict with severity, details, etc.
        On error returns a dict with severity=None and error message.
    """
    if not is_configured():
        return {'severity': None, 'error': 'Server not configured'}

    ok, result = _post_v1('/v1/rag/contradiction', json_data={
        'statement': statement,
        'sources': sources,
    })

    if not ok:
        logger.warning(f'[GroundingClient] contradiction failed: {result}')
        return {'severity': None, 'error': str(result)}

    return result


def run_post_generation_checks(
    project_id: int,
    session_id: Optional[str],
    step_name: str,
    answer_text: str,
    sources: List[Dict[str, Any]],
    temperature_used: Optional[float] = None,
    grounding_threshold: float = 0.5,
    contradiction_flag_threshold: str = 'high',
) -> Dict[str, Any]:
    """
    Run grounding + contradiction checks and persist a HallucinationAuditLog row.

    Returns a summary dict with grounding_score, flagged, contradictions, warning.
    """
    from app.database import db
    from app.models.researcher.hallucination_audit import HallucinationAuditLog

    # --- 1. Grounding evaluation ---
    grounding = evaluate_grounding(answer_text, sources, threshold=grounding_threshold)
    grounding_score = grounding.get('grounding_score')
    ungrounded = grounding.get('ungrounded_sentences') or []
    rag_chunk_ids = [s.get('id') or s.get('doc_id', '') for s in sources]

    # --- 2. Contradiction detection (check each ungrounded sentence) ---
    contradictions = []
    if sources:
        contra = detect_contradictions(answer_text, sources)
        severity = contra.get('severity')
        if severity:
            contradictions.append(contra)

    # --- 3. Flag decision ---
    flagged = False
    warning = None
    if grounding_score is not None and grounding_score < grounding_threshold:
        flagged = True
        warning = 'Low grounding score — answer may not be well supported by sources.'
    if any(c.get('severity') == contradiction_flag_threshold for c in contradictions):
        flagged = True
        warning = 'WARNING: This answer may contradict your source documents.'

    # --- 4. Persist audit log ---
    prompt_hash = hashlib.sha256(answer_text.encode('utf-8')).hexdigest()
    try:
        log = HallucinationAuditLog(
            project_id=project_id,
            session_id=session_id,
            step_name=step_name,
            prompt_hash=prompt_hash,
            answer_text=answer_text,
            grounding_score=grounding_score,
            ungrounded_sentences=ungrounded,
            contradictions_found=contradictions if contradictions else None,
            rag_chunk_ids=rag_chunk_ids,
            temperature_used=temperature_used,
            flagged=flagged,
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f'[GroundingClient] Failed to persist audit log: {e}')
        db.session.rollback()

    return {
        'grounding_score': grounding_score,
        'ungrounded_sentences': ungrounded,
        'contradictions': contradictions,
        'flagged': flagged,
        'warning': warning,
    }
