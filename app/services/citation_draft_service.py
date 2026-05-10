"""Phase 4 Citation Draft Service — themed paragraph draft with citation markers."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services import beep_ai_client
from app.services.citation_formatter_service import format_reference_list

logger = logging.getLogger(__name__)

_CITATION_DRAFT_PROMPT = (
    "You are an academic writing assistant. Write a paragraph on the given theme using "
    "the provided evidence snippets. For each claim, insert a citation marker in the format "
    "[Cite: DOI] or [Cite: title] where DOI/title refers to one of the provided sources.\n\n"
    "Rules:\n"
    "- Every factual claim must have a citation marker\n"
    "- Use natural academic prose — no bullet points\n"
    "- Keep the paragraph cohesive and well-structured\n"
    "- Do NOT invent citations — only use the sources provided\n"
    "- Return the paragraph as plain text with the citation markers inline"
)


class CitationDraftService:
    """Generate a themed paragraph draft with inline citation markers."""

    def __init__(self, ai_client=None):
        self.ai_client = ai_client or beep_ai_client

    def draft(self, theme: str, sources: list[dict[str, Any]]) -> tuple[dict, int]:
        """Generate a draft paragraph using the given sources.

        Each source must have: doi, title, abstract (or excerpt).
        """
        if not theme or not theme.strip():
            return {"error": "A theme or topic is required"}, 400
        if not sources:
            return {"error": "No sources provided for citation drafting"}, 400
        if len(sources) > 20:
            sources = sources[:20]

        source_descriptions = []
        for i, s in enumerate(sources, 1):
            excerpt = (s.get("abstract") or s.get("excerpt") or "")[:500]
            source_descriptions.append(
                f"[{i}] {s.get('title', 'Untitled')}\n"
                f"DOI: {s.get('doi', 'N/A')}\n"
                f"Key content: {excerpt}"
            )

        source_text = "\n\n".join(source_descriptions)
        user_content = f"Theme: {theme}\n\nAvailable sources:\n{source_text}"

        if not self.ai_client.is_configured():
            return {"error": "AI server not configured for citation drafting"}, 503

        messages = [
            {"role": "system", "content": _CITATION_DRAFT_PROMPT},
            {"role": "user", "content": user_content},
        ]

        ok, draft = self.ai_client.chat_reply(messages, temperature=0.7)
        if not ok:
            logger.warning("CitationDraftService: LLM call failed: %s", draft)
            return {"error": "Citation draft generation failed."}, 502

        # Strip markdown fences if present
        draft = draft.strip()
        if draft.startswith("```"):
            lines = draft.split("\n")
            draft = "\n".join(
                l for l in lines if not l.strip().startswith("```")
            ).strip()

        # Extract citation markers
        markers = self._extract_markers(draft, sources)

        # Generate formatted citations for the referenced sources
        cited_sources = [
            s for s in sources if s.get("doi") in markers.get("cited_dois", set())
        ]
        formatted_citations = []
        if cited_sources:
            for s in cited_sources:
                if isinstance(s, dict):
                    formatted_citations.append(
                        {
                            "doi": s.get("doi", ""),
                            "title": s.get("title", ""),
                            "authors": s.get("authors", []),
                            "year": s.get("year", ""),
                        }
                    )
                else:
                    formatted_citations.append(
                        {
                            "doi": getattr(s, "doi", ""),
                            "title": getattr(s, "title", ""),
                            "authors": getattr(s, "authors", []),
                            "year": getattr(s, "year", ""),
                        }
                    )

        return {
            "draft": draft,
            "theme": theme,
            "markers": markers,
            "formatted_citations": formatted_citations,
            "source_count": len(sources),
        }, 200

    @staticmethod
    def _extract_markers(text: str, sources: list[dict]) -> dict:
        """Extract [Cite: ...] markers from the draft text."""
        import re

        cited_dois = set()
        marker_list = []

        for match in re.finditer(r"\[Cite:\s*([^\]]+)\]", text):
            raw = match.group(1).strip()
            citation = {
                "raw": raw,
                "start": match.start(),
                "end": match.end(),
            }

            # Check if it's a DOI match
            for s in sources:
                if s.get("doi") and s["doi"].lower() in raw.lower():
                    citation["matched_doi"] = s["doi"]
                    citation["matched_title"] = s.get("title")
                    cited_dois.add(s["doi"])
                    break
                elif s.get("title") and s["title"].lower() in raw.lower():
                    citation["matched_doi"] = s.get("doi")
                    citation["matched_title"] = s["title"]
                    if s.get("doi"):
                        cited_dois.add(s["doi"])
                    break

            marker_list.append(citation)

        return {
            "markers": marker_list,
            "cited_dois": list(cited_dois),
            "total_markers": len(marker_list),
        }
