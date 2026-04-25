from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy import func

from app.models.researcher import Code, ResearcherDocument

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 300
_MAX_CHUNKS = 20


def codebook_summary(codes) -> str:
    lines = []
    for code in codes:
        description = f" - {code.description}" if code.description else ""
        lines.append(f"  * {code.name}{description}")
    return "\n".join(lines) if lines else "  (no codes defined yet)"


def chunk_text_with_offsets(text: str, size: int = _CHUNK_SIZE):
    index = 0
    chunk_number = 0
    while index < len(text):
        yield text[index:index + size], index, f"chunk-{chunk_number}"
        index += size
        chunk_number += 1


def suggest_codes(
    project,
    data: dict[str, Any],
    *,
    beep_ai_client_module,
    build_project_grounded_context_fn,
    build_grounded_user_prompt_fn,
    merge_supporting_sources_fn,
):
    from app.models.researcher.researcher_coding import CodedReference

    text = (data.get("text") or data.get("selected_text") or "").strip()
    top_k = min(int(data.get("top_k", 5)), 15)
    if not text:
        return {"error": "text or selected_text is required"}, 400

    codes = Code.query.filter_by(project_id=project.id).all()
    codebook = codebook_summary(codes)
    codes_by_name = {code.name.lower(): code for code in codes}

    if beep_ai_client_module.is_configured():
        system_prompt = (
            "You are an expert qualitative researcher specializing in thematic analysis. "
            "Given a passage of text and an existing codebook, suggest the most relevant "
            "qualitative codes from the codebook that apply to the passage. "
            "If no existing code fits well, you may propose a new code with a name and "
            'description. Format your response as valid JSON:\n{"suggestions": [{"name": "...", "rationale": "...", "is_new": false}]}'
        )
        user_prompt = (
            f"CODEBOOK:\n{codebook}\n\n"
            f'TEXT TO CODE:\n"""{text[:2000]}"""\n\n'
            f"Return the top {top_k} most relevant codes as JSON."
        )
        grounded_context = build_project_grounded_context_fn(
            project,
            text[:1200],
            max_results=4,
            max_chars_per_result=260,
        )
        user_prompt = build_grounded_user_prompt_fn(
            user_prompt,
            grounded_context,
            "Use the selected text as the primary source and keep every code suggestion supported by the connected document library evidence below.",
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        ok, reply = beep_ai_client_module.chat_reply(messages)
        if ok:
            try:
                json_str = re.search(r"\{.*\}", reply, re.DOTALL)
                llm_data = json.loads(json_str.group()) if json_str else {}
                raw_suggestions = llm_data.get("suggestions") or []
                suggestions = []
                for suggestion in raw_suggestions[:top_k]:
                    name = (suggestion.get("name") or "").strip()
                    if not name:
                        continue
                    existing_code = codes_by_name.get(name.lower())
                    suggestions.append(
                        {
                            "id": existing_code.id if existing_code else None,
                            "name": name,
                            "description": existing_code.description if existing_code else suggestion.get("description", ""),
                            "color": existing_code.color if existing_code else "#6366f1",
                            "existing": bool(existing_code),
                            "is_new": bool(suggestion.get("is_new", not existing_code)),
                            "rationale": suggestion.get("rationale", ""),
                        }
                    )
                return {
                    "suggestions": suggestions,
                    "method": "llm",
                    "supporting_sources": merge_supporting_sources_fn([], grounded_context),
                }, 200
            except (json.JSONDecodeError, AttributeError) as exc:
                logger.warning("Could not parse LLM code suggestions: %s", exc)

    usage = {
        code_id: count
        for code_id, count in Code.query.session.query(CodedReference.code_id, func.count(CodedReference.id))
        .group_by(CodedReference.code_id)
        .filter(CodedReference.code_id.in_([code.id for code in codes]))
        .all()
    }
    sorted_codes = sorted(codes, key=lambda code: usage.get(code.id, 0), reverse=True)
    suggestions = [
        {
            "id": code.id,
            "name": code.name,
            "description": code.description or "",
            "color": code.color,
            "existing": True,
            "is_new": False,
            "rationale": "Frequency-ranked existing code (server not configured).",
        }
        for code in sorted_codes[:top_k]
    ]
    return {
        "suggestions": suggestions,
        "method": "fallback",
        "note": "Beep.AI.Server not configured. Configure beep_ai_server_url for LLM code suggestions.",
        "supporting_sources": [],
    }, 200


def auto_suggest_codes(
    project,
    data: dict[str, Any],
    *,
    beep_ai_client_module,
    build_project_grounded_context_fn,
    build_grounded_user_prompt_fn,
    merge_supporting_sources_fn,
):
    document_id = data.get("document_id")
    chunk_size = min(int(data.get("chunk_size", _CHUNK_SIZE)), 1000)
    if not document_id:
        return {"proposals": [], "error": "document_id required"}, 400

    document = ResearcherDocument.query.filter_by(project_id=project.id, id=document_id).first_or_404()
    if not document.text_content:
        return {"proposals": [], "note": "Document has no text content."}, 200

    codes = Code.query.filter_by(project_id=project.id).all()
    if not codes:
        return {
            "proposals": [],
            "note": "No codes defined in project. Add codes first, then run auto-suggest.",
        }, 200

    codebook = codebook_summary(codes)
    codes_by_name = {code.name.lower(): code for code in codes}

    if not beep_ai_client_module.is_configured():
        return {
            "proposals": [],
            "method": "unavailable",
            "note": "Beep.AI.Server not configured. Configure beep_ai_server_url for LLM auto-coding.",
        }, 200

    system_prompt = (
        "You are a qualitative researcher. Given a text chunk and a codebook, "
        "identify which codes from the codebook apply to the chunk. "
        'Respond with valid JSON: {"codes": [{"name": "...", "rationale": "..."}]}'
    )

    proposals = []
    chunks = list(chunk_text_with_offsets(document.text_content, chunk_size))[:_MAX_CHUNKS]
    grounded_context = build_project_grounded_context_fn(
        project,
        document.text_content[: min(chunk_size * 2, 1200)],
        max_results=4,
        max_chars_per_result=260,
    )
    supporting_sources = merge_supporting_sources_fn([], grounded_context)

    for chunk_text, start_offset, chunk_id in chunks:
        chunk_text = chunk_text.strip()
        if not chunk_text:
            continue

        user_prompt = (
            f"CODEBOOK:\n{codebook}\n\n"
            f'TEXT CHUNK:\n"""{chunk_text}"""\n\n'
            "Which codes apply? Respond as JSON."
        )
        user_prompt = build_grounded_user_prompt_fn(
            user_prompt,
            grounded_context,
            "Keep each coding suggestion supported by the connected document library evidence below.",
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        ok, reply = beep_ai_client_module.chat_reply(messages)
        chunk_codes = []
        if ok:
            try:
                json_str = re.search(r"\{.*\}", reply, re.DOTALL)
                llm_data = json.loads(json_str.group()) if json_str else {}
                for suggestion in llm_data.get("codes") or []:
                    name = (suggestion.get("name") or "").strip()
                    if not name:
                        continue
                    existing = codes_by_name.get(name.lower())
                    chunk_codes.append(
                        {
                            "id": existing.id if existing else None,
                            "name": name,
                            "existing": bool(existing),
                            "rationale": suggestion.get("rationale", ""),
                        }
                    )
            except (json.JSONDecodeError, AttributeError):
                pass

        if chunk_codes:
            proposals.append(
                {
                    "chunk_id": chunk_id,
                    "start_offset": start_offset,
                    "text_excerpt": chunk_text[:150] + ("..." if len(chunk_text) > 150 else ""),
                    "codes": chunk_codes,
                }
            )

    return {
        "proposals": proposals,
        "document_id": document_id,
        "chunks_processed": len(chunks),
        "method": "llm",
        "supporting_sources": supporting_sources,
    }, 200
