from __future__ import annotations

from typing import Any


def assist_writing(
    project,
    data: dict[str, Any],
    *,
    action_prompts,
    valid_actions,
    beep_ai_client_module,
    build_project_grounded_context_fn,
    build_grounded_user_prompt_fn,
    merge_supporting_sources_fn,
    resolve_project_generation_temperature_fn,
):
    text = (data.get("text") or "").strip()
    action = (data.get("action") or "paraphrase").lower()
    context_hint = (data.get("context") or "").strip()
    model = data.get("model")

    if not text:
        return {"error": "Select or enter some report text first."}, 400
    if len(text) > 10000:
        return {"error": "This section is too long for one writing request. Try a shorter selection."}, 400
    if action not in valid_actions:
        return {"error": "That writing action is not available."}, 400

    if beep_ai_client_module.is_configured():
        system_prompt = action_prompts[action]
        user_content = f"[Context: {context_hint}]\n\n{text}" if context_hint else text
        grounded_context = build_project_grounded_context_fn(
            project,
            context_hint or text,
            max_results=4,
            max_chars_per_result=320,
        )
        user_content = build_grounded_user_prompt_fn(
            user_content,
            grounded_context,
            "Use the connected document library evidence below to keep the rewrite grounded in this project's research context.",
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        ok, suggested = beep_ai_client_module.chat_reply(
            messages,
            model=model,
            temperature=resolve_project_generation_temperature_fn(project),
        )
        if ok:
            return {
                "original": text,
                "suggested": suggested.strip(),
                "action": action,
                "word_count_original": len(text.split()),
                "word_count_suggested": len(suggested.split()),
                "method": "llm",
                "supporting_sources": merge_supporting_sources_fn([], grounded_context),
            }, 200

    return {
        "original": text,
        "suggested": text,
        "action": action,
        "word_count_original": len(text.split()),
        "word_count_suggested": len(text.split()),
        "method": "fallback",
        "note": "The writing assistant is not available right now, so your text has been left unchanged.",
        "supporting_sources": [],
    }, 200


def format_citations(project, data: dict[str, Any]):
    from app.models.researcher.researcher_references import Reference
    from app.services.citation_formatter_service import SUPPORTED_STYLES, format_reference_list

    style = (data.get("style") or "apa").lower()
    if style not in SUPPORTED_STYLES:
        return {"error": f'style must be one of: {", ".join(SUPPORTED_STYLES)}'}, 400

    reference_ids = data.get("reference_ids")
    query = Reference.query.filter_by(project_id=project.id)
    if reference_ids:
        if not isinstance(reference_ids, list):
            return {"error": "reference_ids must be a list of integers"}, 400
        query = query.filter(Reference.id.in_(reference_ids))

    references = query.order_by(Reference.id).all()
    return {
        "style": style,
        "citations": format_reference_list(references, style),
    }, 200


def citation_scan(project, data: dict[str, Any]):
    from app.models.researcher.researcher_references import Reference
    from app.services.citation_formatter_service import scan_citation_markers

    text = (data.get("text") or "").strip()
    if not text:
        return {"error": "text is required"}, 400
    if len(text) > 50000:
        return {"error": "Text too long (max 50 000 characters)."}, 400

    references = Reference.query.filter_by(project_id=project.id).all()
    return scan_citation_markers(text, references), 200


def overlap_check(project, data: dict[str, Any]):
    from app.services.overlap_checker_service import check_overlap

    text = (data.get("text") or "").strip()
    if not text:
        return {"error": "text is required"}, 400
    if len(text) > 20000:
        return {"error": "Passage too long (max 20 000 characters). Split into paragraphs."}, 400

    threshold = float(data.get("threshold") or 0.20)
    threshold = max(0.0, min(1.0, threshold))
    persist = bool(data.get("persist", True))

    try:
        result = check_overlap(project, text, score_threshold=threshold, persist=persist)
    except ValueError as exc:
        result = {
            "check_id": None,
            "status": "skipped",
            "similarity_score": 0.0,
            "matches": [],
            "note": str(exc),
        }
    return result, 200
