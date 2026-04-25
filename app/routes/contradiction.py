"""Check whether project files disagree with a statement or question."""
import json
import logging
import re
from flask import Blueprint, request, jsonify

from app.models.researcher import ResearchProject, ResearcherDocument
from app.routes.route_entity_lookup import get_entity_or_404
from app.services import beep_ai_client

logger = logging.getLogger(__name__)

contradiction_bp = Blueprint('contradiction', __name__)


# ---------------------------------------------------------------------------
# Local heuristic fallback (no LLM required)
# ---------------------------------------------------------------------------

_NEGATION_RE = re.compile(
    r'\b(not|no|never|neither|nor|cannot|can\'t|doesn\'t|isn\'t|aren\'t|wasn\'t'
    r'|weren\'t|haven\'t|hadn\'t|won\'t|wouldn\'t|shouldn\'t|couldn\'t|didn\'t'
    r'|disagrees?|contrary|contradicts?|however|although|whereas|despite|'
    r'inconsistent|refutes?|disputes?)\b',
    re.IGNORECASE,
)

_CLAIM_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')


def _sentences(text: str):
    """Split text into sentences."""
    return [s.strip() for s in _CLAIM_SPLIT_RE.split(text or '') if len(s.strip()) > 20]


def _jaccard(a: set, b: set) -> float:
    """Jaccard similarity between two token sets."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _local_contradiction_heuristic(query: str, docs, max_pairs: int = 5):
    """
    Simple heuristic: find sentence pairs across different documents that
    (a) share key terms from the query and (b) contain negation markers.

    Returns a list of contradiction dicts (same shape as LLM response).
    """
    query_terms = set(re.findall(r'\b\w{4,}\b', query.lower()))
    if not query_terms:
        return []

    doc_sentences = []  # (doc_id, filename, sentence)
    for doc in docs:
        if not doc.text_content:
            continue
        for sent in _sentences(doc.text_content)[:50]:
            terms = set(re.findall(r'\b\w{4,}\b', sent.lower()))
            if query_terms & terms:
                doc_sentences.append((doc.id, doc.filename, sent))

    contradictions = []
    seen = set()

    for i, (id_a, fn_a, sent_a) in enumerate(doc_sentences):
        for id_b, fn_b, sent_b in doc_sentences[i + 1:]:
            if id_a == id_b:
                continue
            key = frozenset({id_a, id_b})
            if key in seen:
                continue
            seen.add(key)

            has_neg_a = bool(_NEGATION_RE.search(sent_a))
            has_neg_b = bool(_NEGATION_RE.search(sent_b))

            if has_neg_a or has_neg_b:
                terms_a = set(re.findall(r'\b\w{4,}\b', sent_a.lower()))
                terms_b = set(re.findall(r'\b\w{4,}\b', sent_b.lower()))
                shared = query_terms & terms_a & terms_b
                if shared:
                    contradictions.append({
                        'claim_a': sent_a[:200],
                        'source_a': {'document_id': id_a, 'filename': fn_a},
                        'claim_b': sent_b[:200],
                        'source_b': {'document_id': id_b, 'filename': fn_b},
                        'shared_terms': list(shared),
                        'severity': 'low',
                        'explanation': 'Possible disagreement found in files that use the same key terms.',
                        'detected_by': 'local_heuristic',
                    })
                    if len(contradictions) >= max_pairs:
                        return contradictions

    return contradictions


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@contradiction_bp.route('/<int:project_id>/contradictions', methods=['POST'])
def detect_contradictions(project_id):
    """Check whether project files contain conflicting statements."""
    project = get_entity_or_404(ResearchProject, project_id)
    data = request.get_json() or {}
    query = (data.get('query') or data.get('text') or '').strip()

    if not query:
        return jsonify({
            'contradictions': [],
            'message': 'Enter a statement or research question to review.',
        }), 400

    document_ids = data.get('document_ids') or []
    max_sources = int(data.get('max_sources', 10))

    # ── LLM path ─────────────────────────────────────────────────────────
    if beep_ai_client.is_configured():
        ok, result = beep_ai_client.detect_contradictions(
            project=project,
            query=query,
            document_ids=document_ids or None,
            max_sources=max_sources,
        )
        if ok:
            contradictions = result.get('contradictions') or []
            normalised = []
            for c in contradictions:
                normalised.append({
                    'claim_a': c.get('claim_a') or c.get('statement_a') or '',
                    'source_a': c.get('source_a') or {},
                    'claim_b': c.get('claim_b') or c.get('statement_b') or '',
                    'source_b': c.get('source_b') or {},
                    'severity': c.get('severity', 'medium'),
                    'explanation': c.get('explanation') or c.get('reason') or '',
                    'detected_by': 'llm',
                })
            return jsonify({
                'contradictions': normalised,
                'total_sources_checked': result.get('total_sources_checked', len(normalised)),
                'method': 'llm',
                'message': (
                    f'Found {len(normalised)} place'
                    f'{"s" if len(normalised) != 1 else ""} where your files may disagree.'
                    if normalised else 'No clear disagreements were found in the reviewed files.'
                ),
            })
        else:
            logger.warning('AI contradiction detection failed: %s — falling back to heuristic', result)

    # ── Local heuristic fallback ─────────────────────────────────────────
    docs_q = ResearcherDocument.query.filter_by(project_id=project.id)
    if document_ids:
        docs_q = docs_q.filter(ResearcherDocument.id.in_(document_ids))
    docs = docs_q.limit(max_sources).all()

    local = _local_contradiction_heuristic(query, docs)
    return jsonify({
        'contradictions': local,
        'total_sources_checked': len(docs),
        'method': 'local_heuristic',
        'message': (
            f'Found {len(local)} possible disagreement'
            f'{"s" if len(local) != 1 else ""} using a simpler text review.'
            if local else 'No clear disagreements were found in the reviewed files.'
        ),
        'note': 'A simpler text review was used because the full assistant review is not available right now.',
    })

