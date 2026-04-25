"""Video (and long-text) summary service (Phase 03).

Produces structured research notes from a transcript or long text via
chunked summarization through the Beep.AI.Server chat/completions route.

Public API
----------
``summarize_video_document(project, document, user_id)``
    Summarizes a ``ResearcherDocument`` that has ``text_content`` set.
    Returns the summary text and saves it as a new linked document.
``summarize_text(text, project, user_id, title)``
    Lower-level helper that summarizes arbitrary text.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.time_utils import utcnow_naive
from app.database import db
from app.models.researcher import ResearchProject, ResearcherDocument
from app.services.beep_ai_client import chat_reply, is_configured

logger = logging.getLogger(__name__)

# --- chunking ---
_CHUNK_SIZE = 3000   # characters per chunk sent to the LLM
_CHUNK_OVERLAP = 200  # overlap between consecutive chunks

_STRUCTURED_NOTE_PROMPT = """\
You are a research assistant.  Summarise the following transcript excerpt into
concise research notes with these sections:
- **Main thesis / topic**
- **Key points** (bullet list, max 6)
- **Methodology or approach** (if mentioned)
- **Limitations or caveats** (if mentioned)
- **Notable quotes** (with approximate location, e.g. "~2 min")

Be terse and scholarly.  Do not invent information not present in the text.

Transcript excerpt:
{chunk}
"""

_MERGE_PROMPT = """\
You are a research assistant.  The following are partial summaries of sections
of a longer transcript.  Merge them into a single coherent set of research notes:
- **Main thesis / topic**
- **Key points** (bullet list)
- **Methodology or approach**
- **Limitations or caveats**
- **Notable quotes**

Partial summaries:
{summaries}
"""


def _chunk_text(text: str, chunk_size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping character chunks."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
        if start >= len(text):
            break
    return chunks


def summarize_text(
    text: str,
    project: ResearchProject,
    *,
    user_id: int,
    title: str = "",
) -> dict:
    """Summarise ``text`` using the project chat backend.

    Returns ``{"ok": bool, "summary": str|None, "error": str|None}``.
    Degrades gracefully when Beep.AI.Server is not configured.
    """
    if not text or not text.strip():
        return {"ok": False, "summary": None, "error": "No text to summarise."}

    if not is_configured():
        return {
            "ok": False,
            "summary": None,
            "error": "Beep.AI.Server is not configured; summarisation unavailable.",
        }

    chunks = _chunk_text(text)

    # If small enough, summarise in one shot
    if len(chunks) == 1:
        messages = [
            {
                "role": "user",
                "content": _STRUCTURED_NOTE_PROMPT.format(chunk=chunks[0]),
            }
        ]
        ok, response = chat_reply(messages, user_id=user_id)
        if not ok:
            return {"ok": False, "summary": None, "error": str(response)}
        return {"ok": True, "summary": str(response), "error": None}

    # Multi-chunk: summarise each chunk, then merge
    partial_summaries: list[str] = []
    for i, chunk in enumerate(chunks):
        messages = [
            {
                "role": "user",
                "content": _STRUCTURED_NOTE_PROMPT.format(chunk=chunk),
            }
        ]
        ok, response = chat_reply(messages, user_id=user_id)
        if ok and response:
            partial_summaries.append(f"--- Part {i + 1} ---\n{response}")
        else:
            logger.warning("Chunk %d summarisation failed: %s", i + 1, response)

    if not partial_summaries:
        return {"ok": False, "summary": None, "error": "All chunk summarisations failed."}

    if len(partial_summaries) == 1:
        return {"ok": True, "summary": partial_summaries[0], "error": None}

    # Merge partial summaries
    merge_messages = [
        {
            "role": "user",
            "content": _MERGE_PROMPT.format(summaries="\n\n".join(partial_summaries)),
        }
    ]
    ok, merged = chat_reply(merge_messages, user_id=user_id)
    if not ok:
        # Fall back to concatenation
        merged = "\n\n".join(partial_summaries)
    return {"ok": True, "summary": str(merged), "error": None}


def summarize_video_document(
    project: ResearchProject,
    document: ResearcherDocument,
    *,
    user_id: int,
) -> dict:
    """Summarise a video-sourced document and persist the summary as a linked note.

    Returns ``{"ok": bool, "summary": str|None, "note_document_id": int|None,
               "error": str|None}``.
    """
    if not document.text_content:
        return {
            "ok": False,
            "summary": None,
            "note_document_id": None,
            "error": "Document has no transcript text to summarise.",
        }

    result = summarize_text(
        document.text_content,
        project,
        user_id=user_id,
        title=document.filename or "",
    )

    if not result["ok"] or not result["summary"]:
        result["note_document_id"] = None
        return result

    summary_text: str = result["summary"]

    # Persist summary as a linked ResearcherDocument note
    note_filename = f"summary_{document.id}_{document.filename or 'transcript'}.md"
    note = ResearcherDocument(
        project_id=project.id,
        filename=note_filename,
        source_type="note",
        source_id=str(document.id),
        source_url=document.source_url,
        text_content=summary_text,
    )
    db.session.add(note)
    db.session.commit()

    return {
        "ok": True,
        "summary": summary_text,
        "note_document_id": note.id,
        "error": None,
    }
