"""Phase 6 Library Analytics Service — usage scores, coverage maps, and
temporal growth analysis for a project's reference library.
"""

from __future__ import annotations

import logging
from typing import Any

from app.database import db
from app.models.researcher import Reference, ResearcherDocument
from app.services.interest_inference_service import InterestInferenceService

logger = logging.getLogger(__name__)


class LibraryAnalyticsService:
    """Generate analytics for a project's reference library."""

    def get_usage_scores(self, project_id: int) -> list[dict[str, Any]]:
        """Score references by usage: annotations + coded refs + synthesis citations + manuscript citations."""
        from sqlalchemy import func

        # Count annotations per reference
        from app.models.researcher import DocumentAnnotation, CodedReference, Code

        # Get references with their project's documents
        refs = Reference.query.filter_by(project_id=project_id).all()
        doc_ids = [r.document_id for r in refs if r.document_id]

        # Count annotations on linked documents
        annotation_counts = {}
        if doc_ids:
            rows = (
                db.session.query(
                    DocumentAnnotation.document_id, func.count(DocumentAnnotation.id)
                )
                .filter(DocumentAnnotation.document_id.in_(doc_ids))
                .group_by(DocumentAnnotation.document_id)
                .all()
            )
            annotation_counts = {r[0]: r[1] for r in rows}

        results = []
        for ref in refs:
            score = annotation_counts.get(ref.document_id, 0)
            results.append(
                {
                    "reference_id": ref.id,
                    "title": ref.title or "Untitled",
                    "doi": ref.doi,
                    "usage_score": score,
                    "year": ref.publication_year,
                    "source": ref.source,
                }
            )

        results.sort(key=lambda r: -r["usage_score"])
        return results

    def get_coverage_map(self, project_id: int) -> dict[str, Any]:
        """Map references to interest topic clusters."""
        from app.models.researcher import ResearchProject

        project = db.session.get(ResearchProject, project_id)
        if not project:
            return {"error": "Project not found"}

        refs = Reference.query.filter_by(project_id=project_id).all()
        topics = {}

        for ref in refs:
            # Use title + abstract as corpus
            text = (ref.title or "") + " " + (ref.abstract or "")
            if not text.strip():
                continue

            # Simple keyword-based topic assignment
            topic = self._infer_topic(text)
            topics[topic] = topics.get(topic, 0) + 1

        return {
            "total_references": len(refs),
            "topics": [
                {"topic": k, "count": v}
                for k, v in sorted(topics.items(), key=lambda x: -x[1])
            ],
        }

    def get_temporal_growth(self, project_id: int) -> dict[str, Any]:
        """Chart references added per month."""
        refs = Reference.query.filter_by(project_id=project_id).all()
        monthly = {}

        for ref in refs:
            year = ref.publication_year
            if not year:
                continue
            year = str(year)
            monthly[year] = monthly.get(year, 0) + 1

        return {
            "total_references": len(refs),
            "by_year": [{"year": k, "count": v} for k, v in sorted(monthly.items())],
        }

    def get_most_cited(self, project_id: int, *, limit: int = 10) -> list[dict]:
        """Return most-cited references by synthesis evidence."""
        from app.models.researcher import SynthesisReport

        reports = SynthesisReport.query.filter_by(project_id=project_id).all()
        doi_counts = {}

        for report in reports:
            for ev in report.evidence_json or []:
                doi = ev.get("doi", "")
                if doi:
                    doi_counts[doi] = doi_counts.get(doi, 0) + 1

        # Match DOIs to references
        refs = {
            r.doi: r
            for r in Reference.query.filter_by(project_id=project_id).all()
            if r.doi
        }

        results = []
        for doi, count in sorted(doi_counts.items(), key=lambda x: -x[1])[:limit]:
            ref = refs.get(doi)
            results.append(
                {
                    "reference_id": ref.id if ref else None,
                    "title": ref.title if ref else doi,
                    "doi": doi,
                    "citation_count": count,
                }
            )

        return results

    def export_csv(self, project_id: int) -> str:
        """Export library analytics as CSV."""
        import csv
        import io

        scores = self.get_usage_scores(project_id)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["reference_id", "title", "doi", "usage_score", "year", "source"]
        )
        for s in scores:
            writer.writerow(
                [
                    s["reference_id"],
                    s["title"],
                    s["doi"] or "",
                    s["usage_score"],
                    s["year"] or "",
                    s["source"] or "",
                ]
            )

        return output.getvalue()

    @staticmethod
    def _infer_topic(text: str) -> str:
        """Simple keyword-based topic inference."""
        text = text.lower()
        topics = {
            "Machine Learning": [
                "machine learning",
                "neural network",
                "deep learning",
                "transformer",
            ],
            "Healthcare": ["patient", "clinical", "treatment", "diagnosis", "disease"],
            "Climate": ["climate", "temperature", "carbon", "emission", "warming"],
            "Education": [
                "student",
                "learning",
                "curriculum",
                "pedagogy",
                "assessment",
            ],
            "Economics": ["economic", "market", "financial", "investment", "gdp"],
        }

        for topic, keywords in topics.items():
            for kw in keywords:
                if kw in text:
                    return topic

        return "General"
