"""Phase 2 Evidence Synthesis Service — answers a research question using
project-grounded RAG evidence with LLM synthesis and polarity classification.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.database import db
from app.models.researcher import (
    EvidenceItem,
    ResearchProject,
    ResearcherDocument,
    SynthesisReport,
)
from app.services import beep_ai_client
from app.services.polarity_classifier import PolarityClassifier

logger = logging.getLogger(__name__)

_SYNTHESIS_PROMPT = (
    "You are an evidence synthesis assistant. Answer the research question below "
    "using ONLY the evidence snippets provided. Every claim you make MUST be "
    "supported by at least one evidence snippet with an inline citation.\n\n"
    "Rules:\n"
    "- Use inline citations like [1], [2] referencing the snippet numbers\n"
    "- If the evidence is inconclusive, state that clearly\n"
    "- If the evidence contradicts itself, present both sides\n"
    "- Do NOT invent facts not present in the evidence\n"
    "- Keep the answer to 3-5 well-structured paragraphs\n"
    "- Return ONLY the answer text, no preamble or meta-commentary"
)

_REPORT_SYSTEM_PROMPT = (
    "You are a structured data extractor. Given the evidence snippets and "
    "the synthesized answer, produce a summary JSON.\n\n"
    "Return ONLY valid JSON:\n"
    "{\n"
    '  "confidence": "supporting" | "contradicting" | "mixed",\n'
    '  "key_themes": ["theme 1", "theme 2"],\n'
    '  "gaps": ["areas with insufficient evidence"]\n'
    "}"
)


class EvidenceSynthesisService:
    """Synthesize an answer to a research question using project evidence."""

    def __init__(self, ai_client=None, polarity_classifier=None, report_repo=None):
        self.ai_client = ai_client or beep_ai_client
        self.classifier = polarity_classifier or PolarityClassifier(ai_client)
        self._report_repo = report_repo

    @property
    def _repo(self):
        if self._report_repo is None:
            from app.repositories.synthesis_report_repository import (
                SynthesisReportRepository,
            )

            self._report_repo = SynthesisReportRepository()
        return self._report_repo

    def synthesise(
        self,
        project: ResearchProject,
        question: str,
        *,
        max_evidence: int = 10,
        quality_mode: str = "balanced",
        persist: bool = True,
    ) -> tuple[dict[str, Any], int]:
        """Run the full synthesis pipeline.

        1. Query project RAG for relevant evidence
        2. Classify polarity of each snippet
        3. Synthesize grounded answer
        4. Persist as SynthesisReport
        """
        if not question or not question.strip():
            return {"error": "Research question is required"}, 400

        if not self.ai_client.is_configured():
            return {"error": "AI server not configured for synthesis"}, 503

        # Step 1: Retrieve evidence via RAG
        snippets = self._retrieve_evidence(
            project, question, max_evidence, quality_mode
        )
        if not snippets:
            return {
                "error": "No relevant evidence found for this question in the project library.",
                "question": question,
                "answer": None,
                "evidence_count": 0,
            }, 200

        # Step 2: Classify polarity
        raw_snippets = [s["text"] for s in snippets]
        classifications = self.classifier.classify_batch(question, raw_snippets)

        # Enrich snippets with polarity
        for c in classifications:
            idx = c.get("snippet_index", 0)
            if 0 <= idx < len(snippets):
                snippets[idx]["polarity"] = c["polarity"]
                snippets[idx]["confidence"] = c["confidence"]
                snippets[idx]["reason"] = c["reason"]

        # Count polarities
        polarity_counts = {"supporting": 0, "contradicting": 0, "mentioning": 0}
        for s in snippets:
            p = s.get("polarity", "mentioning")
            polarity_counts[p] = polarity_counts.get(p, 0) + 1

        # Step 3: Synthesize answer
        answer = self._generate_answer(question, snippets)

        # Determine confidence
        if polarity_counts["supporting"] > polarity_counts["contradicting"] * 2:
            confidence = "supporting"
        elif polarity_counts["contradicting"] > polarity_counts["supporting"] * 2:
            confidence = "contradicting"
        else:
            confidence = "mixed"

        # Step 4: Persist
        report = None
        if persist:
            report = self._persist_report(
                project, question, answer, snippets, confidence, polarity_counts
            )

        return {
            "report_id": report.id if report else None,
            "question": question,
            "answer": answer,
            "evidence": [
                {
                    "snippet": s["text"][:1000],
                    "polarity": s.get("polarity", "mentioning"),
                    "source_doc_id": s.get("document_id"),
                    "doi": s.get("doi", ""),
                    "score": s.get("score", 0),
                }
                for s in snippets
            ],
            "confidence": confidence,
            "supporting_count": polarity_counts["supporting"],
            "contradicting_count": polarity_counts["contradicting"],
            "mentioning_count": polarity_counts["mentioning"],
            "evidence_count": len(snippets),
        }, 200

    def _retrieve_evidence(
        self,
        project: ResearchProject,
        question: str,
        max_results: int,
        quality_mode: str,
    ) -> list[dict]:
        """Retrieve evidence snippets from project RAG collection."""
        if not project.collection_id:
            return self._fallback_evidence(project, question, max_results)

        ok, result = self.ai_client.query_project_rag(
            project,
            question,
            max_results=max_results,
            user_id=project.owner_id,
            quality_mode=quality_mode,
            hybrid_search=True,
            rerank=True,
            return_citations=True,
            return_full=True,
        )

        if not ok or not result:
            logger.warning("EvidenceSynthesisService: RAG query failed: %s", result)
            return self._fallback_evidence(project, question, max_results)

        # Extract snippets from RAG result (handles multiple response formats)
        if isinstance(result, dict):
            sources = (
                result.get("sources")
                or result.get("results")
                or result.get("documents")
                or []
            )
        elif isinstance(result, list):
            sources = result
        else:
            sources = []

        snippets = []
        for source in sources[:max_results]:
            if isinstance(source, dict):
                snippets.append(
                    {
                        "text": source.get("content", source.get("text", "")),
                        "document_id": source.get("document_id")
                        or source.get("source_id"),
                        "doi": source.get("doi", ""),
                        "score": source.get("score", source.get("relevance", 0)),
                        "polarity": "mentioning",
                        "confidence": 0.0,
                        "reason": "",
                    }
                )

        return snippets or self._fallback_evidence(project, question, max_results)

    @staticmethod
    def _fallback_evidence(project, question, max_results):
        """Use existing EvidenceItems as fallback."""
        items = (
            EvidenceItem.query.filter_by(project_id=project.id)
            .order_by(EvidenceItem.created_at.desc())
            .limit(max_results)
            .all()
        )

        return [
            {
                "text": item.claim_text
                + (": " + item.verbatim_quote if item.verbatim_quote else ""),
                "document_id": item.document_id,
                "doi": "",
                "score": item.confidence_score or 0.5,
                "polarity": "mentioning",
                "confidence": 0.0,
                "reason": "",
            }
            for item in items
        ]

    def _generate_answer(self, question: str, snippets: list[dict]) -> str:
        """Generate a grounded synthesis answer."""
        evidence_text = "\n\n".join(
            f"[{i + 1}] {s['text'][:500]}" for i, s in enumerate(snippets)
        )

        messages = [
            {"role": "system", "content": _SYNTHESIS_PROMPT},
            {
                "role": "user",
                "content": f"Question: {question}\n\nEvidence:\n{evidence_text}",
            },
        ]

        ok, answer = self.ai_client.chat_reply(messages, temperature=0.3)
        if not ok:
            return "(Synthesis failed — could not reach the model.)"

        # Strip markdown fences
        answer = answer.strip()
        if answer.startswith("```"):
            lines = answer.split("\n")
            answer = "\n".join(
                l for l in lines if not l.strip().startswith("```")
            ).strip()

        return answer

    def _persist_report(
        self,
        project,
        question: str,
        answer: str,
        snippets: list[dict],
        confidence: str,
        polarity_counts: dict,
    ) -> SynthesisReport:
        """Save the synthesis report to the database."""
        report = SynthesisReport(
            project_id=project.id,
            question=question,
            answer_text=answer,
            evidence_json=[
                {
                    "snippet": s["text"][:1000],
                    "polarity": s.get("polarity", "mentioning"),
                    "document_id": s.get("document_id"),
                    "doi": s.get("doi", ""),
                    "score": s.get("score", 0),
                }
                for s in snippets
            ],
            confidence=confidence,
            supporting_count=polarity_counts["supporting"],
            contradicting_count=polarity_counts["contradicting"],
            mentioning_count=polarity_counts["mentioning"],
            status="complete",
        )
        return self._repo.add(report)
