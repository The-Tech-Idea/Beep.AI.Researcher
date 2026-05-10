"""Report writing help for the project editor."""

import logging
from flask import Blueprint, request, jsonify
from flask_login import login_required

from app.routes.project_api_guard import (
    guard_project_blueprint,
    get_guarded_project_or_404 as get_project_or_404,
)
from app.services import beep_ai_client
from app.services import report_writing_service
from app.services.project_grounded_context_service import build_project_grounded_context
from app.services.project_grounded_prompt_service import (
    build_grounded_user_prompt,
    merge_supporting_sources,
)
from app.services.project_rag_preferences_service import (
    resolve_project_generation_temperature,
)

logger = logging.getLogger(__name__)

report_bp = Blueprint("report_writing", __name__)


# ---------------------------------------------------------------------------
# Action system prompts
# ---------------------------------------------------------------------------

_ACTION_PROMPTS = {
    "grammar": (
        "You are an expert academic editor. Fix only grammar, spelling, and punctuation "
        "errors in the text below. Preserve meaning, style, and all terminology exactly. "
        "Return ONLY the corrected text, no explanation."
    ),
    "paraphrase": (
        "You are an academic writing assistant. Paraphrase the following text while "
        "preserving its full meaning. Use different vocabulary and sentence structures. "
        "Return ONLY the paraphrased text."
    ),
    "tone": (
        "You are an academic writing assistant. Rewrite the following text in a formal, "
        "objective, academic tone suitable for a research paper. "
        "Return ONLY the rewritten text."
    ),
    "summarize": (
        "You are a research assistant. Summarize the following text into 2-3 concise "
        "sentences that capture the key points. Return ONLY the summary."
    ),
    "expand": (
        "You are an academic writing assistant. Expand the following text with more "
        "detail, supporting context, and academic depth. Keep the same topic and tone. "
        "Return ONLY the expanded text."
    ),
    "academic_rewrite": (
        "You are an expert in academic writing. Rewrite the following text using "
        "appropriate academic vocabulary, passive constructions where suitable, "
        "and hedging language. Return ONLY the rewritten text."
    ),
    "simplify": (
        "You are a science communicator. Simplify the following text so it is "
        "accessible to a general audience, without losing accuracy. "
        "Return ONLY the simplified text."
    ),
    "legal_plain": (
        "You are a legal writing assistant. Rewrite the following legal text in "
        "plain English that a non-lawyer can understand, while preserving all legal "
        "meaning. Return ONLY the plain-English version."
    ),
    "medical_lay": (
        "You are a healthcare communication specialist. Rewrite the following clinical "
        "text in patient-friendly language at a 6th-grade reading level. "
        "Return ONLY the rewritten text."
    ),
    "academic_paraphrase_v2": (
        "You are an expert academic editor. Paraphrase the following text while "
        'strictly preserving all in-text citation markers (e.g. "(Smith, 2020)", '
        '"[1]", "Author et al., YYYY"). Do NOT rewrite, remove, or alter any '
        "citation markers. Use different vocabulary and sentence structures for the "
        "surrounding prose. Return ONLY the paraphrased text."
    ),
    "clarity": (
        "You are an academic writing assistant specialising in clarity and concision. "
        "Identify and remove redundant phrases, nominalizations, and wordy constructions "
        "in the text below. Preserve the original meaning exactly. "
        "Return ONLY the improved text."
    ),
}

_VALID_ACTIONS = set(_ACTION_PROMPTS.keys())


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@report_bp.route("/<int:project_id>/writing/assist", methods=["POST"])
@login_required
def assist_writing(project_id):
    """Improve selected report text with the writing assistant."""
    project = get_project_or_404(project_id)
    data = request.get_json() or {}
    # build_project_grounded_context(...) remains the grounded entry point; the service receives it via injection.
    payload, status_code = report_writing_service.assist_writing(
        project,
        data,
        action_prompts=_ACTION_PROMPTS,
        valid_actions=_VALID_ACTIONS,
        beep_ai_client_module=beep_ai_client,
        build_project_grounded_context_fn=build_project_grounded_context,
        build_grounded_user_prompt_fn=build_grounded_user_prompt,
        merge_supporting_sources_fn=merge_supporting_sources,
        resolve_project_generation_temperature_fn=resolve_project_generation_temperature,
    )
    return jsonify(payload), status_code


# ---------------------------------------------------------------------------
# Citation formatting
# ---------------------------------------------------------------------------


@report_bp.route("/<int:project_id>/writing/format-citations", methods=["POST"])
@login_required
def format_citations(project_id):
    """Format all (or a subset of) project references in the requested style.

    Request body::

        {
            "style": "apa",            // apa | mla | chicago | bibtex
            "reference_ids": [1, 2]    // optional — omit to format all project refs
        }

    Response::

        {
            "style": "apa",
            "citations": [
                {"id": 1, "citation_key": "Smith2020", "formatted": "Smith, J. (2020)…"},
                …
            ]
        }
    """
    project = get_project_or_404(project_id)
    payload, status_code = report_writing_service.format_citations(
        project, request.get_json() or {}
    )
    return jsonify(payload), status_code


# ---------------------------------------------------------------------------
# Citation marker scan
# ---------------------------------------------------------------------------


@report_bp.route("/<int:project_id>/writing/citation-scan", methods=["POST"])
@login_required
def citation_scan(project_id):
    """Scan text for author-year in-text markers and check against the library.

    Request body::

        {"text": "…Smith (2020) argued that…Jones & Doe (2019)…"}

    Response::

        {
            "markers": [
                {
                    "raw": "Smith (2020)",
                    "author": "Smith",
                    "year": "2020",
                    "matched_ref_id": 3,
                    "matched_citation_key": "Smith2020"
                }
            ],
            "matched_count": 1,
            "unmatched_count": 1
        }
    """
    project = get_project_or_404(project_id)
    payload, status_code = report_writing_service.citation_scan(
        project, request.get_json() or {}
    )
    return jsonify(payload), status_code


# ---------------------------------------------------------------------------
# Overlap check
# ---------------------------------------------------------------------------


@report_bp.route("/<int:project_id>/writing/overlap-check", methods=["POST"])
@login_required
def overlap_check(project_id):
    """Compare a passage against the project corpus and return similar sources.

    Request body::

        {
            "text": "…the passage to check…",
            "threshold": 0.20,    // optional min similarity score (0-1)
            "persist": true       // optional — set false to skip DB write
        }

    Response::

        {
            "check_id": 12,
            "status": "completed",
            "similarity_score": 42.0,   // as percentage
            "matches": [
                {
                    "source": "document name",
                    "document_id": 5,
                    "reference_id": 3,
                    "citation_key": "Smith2020",
                    "snippet": "…",
                    "score": 0.82,
                    "string_similarity": 0.35
                }
            ],
            "note": "Project-grounded overlap check only."
        }
    """
    project = get_project_or_404(project_id)
    payload, status_code = report_writing_service.overlap_check(
        project, request.get_json() or {}
    )
    return jsonify(payload), status_code


# ---------------------------------------------------------------------------
# Phase 4 — Writing Quality Analysis (structured offset-mapped issues)
# ---------------------------------------------------------------------------


@report_bp.route("/<int:project_id>/writing/analyse", methods=["POST"])
@login_required
def analyse_writing(project_id):
    """Analyse a manuscript section for writing quality issues.

    Request body::

        {
            "text": "The paragraph to analyse…",
            "section_id": 5       // optional — stored on ManuscriptSection if provided
        }

    Response::

        {
            "overall_score": 72.5,
            "tone_score": 80.0,
            "clarity_score": 65.0,
            "grammar_score": 78.0,
            "issues": [
                {"type": "passive_voice", "severity": "warning",
                 "text": "was found to be", "suggestion": "found",
                 "offset": 12, "length": 13}
            ],
            "suggestions": ["Consider more active constructions"]
        }
    """
    project = get_project_or_404(project_id)
    from app.services.writing_quality_service import WritingQualityService

    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    section_id = data.get("section_id")

    payload, status_code = WritingQualityService().analyse(text, section_id=section_id)
    return jsonify(payload), status_code


# ---------------------------------------------------------------------------
# Phase 4 — Citation Draft (project-level themed paragraph with citation markers)
# ---------------------------------------------------------------------------


@report_bp.route("/<int:project_id>/writing/citations-draft", methods=["POST"])
@login_required
def citation_draft(project_id):
    """Generate a themed paragraph draft with inline citation markers.

    Request body::

        {"theme": "Impact of X on Y"}

    Response::

        {
            "draft": "The paragraph text with [Cite: DOI] markers…",
            "theme": "Impact of X on Y",
            "markers": {"markers": [...], "cited_dois": [...], "total_markers": 1},
            "formatted_citations": [{"doi": "...", "title": "...", ...}],
            "source_count": 5
        }
    """
    project = get_project_or_404(project_id)
    from app.models.researcher.researcher_references import Reference
    from app.services.citation_draft_service import CitationDraftService

    data = request.get_json() or {}
    theme = (data.get("theme") or "").strip()
    if not theme:
        return jsonify({"error": "theme is required"}), 400

    references = Reference.query.filter_by(project_id=project.id).all()
    sources = [
        {
            "doi": r.doi or "",
            "title": r.title or "",
            "abstract": r.abstract or "",
            "authors": (r.authors_json or [])
            if isinstance(r.authors_json, list)
            else [],
            "year": r.publication_year,
        }
        for r in references
        if r.doi or r.title
    ][:20]

    if not sources:
        return jsonify(
            {"error": "No references with DOI or title in this project"}
        ), 400

    payload, status_code = CitationDraftService().draft(theme, sources)
    return jsonify(payload), status_code


guard_project_blueprint(report_bp)
