"""AI-assisted qualitative code suggestions (NVivo-style) via Beep.AI.Server LLM.

suggest_codes:    Suggest relevant codes for a selected text snippet.
auto_suggest_codes: Bulk-propose codes for all chunks of a document.

Falls back to frequency-ranking of existing codes when not configured.
"""
import json
import logging
import re
from flask import Blueprint, request, jsonify

from app.models.researcher import ResearchProject
from app.routes.project_api_guard import guard_project_blueprint, get_guarded_project_or_404
from app.services import beep_ai_client
from app.services import ai_coding_service
from app.services.project_grounded_context_service import build_project_grounded_context
from app.services.project_grounded_prompt_service import (
    build_grounded_user_prompt,
    merge_supporting_sources,
)

logger = logging.getLogger(__name__)

ai_coding_bp = Blueprint('ai_coding', __name__)

# Max characters per chunk for auto-suggest batch processing
_CHUNK_SIZE = 300
# Cap number of chunks processed in one auto-suggest call
_MAX_CHUNKS = 20


def _get_project_or_404(project_id):
    return get_guarded_project_or_404(project_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _codebook_summary(codes) -> str:
    """Build a compact codebook string for the LLM prompt."""
    return ai_coding_service.codebook_summary(codes)


def _chunk_text_with_offsets(text: str, size: int = _CHUNK_SIZE):
    """Yield (chunk_text, start_offset, chunk_id) tuples."""
    yield from ai_coding_service.chunk_text_with_offsets(text, size)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@ai_coding_bp.route('/<int:project_id>/codes/suggest', methods=['POST'])
def suggest_codes(project_id):
    """Suggest qualitative codes for a selected text passage.

    Request body:
        text (str, required): Selected text to code.
        selected_text (str, alias for text).
        document_id (int, optional): Source document context.
        top_k (int, optional): Number of suggestions to return. Default: 5.

    Returns:
        {
            "suggestions": [
                {"id": int|null, "name": str, "description": str, "existing": bool,
                 "relevance": str, "rationale": str}
            ],
            "method": "llm|fallback"
        }
    """
    project = _get_project_or_404(project_id)
    # build_project_grounded_context(...) remains the grounded entry point; the service receives it via injection.
    payload, status_code = ai_coding_service.suggest_codes(
        project,
        request.get_json() or {},
        beep_ai_client_module=beep_ai_client,
        build_project_grounded_context_fn=build_project_grounded_context,
        build_grounded_user_prompt_fn=build_grounded_user_prompt,
        merge_supporting_sources_fn=merge_supporting_sources,
    )
    return jsonify(payload), status_code


@ai_coding_bp.route('/<int:project_id>/codes/auto-suggest', methods=['POST'])
def auto_suggest_codes(project_id):
    """Bulk AI-suggested codes for all chunks of a document.

    Request body:
        document_id (int, required): Document to analyse.
        chunk_size (int, optional): Characters per chunk. Default: 300.

    Returns:
        {
            "proposals": [
                {
                    "chunk_id": str,
                    "start_offset": int,
                    "text_excerpt": str,
                    "codes": [{"name": str, "id": int|null, "existing": bool, "rationale": str}]
                }
            ],
            "method": "llm|unavailable"
        }
    """
    project = _get_project_or_404(project_id)
    # build_project_grounded_context(...) remains the grounded entry point; the service receives it via injection.
    payload, status_code = ai_coding_service.auto_suggest_codes(
        project,
        request.get_json() or {},
        beep_ai_client_module=beep_ai_client,
        build_project_grounded_context_fn=build_project_grounded_context,
        build_grounded_user_prompt_fn=build_grounded_user_prompt,
        merge_supporting_sources_fn=merge_supporting_sources,
    )
    return jsonify(payload), status_code


guard_project_blueprint(ai_coding_bp)

