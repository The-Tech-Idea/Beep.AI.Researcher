"""Build grounded evidence blocks for project-backed AI generation."""

from typing import Any, Dict, List, Optional

from app.services.beep_ai_client import query_project_rag


def build_project_grounded_context(
    project,
    query: str,
    user_id: Optional[int] = None,
    max_results: int = 4,
    max_chars_per_result: int = 320,
) -> Dict[str, Any]:
    """Return a formatted evidence block plus normalized source metadata."""
    normalized_query = str(query or "").strip()
    if not normalized_query or not getattr(project, "collection_id", None):
        return {"context_text": "", "sources": []}

    ok, result_payload = query_project_rag(
        project=project,
        query=normalized_query,
        max_results=max_results,
        user_id=user_id,
        grounded_only=False,
        return_citations=True,
        return_full=True,
    )
    if not ok or not isinstance(result_payload, dict):
        return {"context_text": "", "sources": []}

    normalized_sources: List[Dict[str, Any]] = []
    for item in (result_payload.get("results") or []):
        if not isinstance(item, dict):
            continue
        raw_content = str(item.get("content") or item.get("text") or item.get("snippet") or "").strip()
        if not raw_content:
            continue

        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        source_name = (
            str(item.get("source") or item.get("filename") or metadata.get("filename") or "").strip()
            or "Document library source"
        )
        document_id = str(
            item.get("document_id")
            or metadata.get("researcher_doc_id")
            or metadata.get("document_id")
            or ""
        ).strip()
        snippet = " ".join(raw_content.split())[:max_chars_per_result].strip()
        if not snippet:
            continue

        normalized_sources.append(
            {
                "source": source_name,
                "document_id": document_id,
                "snippet": snippet,
                "score": item.get("score") or item.get("relevance_score") or item.get("confidence"),
            }
        )
        if len(normalized_sources) >= max_results:
            break

    if not normalized_sources:
        return {"context_text": "", "sources": []}

    evidence_lines = ["Supporting library evidence:"]
    for index, entry in enumerate(normalized_sources, start=1):
        source_label = entry["source"]
        if entry["document_id"]:
            source_label = f"{source_label} [Doc {entry['document_id']}]"
        evidence_lines.append(f"[{index}] {source_label}: {entry['snippet']}")

    return {
        "context_text": "\n".join(evidence_lines),
        "sources": normalized_sources,
    }
