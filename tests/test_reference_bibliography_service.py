from app.database import db
from app.models.researcher.researcher_references import Reference, ReferenceSourceType
from app.services.reference_bibliography_service import (
    build_project_bibliography_preview,
    export_project_bibliography,
)


def _create_reference(
    project,
    *,
    title: str,
    citation_key: str,
    authors: list[str] | None = None,
    year: int | None = None,
    tags: list[str] | None = None,
    citation_count: int = 0,
):
    reference = Reference(
        project_id=project.id,
        title=title,
        citation_key=citation_key,
        source="Journal of Testing",
        source_type=ReferenceSourceType.JOURNAL.value,
        year=year,
        citation_count=citation_count,
    )
    if authors:
        reference.set_authors(authors)
    if tags:
        reference.set_metadata_dict({"tags": tags})
    db.session.add(reference)
    db.session.commit()
    return reference


def test_build_project_bibliography_preview_returns_filtered_list_entries(app_context, test_project):
    _create_reference(
        test_project,
        title="AI Methods for Review",
        citation_key="AiMethods2026",
        authors=["Smith, A."],
        year=2026,
        tags=["methods"],
    )
    _create_reference(
        test_project,
        title="Field Journal Notes",
        citation_key="FieldNotes2026",
        authors=["Jones, B."],
        year=2026,
        tags=["field"],
    )

    preview = build_project_bibliography_preview(
        test_project,
        style="apa",
        tag="methods",
        query="AI",
    )

    assert preview["style"] == "apa"
    assert preview["preview_mode"] == "list"
    assert preview["total_count"] == 1
    assert preview["preview_count"] == 1
    assert preview["truncated"] is False
    assert len(preview["entries"]) == 1
    assert "AI Methods for Review" in preview["entries"][0]
    assert "AiMethods2026" not in preview["preview_content"]


def test_build_project_bibliography_preview_returns_raw_bibtex_preview(app_context, test_project):
    _create_reference(
        test_project,
        title="Deep Systems",
        citation_key="DeepSystems2026",
        authors=["Taylor, C."],
        year=2026,
    )

    preview = build_project_bibliography_preview(test_project, style="bibtex")

    assert preview["style"] == "bibtex"
    assert preview["preview_mode"] == "raw"
    assert preview["total_count"] == 1
    assert preview["entries"] == []
    assert "@journal{DeepSystems2026" in preview["preview_content"]
    assert preview["filename"].endswith(".bib")


def test_export_project_bibliography_honors_filtered_view(app_context, test_project):
    _create_reference(
        test_project,
        title="Linked Source",
        citation_key="Linked2026",
        authors=["Lopez, D."],
        year=2026,
        citation_count=2,
    )
    _create_reference(
        test_project,
        title="Unlinked Source",
        citation_key="Unlinked2026",
        authors=["Ng, E."],
        year=2026,
        citation_count=0,
    )

    content, mimetype, filename = export_project_bibliography(
        test_project,
        style="json",
        collection="linked",
    )

    assert mimetype == "application/json"
    assert filename.endswith(".json")
    assert "Linked2026" in content
    assert "Unlinked2026" not in content
