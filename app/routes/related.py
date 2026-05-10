"""Project file matching and citation support helpers.

These routes keep the response shape predictable for the UI while returning
plain-language notes that make sense to non-technical users.
"""

import logging
import re
from flask import Blueprint, request, jsonify
from flask_login import login_required

from app.models.researcher import ResearchProject, ResearcherDocument
from app.routes.route_entity_lookup import get_entity_or_404
from app.services import beep_ai_client

logger = logging.getLogger(__name__)

related_bp = Blueprint("related", __name__)


# ---------------------------------------------------------------------------
# Local fallback helpers
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> set:
    """Return set of lowercase word tokens (>=4 chars) from text."""
    if not text:
        return set()
    return set(re.findall(r"\b\w{4,}\b", text.lower()))


def _jaccard(a: set, b: set) -> float:
    """Jaccard similarity between two token sets."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _local_related(doc, others, limit: int = 10):
    """Rank other docs by text overlap with the selected file."""
    query_tokens = _tokenize(doc.text_content or "")
    scored = []
    for other in others:
        sim = _jaccard(query_tokens, _tokenize(other.text_content or ""))
        if sim > 0:
            scored.append((sim, other))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "document_id": o.id,
            "filename": o.filename,
            "similarity_score": round(sim, 4),
            "method": "local_jaccard",
        }
        for sim, o in scored[:limit]
    ]


def _local_citations(text: str, docs, limit: int = 5):
    """Return docs whose content overlaps with the draft text (token overlap)."""
    query_tokens = _tokenize(text)
    scored = []
    for doc in docs:
        if not doc.text_content:
            continue
        overlap_score = len(query_tokens & _tokenize(doc.text_content))
        if overlap_score > 0:
            # Find snippet: first sentence that contains an overlapping word
            first_word = next(iter(query_tokens & _tokenize(doc.text_content)), None)
            snippet = ""
            if first_word:
                for sent in re.split(r"(?<=[.!?])\s+", doc.text_content):
                    if first_word in sent.lower():
                        snippet = sent[:200]
                        break
            scored.append((overlap_score, doc, snippet))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "document_id": d.id,
            "filename": d.filename,
            "snippet": snip or (d.text_content or "")[:100] + "...",
            "overlap_score": score,
            "score": score,
            "method": "local_overlap",
        }
        for score, d, snip in scored[:limit]
    ]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@related_bp.route("/<int:project_id>/documents/<int:doc_id>/related", methods=["GET"])
@login_required
def related_documents(project_id, doc_id):
    """Find other project files that may help when reviewing a file."""
    project = get_entity_or_404(ResearchProject, project_id)
    doc = ResearcherDocument.query.filter_by(
        project_id=project.id, id=doc_id
    ).first_or_404()

    limit = min(int(request.args.get("limit", 10)), 50)

    if not doc.text_content:
        return jsonify(
            {
                "related": [],
                "note": "This file does not contain readable text yet.",
                "message": "No similar files could be reviewed because this file has no readable text.",
            }
        )

    # ── RAG semantic search ───────────────────────────────────────────────
    if beep_ai_client.is_configured():
        # Use key excerpt (first 500 chars) as the query
        query_excerpt = (doc.text_content or "")[:500].strip()
        ok, result = beep_ai_client.query_with_context(
            project=project,
            query=query_excerpt,
            max_results=limit + 1,  # +1 because the source doc may appear in results
            return_provenance=True,
        )
        if ok:
            results_list = []
            if isinstance(result, dict):
                items = result.get("results") or result.get("documents") or []
            elif isinstance(result, list):
                items = result
            else:
                items = []

            for item in items:
                item_doc_id = item.get("document_id") or (
                    item.get("metadata") or {}
                ).get("researcher_doc_id")
                # Skip self
                try:
                    if item_doc_id and int(item_doc_id) == doc.id:
                        continue
                except (ValueError, TypeError):
                    pass

                results_list.append(
                    {
                        "document_id": item_doc_id,
                        "filename": item.get("source") or item.get("filename") or "",
                        "snippet": (item.get("content") or "")[:200],
                        "similarity_score": item.get("confidence") or item.get("score"),
                        "page": item.get("page"),
                        "section": item.get("section"),
                        "method": "rag_semantic",
                    }
                )
                if len(results_list) >= limit:
                    break

            return jsonify(
                {
                    "related": results_list,
                    "method": "rag_semantic",
                    "message": (
                        f"Found {len(results_list)} other file"
                        f"{'s' if len(results_list) != 1 else ''} that may help with review."
                    ),
                }
            )
        else:
            logger.warning(
                "RAG related docs failed: %s — falling back to local", result
            )

    # ── Local fallback ─────────────────────────────────────────────────────
    others = (
        ResearcherDocument.query.filter_by(project_id=project.id)
        .filter(ResearcherDocument.id != doc.id)
        .all()
    )
    related = _local_related(doc, others, limit=limit)
    return jsonify(
        {
            "related": related,
            "method": "local_jaccard",
            "note": "A simpler text comparison was used for this file review.",
            "message": (
                f"Found {len(related)} other file"
                f"{'s' if len(related) != 1 else ''} with similar wording."
            ),
        }
    )


@related_bp.route("/<int:project_id>/writing/citations", methods=["POST"])
@login_required
def find_citations(project_id):
    """Find project files that may support a draft passage."""
    project = get_entity_or_404(ResearchProject, project_id)
    data = request.get_json() or {}
    text = (data.get("text") or data.get("draft") or "").strip()
    max_citations = min(int(data.get("max_citations", 5)), 20)

    if not text:
        return jsonify(
            {"error": "Enter the passage you want supporting files for."}
        ), 400

    # ── LLM citation finder ───────────────────────────────────────────────
    if beep_ai_client.is_configured():
        ok, result = beep_ai_client.find_citations_for_draft(
            project=project,
            draft_text=text,
            max_citations=max_citations,
        )
        if ok:
            citations = result.get("citations") or []
            normalised = []
            for c in citations:
                normalised.append(
                    {
                        "document_id": c.get("document_id"),
                        "filename": c.get("source") or c.get("filename") or "",
                        "snippet": (c.get("snippet") or "")[:300],
                        "relevance_score": c.get("relevance_score") or c.get("score"),
                        "suggested_inline": c.get("suggested_inline_citation") or "",
                        "method": "llm_rag",
                    }
                )
            return jsonify(
                {
                    "citations": normalised,
                    "method": "llm_rag",
                    "message": (
                        f"Found {len(normalised)} supporting file"
                        f"{'s' if len(normalised) != 1 else ''} for this draft passage."
                    ),
                }
            )
        else:
            logger.warning("Citation finder failed: %s — falling back to local", result)

    # ── Local fallback ─────────────────────────────────────────────────────
    docs = ResearcherDocument.query.filter_by(project_id=project.id).all()
    citations = _local_citations(text, docs, limit=max_citations)
    return jsonify(
        {
            "citations": citations,
            "method": "local_overlap",
            "note": "A simpler text comparison was used to suggest supporting files.",
            "message": (
                f"Found {len(citations)} file"
                f"{'s' if len(citations) != 1 else ''} with overlapping wording."
            ),
        }
    )
