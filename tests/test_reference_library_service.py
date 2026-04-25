"""Tests for project-scoped citation library filters and tag helpers."""
from datetime import timedelta

from app.core.time_utils import utcnow_naive
from app.models.researcher.researcher_references import Reference
from app.services.citation_library_service import (
    build_project_citation_library,
    get_reference_tags,
    normalize_reference_tags,
    set_reference_tags,
)


class TestCitationLibraryTagHelpers:
    def test_normalize_reference_tags_deduplicates_and_preserves_order(self):
        assert normalize_reference_tags("methods; AI, methods ; literature review") == [
            "methods",
            "AI",
            "literature review",
        ]

    def test_set_reference_tags_preserves_other_metadata(self, app_context, test_project):
        from app.database import db

        reference = Reference(
            project_id=test_project.id,
            title="Tagged Reference",
            citation_key="TaggedReference",
        )
        reference.set_metadata_dict({"rating": 5})
        set_reference_tags(reference, "methods; review")
        db.session.add(reference)
        db.session.commit()

        assert get_reference_tags(reference) == ["methods", "review"]
        assert reference.get_metadata_dict()["rating"] == 5


class TestProjectCitationLibraryView:
    def test_build_project_citation_library_filters_collections_and_tags(self, app_context, test_project):
        from app.database import db
        from app.models.researcher import ResearchProject

        project = db.session.get(ResearchProject, test_project.id)

        recent_reference = Reference(
            project_id=project.id,
            title="AI Methods Review",
            citation_key="AiMethodsReview",
            doi="10.1000/example",
            notes="Important note",
            citation_count=1,
        )
        set_reference_tags(recent_reference, ["methods", "ai"])

        older_reference = Reference(
            project_id=project.id,
            title="Theory Notes",
            citation_key="TheoryNotes",
            notes="Older note",
        )
        set_reference_tags(older_reference, "theory")
        older_reference.created_at = utcnow_naive() - timedelta(days=45)

        no_doi_reference = Reference(
            project_id=project.id,
            title="Literature Survey",
            citation_key="LiteratureSurvey",
        )
        set_reference_tags(no_doi_reference, "review")

        db.session.add_all([recent_reference, older_reference, no_doi_reference])
        db.session.commit()

        overview = build_project_citation_library(project)
        counts = {entry["key"]: entry["count"] for entry in overview["collections"]}
        tags = {entry["name"]: entry["count"] for entry in overview["tags"]}

        assert overview["result_count"] == 3
        assert counts["all"] == 3
        assert counts["recent"] == 2
        assert counts["linked"] == 1
        assert counts["notes"] == 2
        assert counts["needs_doi"] == 2
        assert tags["methods"] == 1
        assert tags["ai"] == 1
        assert tags["theory"] == 1
        assert tags["review"] == 1

        linked_only = build_project_citation_library(project, collection="linked")
        assert [reference.citation_key for reference in linked_only["references"]] == ["AiMethodsReview"]

        tagged = build_project_citation_library(project, collection="all", tag="review")
        assert [reference.citation_key for reference in tagged["references"]] == ["LiteratureSurvey"]

        searched = build_project_citation_library(project, query="Methods")
        assert [reference.citation_key for reference in searched["references"]] == ["AiMethodsReview"]
