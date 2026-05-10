"""Phase 2 Literature Review Draft Service — clusters evidence by theme
and generates a grounded literature review draft.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.database import db
from app.models.researcher import ResearchBrief, ResearchProject
from app.services import beep_ai_client

logger = logging.getLogger(__name__)

_CLUSTER_PROMPT = (
    "You are a research organizer. Given a set of evidence snippets about a topic, "
    "group them into thematic clusters. Return ONLY valid JSON:\n"
    '{"themes": [{"theme": "Theme name", "snippet_indices": [0, 2, 5], '
    '"description": "Brief description of this theme"}, ...]}'
)

_DRAFT_PROMPT = (
    "You are an academic writer writing a literature review section. "
    "For each theme below, write one well-structured paragraph synthesizing "
    "the evidence. Use inline citations [1], [2] referencing snippet numbers.\n\n"
    "Rules:\n"
    "- Every claim must be cited\n"
    "- Identify gaps where evidence is lacking\n"
    "- Write in formal academic prose\n"
    "- Return ONLY the review text, no meta-commentary"
)


class LiteratureReviewDraftService:
    """Generate a literature review draft by clustering evidence thematically."""

    def __init__(self, ai_client=None):
        self.ai_client = ai_client or beep_ai_client

    def generate_draft(
        self,
        project: ResearchProject,
        evidence_snippets: list[dict[str, Any]],
        *,
        max_themes: int = 5,
        persist: bool = True,
    ) -> tuple[dict, int]:
        """Generate a literature review draft from evidence snippets.

        Each snippet: {text, document_id, doi, ...}
        """
        if not evidence_snippets:
            return {"error": "No evidence snippets provided"}, 400

        if not self.ai_client.is_configured():
            return {"error": "AI server not configured"}, 503

        # Step 1: Cluster by theme
        themes = self._cluster_themes(evidence_snippets, max_themes)
        if not themes:
            return {"error": "Could not identify themes in the evidence"}, 422

        # Step 2: Generate draft paragraphs
        draft = self._generate_review(themes, evidence_snippets)

        # Step 3: Identify gaps
        gaps = [t["description"] for t in themes if len(t["snippet_indices"]) < 2]

        # Step 4: Persist
        brief = None
        if persist:
            brief = ResearchBrief(
                project_id=project.id,
                sector="general",
                title="Literature Review Draft",
                summary_text=draft,
                key_findings={
                    "themes": [
                        {"name": t["theme"], "count": len(t["snippet_indices"])}
                        for t in themes
                    ],
                    "gaps": gaps,
                },
                status="draft",
                llm_model_used="llm",
            )
            db.session.add(brief)
            db.session.commit()

        return {
            "brief_id": brief.id if brief else None,
            "draft": draft,
            "themes": themes,
            "gaps": gaps,
            "snippet_count": len(evidence_snippets),
        }, 200

    def _cluster_themes(self, snippets: list[dict], max_themes: int) -> list[dict]:
        """Cluster snippets into themes via LLM."""
        snippet_list = "\n".join(
            f"[{i}] {s['text'][:300]}" for i, s in enumerate(snippets)
        )

        messages = [
            {"role": "system", "content": _CLUSTER_PROMPT},
            {
                "role": "user",
                "content": f"Snippets:\n{snippet_list}\n\nGroup into at most {max_themes} themes.",
            },
        ]

        ok, raw = self.ai_client.chat_reply(messages, temperature=0.3)
        if not ok:
            logger.warning("LiteratureReviewDraftService: clustering failed: %s", raw)
            return self._heuristic_cluster(snippets, max_themes)

        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(l for l in lines if not l.strip().startswith("```"))

        try:
            data = json.loads(cleaned)
            themes = data.get("themes", [])
            return [
                {
                    "theme": t["theme"],
                    "snippet_indices": t.get("snippet_indices", []),
                    "description": t.get("description", ""),
                }
                for t in themes[:max_themes]
            ]
        except (json.JSONDecodeError, KeyError, TypeError):
            return self._heuristic_cluster(snippets, max_themes)

    @staticmethod
    def _heuristic_cluster(snippets: list, max_themes: int) -> list[dict]:
        """Fallback: split into chunks by position."""
        chunk_size = max(1, len(snippets) // max_themes)
        themes = []
        for i in range(0, len(snippets), chunk_size):
            chunk = snippets[i : i + chunk_size]
            themes.append(
                {
                    "theme": f"Theme {len(themes) + 1}",
                    "snippet_indices": list(range(i, i + len(chunk))),
                    "description": f"Group of {len(chunk)} evidence snippets.",
                }
            )
            if len(themes) >= max_themes:
                break
        return themes

    def _generate_review(self, themes: list[dict], snippets: list[dict]) -> str:
        """Generate the literature review text."""
        theme_descriptions = []
        for t in themes:
            snippet_refs = []
            for idx in t["snippet_indices"]:
                if 0 <= idx < len(snippets):
                    snippet_refs.append(f"[{idx + 1}] {snippets[idx]['text'][:300]}")
            if snippet_refs:
                theme_descriptions.append(
                    f"Theme: {t['theme']}\nEvidence:\n" + "\n".join(snippet_refs)
                )

        user_content = "\n\n---\n\n".join(theme_descriptions)

        messages = [
            {"role": "system", "content": _DRAFT_PROMPT},
            {"role": "user", "content": user_content},
        ]

        ok, draft = self.ai_client.chat_reply(messages, temperature=0.5)
        if not ok:
            return "(Literature review draft generation failed.)"

        # Strip markdown
        draft = draft.strip()
        if draft.startswith("```"):
            lines = draft.split("\n")
            draft = "\n".join(
                l for l in lines if not l.strip().startswith("```")
            ).strip()

        return draft
