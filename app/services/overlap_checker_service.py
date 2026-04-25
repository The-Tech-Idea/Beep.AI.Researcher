"""Project-grounded overlap checker (Phase 06).

Compares a passage of text against the project's RAG corpus and returns
matching source references with similarity scores.  This is **project-
grounded only** — it does NOT perform web-scale plagiarism detection.

Design decisions
----------------
* Uses ``query_project_rag`` (already in ``beep_ai_client``) with the passage
  as the query to retrieve semantically similar chunks.
* Maps retrieved chunks back to ``Reference`` rows via the ``document_id``
  field stored in RAG metadata (set by the attachment-ingest pipeline).
* Stores the result in ``PlagiarismCheck`` (reusing the existing model)
  with ``service='internal_rag'`` — no new audit table needed.
* Returns a lightweight payload suitable for an editor side-panel.
"""
from __future__ import annotations

import difflib
from typing import Any, Dict, List, Optional, Tuple

from app.database import db
from app.core.time_utils import utcnow_naive


# Minimum RAG score to report a source as overlapping.
DEFAULT_SCORE_THRESHOLD = 0.20


def _resolve_references_for_doc_ids(
    project_id: int,
    doc_ids: List[int],
) -> Dict[int, Any]:
    """Return {document_id: reference_dict} for refs linked to these docs."""
    if not doc_ids:
        return {}
    from app.models.researcher.researcher_references import Reference

    refs = (
        Reference.query
        .filter(
            Reference.project_id == project_id,
            Reference.document_id.in_(doc_ids),
        )
        .all()
    )
    return {ref.document_id: ref for ref in refs}


def check_overlap(
    project,
    passage: str,
    user_id: Optional[int] = None,
    max_results: int = 8,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    persist: bool = True,
) -> Dict[str, Any]:
    """Compare *passage* against the project corpus.

    Returns::

        {
            "check_id": 12,           // PlagiarismCheck.id (null if not persisted)
            "status": "completed",
            "similarity_score": 0.42, // max score across all matches (0-100)
            "matches": [
                {
                    "source": "filename or title",
                    "document_id": 5,
                    "reference_id": 3,
                    "citation_key": "Smith2020",
                    "snippet": "the retrieved passage text...",
                    "score": 0.82,
                    "string_similarity": 0.35,  // trigram overlap with passage
                }
            ],
            "note": "Project-grounded overlap check only."
        }

    If ``persist=True`` the result is saved to ``plagiarism_checks`` before
    returning.  Pass ``persist=False`` in tests or ephemeral checks.
    """
    from app.services.beep_ai_client import query_project_rag
    from app.models.researcher.sector_models import PlagiarismCheck

    result_payload: Dict[str, Any] = {
        "check_id": None,
        "status": "error",
        "similarity_score": 0.0,
        "matches": [],
        "note": "Project-grounded overlap check only.",
    }

    if not passage or not passage.strip():
        result_payload["status"] = "error"
        result_payload["error"] = "Empty passage"
        return result_payload

    collection_id = getattr(project, "collection_id", None)
    if not collection_id:
        # No RAG collection — can't check
        result_payload["status"] = "skipped"
        result_payload["note"] = "No RAG collection attached to this project."
        return result_payload

    # ── Create pending row ────────────────────────────────────────────────
    check_row: Optional[PlagiarismCheck] = None
    if persist:
        check_row = PlagiarismCheck(
            project_id=project.id,
            document_id=_get_sentinel_document_id(project.id),
            service="internal_rag",
            status="pending",
            performed_by=user_id,
        )
        db.session.add(check_row)
        db.session.commit()

    # ── Query RAG ─────────────────────────────────────────────────────────
    ok, rag_result = query_project_rag(
        project=project,
        query=passage,
        max_results=max_results,
        user_id=user_id,
        grounded_only=False,
        return_citations=True,
        return_full=True,
    )

    if not ok or not isinstance(rag_result, dict):
        if check_row:
            check_row.status = "error"
            db.session.commit()
        result_payload["status"] = "error"
        result_payload["error"] = "RAG query failed"
        return result_payload

    # ── Build matches ──────────────────────────────────────────────────────
    raw_items = rag_result.get("results") or []
    doc_ids = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        doc_id = (
            item.get("document_id")
            or meta.get("researcher_doc_id")
            or meta.get("document_id")
        )
        if doc_id:
            try:
                doc_ids.append(int(doc_id))
            except (ValueError, TypeError):
                pass

    ref_by_doc = _resolve_references_for_doc_ids(project.id, list(set(doc_ids)))

    matches = []
    max_score = 0.0

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        score = float(
            item.get("score")
            or item.get("relevance_score")
            or item.get("confidence")
            or 0.0
        )
        if score < score_threshold:
            continue

        meta = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        doc_id = (
            item.get("document_id")
            or meta.get("researcher_doc_id")
            or meta.get("document_id")
        )
        doc_id_int: Optional[int] = None
        try:
            doc_id_int = int(doc_id) if doc_id is not None else None
        except (ValueError, TypeError):
            pass

        chunk_text = str(
            item.get("content") or item.get("text") or item.get("snippet") or ""
        ).strip()

        # String-level overlap using trigram similarity
        string_sim = difflib.SequenceMatcher(
            None,
            passage.lower(),
            chunk_text.lower(),
        ).ratio()

        ref = ref_by_doc.get(doc_id_int) if doc_id_int else None
        source_name = (
            str(item.get("source") or item.get("filename") or meta.get("filename") or "").strip()
            or (ref.title if ref else "Document library source")
        )

        matches.append(
            {
                "source": source_name,
                "document_id": doc_id_int,
                "reference_id": ref.id if ref else None,
                "citation_key": ref.citation_key if ref else None,
                "snippet": chunk_text[:400],
                "score": round(score, 4),
                "string_similarity": round(string_sim, 4),
            }
        )
        if score > max_score:
            max_score = score

    # Sort by score descending
    matches.sort(key=lambda m: m["score"], reverse=True)

    # Overall score as percentage (0-100)
    overall_pct = round(max_score * 100, 1)

    # ── Persist result ────────────────────────────────────────────────────
    flagged = [
        {"text": m["snippet"], "source": m["source"], "similarity": m["score"]}
        for m in matches
    ]
    if check_row:
        check_row.similarity_score = overall_pct
        check_row.flagged_passages_json = flagged
        check_row.status = "completed"
        check_row.completed_at = utcnow_naive()
        db.session.commit()

    result_payload.update(
        {
            "check_id": check_row.id if check_row else None,
            "status": "completed",
            "similarity_score": overall_pct,
            "matches": matches,
        }
    )
    return result_payload


def _get_sentinel_document_id(project_id: int) -> int:
    """Return any document id belonging to the project, or raise.

    ``PlagiarismCheck.document_id`` is NOT NULL — use the most recently
    created project document as the row anchor when the check is not tied to
    a specific document.
    """
    from app.models.researcher.researcher_documents import ResearcherDocument

    doc = (
        ResearcherDocument.query
        .filter_by(project_id=project_id)
        .order_by(ResearcherDocument.id.desc())
        .first()
    )
    if doc is None:
        raise ValueError(
            f"Cannot persist overlap check: project {project_id} has no documents."
        )
    return doc.id
