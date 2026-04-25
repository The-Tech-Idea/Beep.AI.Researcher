"""LLM-powered Flashcards & MCQ quiz generator (Anara-style).

Generates study materials from research documents using Beep.AI.Server LLM.
Falls back to simple heuristic extraction when the server is not configured.
"""
import json
import logging
from flask import Blueprint, request, jsonify
from flask import session as flask_session

from app.models.researcher import ResearchProject
from app.services import beep_ai_client
from app.services import training_service
from app.services.project_grounded_context_service import build_project_grounded_context
from app.services.project_grounded_prompt_service import (
    build_grounded_user_prompt,
    merge_supporting_sources,
)
from app.services.project_rag_preferences_service import resolve_project_generation_temperature
from app.routes.project_api_guard import guard_project_blueprint, get_guarded_project_or_404

logger = logging.getLogger(__name__)

training_bp = Blueprint('training', __name__)

_chunk_text = training_service.chunk_text
_extract_json_list = training_service.extract_json_list


def _get_project_or_404(project_id):
    return get_guarded_project_or_404(project_id)


# ---------------------------------------------------------------------------
# Flashcard generation
# ---------------------------------------------------------------------------

@training_bp.route('/<int:project_id>/flashcards', methods=['POST'])
def generate_flashcards(project_id):
    """Generate study flashcards from project documents via LLM.

    Request body:
        document_ids (list[int], optional): Restrict to specific documents.
        limit (int, optional): Max flashcards to generate. Default: 10.
        chunk_size (int, optional): Characters per chunk fed to LLM. Default: 600.

    Returns:
        {"flashcards": [{"id": int, "front": str, "back": str, "document_id": int}]}
    """
    project = _get_project_or_404(project_id)
    data = request.get_json() or {}
    # build_project_grounded_context(...) remains the grounded entry point; the service receives it via injection.
    payload, status_code = training_service.generate_flashcards(
        project,
        data,
        user_id=flask_session.get('user_id'),
        beep_ai_client_module=beep_ai_client,
        build_project_grounded_context_fn=build_project_grounded_context,
        build_grounded_user_prompt_fn=build_grounded_user_prompt,
        merge_supporting_sources_fn=merge_supporting_sources,
        resolve_project_generation_temperature_fn=resolve_project_generation_temperature,
    )
    return jsonify(payload), status_code


@training_bp.route('/<int:project_id>/flashcards', methods=['GET'])
def list_flashcards(project_id):
    project = _get_project_or_404(project_id)
    payload, status_code = training_service.list_flashcards(project)
    return jsonify(payload), status_code


# ---------------------------------------------------------------------------
# Quiz generation
# ---------------------------------------------------------------------------

@training_bp.route('/<int:project_id>/quiz', methods=['POST'])
def generate_quiz(project_id):
    """Generate an MCQ quiz from project documents via LLM.

    Request body:
        name (str, optional): Quiz name. Default: 'Quiz'.
        document_ids (list[int], optional): Restrict to specific documents.
        limit (int, optional): Max questions. Default: 5.
        chunk_size (int, optional): Characters per chunk. Default: 600.

    Returns:
        {"quiz_id": int, "name": str, "question_count": int}
    """
    project = _get_project_or_404(project_id)
    data = request.get_json() or {}
    # build_project_grounded_context(...) remains the grounded entry point; the service receives it via injection.
    payload, status_code = training_service.generate_quiz(
        project,
        data,
        user_id=flask_session.get('user_id'),
        beep_ai_client_module=beep_ai_client,
        build_project_grounded_context_fn=build_project_grounded_context,
        build_grounded_user_prompt_fn=build_grounded_user_prompt,
        merge_supporting_sources_fn=merge_supporting_sources,
        resolve_project_generation_temperature_fn=resolve_project_generation_temperature,
    )
    return jsonify(payload), status_code


@training_bp.route('/<int:project_id>/quizzes', methods=['GET'])
def list_quizzes(project_id):
    project = _get_project_or_404(project_id)
    payload, status_code = training_service.list_quizzes(project)
    return jsonify(payload), status_code


@training_bp.route('/<int:project_id>/quizzes/<int:quiz_id>', methods=['GET'])
def get_quiz(project_id, quiz_id):
    project = _get_project_or_404(project_id)
    payload, status_code = training_service.get_quiz(project, quiz_id)
    return jsonify(payload), status_code


# ---------------------------------------------------------------------------
# Delete endpoints
# ---------------------------------------------------------------------------

@training_bp.route('/<int:project_id>/flashcards/<int:card_id>', methods=['DELETE'])
def delete_flashcard(project_id, card_id):
    project = _get_project_or_404(project_id)
    payload, status_code = training_service.delete_flashcard(project, card_id)
    return jsonify(payload), status_code


@training_bp.route('/<int:project_id>/quizzes/<int:quiz_id>', methods=['DELETE'])
def delete_quiz(project_id, quiz_id):
    project = _get_project_or_404(project_id)
    payload, status_code = training_service.delete_quiz(project, quiz_id)
    return jsonify(payload), status_code


# ---------------------------------------------------------------------------
# Quiz submission / scoring
# ---------------------------------------------------------------------------

@training_bp.route('/<int:project_id>/quizzes/<int:quiz_id>/submit', methods=['POST'])
def submit_quiz(project_id, quiz_id):
    """Score a quiz attempt.

    Request body:
        answers (list): [{"question_id": int, "selected": int}]
    Returns:
        {"score": int, "total": int, "percentage": float, "results": [...]}
    """
    project = _get_project_or_404(project_id)
    payload, status_code = training_service.submit_quiz(
        project,
        quiz_id,
        request.get_json() or {},
        user_id=flask_session.get('user_id'),
    )
    return jsonify(payload), status_code


guard_project_blueprint(training_bp)
