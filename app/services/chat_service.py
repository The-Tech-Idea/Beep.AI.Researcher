from __future__ import annotations

from typing import Any

from app.database import db
from app.models.researcher import ChatMessage, ChatSession


def post_project_message(project, data: dict[str, Any], *, user_id=None, get_chat_reply_fn):
    content = (data.get("message") or data.get("content") or "").strip()
    session_id = data.get("session_id")
    mode = (data.get("mode") or "rag").strip().lower()
    requested_quality_mode = (data.get("quality_mode") or "").strip() or None
    quality_mode, _ = data["resolve_project_quality_mode_fn"](project, requested_quality_mode)
    research_mode = data.get("research_mode", True)
    temperature = data["resolve_project_generation_temperature_fn"](
        project,
        requested_quality_mode=requested_quality_mode,
        explicit_temperature=data.get("temperature"),
        research_mode=research_mode,
    )

    if not content:
        return {"error": "message required"}, 400

    if session_id:
        session = ChatSession.query.filter_by(project_id=project.id, id=session_id).first()
    else:
        session = None

    if session is None:
        session = ChatSession(project_id=project.id, created_by_id=user_id)
        db.session.add(session)
        db.session.flush()

    user_msg = ChatMessage(session_id=session.id, role="user", content=content)
    db.session.add(user_msg)
    db.session.commit()

    reply_result = get_chat_reply_fn(
        project,
        session,
        content,
        use_context=(mode != "local"),
        user_id=user_id,
        quality_mode=quality_mode,
        rewrite_query=data.get("rewrite_query"),
        hybrid_search=data.get("hybrid_search"),
        rerank=data.get("rerank"),
        grounded_only=data.get("grounded_only", True),
        research_mode=research_mode,
        temperature=temperature,
    )
    reply = reply_result.get("reply", "")
    sources = reply_result.get("sources", [])
    assistant_msg = ChatMessage(session_id=session.id, role="assistant", content=reply)
    db.session.add(assistant_msg)
    db.session.commit()

    return {
        "session_id": session.id,
        "message": {"role": "assistant", "content": reply},
        "response": reply,
        "sources": sources,
    }, 200


def get_chat_reply(
    project,
    session,
    user_content,
    *,
    use_context=True,
    user_id=None,
    quality_mode="balanced",
    rewrite_query=None,
    hybrid_search=None,
    rerank=None,
    grounded_only=True,
    research_mode=True,
    temperature=None,
    is_configured_fn,
    query_project_rag_fn,
    chat_reply_fn,
    get_scope_context_fn,
):
    context = ""
    sources = []

    if use_context:
        if not is_configured_fn() or not project.collection_id:
            return {
                "reply": (
                    "This project is not ready for file-based answers yet. "
                    "Ask an administrator to connect the document library service and link this project to a document library."
                ),
                "sources": [],
            }

        ok, result_payload = query_project_rag_fn(
            project=project,
            query=user_content,
            max_results=5,
            user_id=user_id,
            quality_mode=quality_mode,
            rewrite_query=rewrite_query,
            hybrid_search=hybrid_search,
            rerank=rerank,
            grounded_only=grounded_only,
            return_citations=True,
            return_full=True,
        )

        results = []
        if ok and isinstance(result_payload, dict):
            results = result_payload.get("results") or []
            citations = result_payload.get("citations") or []
            for citation in citations:
                sources.append(
                    {
                        "doc_id": citation.get("id") or "",
                        "chunk_id": "",
                        "name": citation.get("source") or citation.get("id") or "Source",
                    }
                )
        elif ok and isinstance(result_payload, list):
            results = result_payload

        if not results:
            return {
                "reply": "No relevant documents found in this project for that query.",
                "sources": [],
                "grounded": False,
                "confidence": 0.0,
            }

        context = "\n\n".join(d.get("content", d.get("text", str(d)))[:500] for d in results[:3])

    system_prompt = f"Answer based on context:\n{context}"
    if use_context and research_mode:
        system_prompt = (
            "You are a strict research assistant.\n"
            "Answer ONLY from the provided sources. Every factual claim must cite [Doc ID] inline. "
            "If the sources do not contain sufficient information, respond: 'Insufficient evidence in provided documents.' "
            "Do not infer, extrapolate, or combine knowledge beyond what the sources state.\n\n"
            f"Sources:\n{context}"
        )

    messages = [{"role": "system", "content": system_prompt}]
    previous_messages = ChatMessage.query.filter_by(session_id=session.id).order_by(ChatMessage.id).limit(12).all()
    for message in previous_messages[-8:]:
        messages.append({"role": message.role, "content": message.content})

    scope = get_scope_context_fn(project, user_id)
    ok, text = chat_reply_fn(
        messages,
        user_id=scope.get("user_id"),
        user_role=scope.get("user_role"),
        temperature=temperature,
    )
    reply_text = text if ok else f"Error: {text}"
    result = {"reply": reply_text, "sources": sources}

    if ok and use_context and sources:
        try:
            from app.services.grounding_client import run_post_generation_checks

            checks = run_post_generation_checks(
                project_id=project.id,
                session_id=str(session.id),
                step_name="chat",
                answer_text=reply_text,
                sources=[{"content": source.get("name", ""), "id": source.get("doc_id", "")} for source in sources],
                temperature_used=temperature,
            )
            result["grounding_score"] = checks.get("grounding_score")
            result["flagged"] = checks.get("flagged", False)
            if checks.get("warning"):
                result["warning"] = checks["warning"]
        except Exception:
            pass

    return result


def get_history(project, session_id):
    if not session_id:
        sessions = ChatSession.query.filter_by(project_id=project.id).all()
        return {
            "sessions": [
                {"id": session.id, "created_at": session.created_at.isoformat() if session.created_at else None}
                for session in sessions
            ]
        }, 200

    session = ChatSession.query.filter_by(project_id=project.id, id=session_id).first_or_404()
    messages = ChatMessage.query.filter_by(session_id=session.id).order_by(ChatMessage.created_at).all()
    return {
        "messages": [
            {
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at.isoformat() if message.created_at else None,
            }
            for message in messages
        ]
    }, 200


def search_library(project, data: dict[str, Any], *, user_id=None, is_configured_fn, query_project_rag_fn):
    from app.models.researcher.researcher_references import Reference
    from app.services.citation_formatter_service import SUPPORTED_STYLES, format_reference

    query = (data.get("query") or "").strip()
    if not query:
        return {"error": "query is required"}, 400

    style = (data.get("style") or "apa").lower()
    if style not in SUPPORTED_STYLES:
        style = "apa"
    max_results = min(int(data.get("max_results") or 5), 20)

    if not is_configured_fn() or not project.collection_id:
        return {"results": [], "note": "Document library not available for this project."}, 200

    ok, result_payload = query_project_rag_fn(
        project=project,
        query=query,
        max_results=max_results,
        user_id=user_id,
        return_citations=True,
        return_full=True,
    )

    reference_by_document_id = {}
    for reference in Reference.query.filter_by(project_id=project.id).all():
        if reference.document_id:
            reference_by_document_id[reference.document_id] = reference

    results = []
    raw_items = (result_payload.get("results") or []) if ok and isinstance(result_payload, dict) else []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        document_id = item.get("document_id") or metadata.get("researcher_doc_id") or metadata.get("document_id")
        try:
            document_id = int(document_id) if document_id is not None else None
        except (TypeError, ValueError):
            document_id = None
        reference = reference_by_document_id.get(document_id) if document_id else None
        results.append(
            {
                "source": str(
                    item.get("source")
                    or item.get("filename")
                    or metadata.get("filename")
                    or ""
                ).strip()
                or "Document library source",
                "snippet": str(item.get("content") or item.get("text") or item.get("snippet") or "")[:300].strip(),
                "score": item.get("score") or item.get("relevance_score") or 0.0,
                "reference_id": reference.id if reference else None,
                "citation": format_reference(reference, style) if reference else None,
            }
        )

    return {"results": results}, 200


def summarize_source(
    project,
    data: dict[str, Any],
    *,
    user_id=None,
    is_configured_fn,
    chat_reply_fn,
    get_scope_context_fn,
    resolve_project_generation_temperature_fn,
):
    from app.models.researcher.researcher_references import Reference

    reference_id = data.get("reference_id")
    if not reference_id:
        return {"error": "reference_id is required"}, 400

    reference = Reference.query.filter_by(id=reference_id, project_id=project.id).first()
    if reference is None:
        return {"error": "Reference not found"}, 404

    focus = (data.get("focus") or "").strip()
    authors = "; ".join(reference.get_authors()) if reference.get_authors() else "Unknown"
    content_parts = [
        f"Title: {reference.title}",
        f"Authors: {authors}",
        f"Year: {reference.year or 'n.d.'}",
    ]
    if reference.source:
        content_parts.append(f"Published in: {reference.source}")
    if reference.abstract:
        content_parts.append(f"Abstract: {reference.abstract}")
    source_text = "\n".join(content_parts)

    system_prompt = (
        "You are a research assistant. Summarize the following reference in 3-5 sentences, "
        "highlighting the main contribution and key findings."
    )
    if focus:
        system_prompt += f" Focus specifically on: {focus}."

    if not is_configured_fn():
        return {
            "reference_id": reference.id,
            "citation_key": reference.citation_key,
            "summary": reference.abstract or "(No abstract available; Beep.AI.Server not configured.)",
        }, 200

    scope = get_scope_context_fn(project, user_id)
    ok, summary = chat_reply_fn(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": source_text},
        ],
        user_id=scope.get("user_id"),
        user_role=scope.get("user_role"),
        temperature=resolve_project_generation_temperature_fn(project),
    )
    return {
        "reference_id": reference.id,
        "citation_key": reference.citation_key,
        "summary": summary.strip() if ok else (reference.abstract or "(Summary unavailable)"),
    }, 200


def insert_citation(project, data: dict[str, Any]):
    from app.models.researcher.researcher_references import Reference
    from app.services.citation_formatter_service import SUPPORTED_STYLES, format_reference

    reference_ids = data.get("reference_ids")
    if not reference_ids or not isinstance(reference_ids, list):
        return {"error": "reference_ids must be a non-empty list"}, 400

    style = (data.get("style") or "apa").lower()
    if style not in SUPPORTED_STYLES:
        style = "apa"

    references = Reference.query.filter(Reference.project_id == project.id, Reference.id.in_(reference_ids)).all()
    citations = [
        {
            "reference_id": reference.id,
            "citation_key": reference.citation_key,
            "formatted": format_reference(reference, style),
        }
        for reference in references
    ]
    return {"citations": citations}, 200
