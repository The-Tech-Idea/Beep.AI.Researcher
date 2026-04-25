import json

from app.database import db
from app.models.researcher.researcher_references import Reference, ReferenceSourceType
from app.services.reference_import_service import import_references


def _create_reference(project, *, title: str, citation_key: str, year: int | None = None, doi: str | None = None):
    reference = Reference(
        project_id=project.id,
        title=title,
        citation_key=citation_key,
        source_type=ReferenceSourceType.JOURNAL.value,
        source="Journal of Testing",
        year=year,
        doi=doi,
    )
    db.session.add(reference)
    db.session.commit()
    return reference


def test_import_references_reports_duplicate_reason_counts(app_context, test_project):
    _create_reference(
        test_project,
        title="Existing Methods Paper",
        citation_key="ExistingMethods2026",
        year=2026,
        doi="10.1000/existing-methods",
    )

    payload = json.dumps(
        [
            {
                "title": "Existing Methods Paper",
                "citation_key": "ExistingMethods2026",
                "year": 2026,
            },
            {
                "title": "Different Title Same DOI",
                "citation_key": "DifferentKey2026",
                "doi": "https://doi.org/10.1000/existing-methods",
                "year": 2026,
            },
            {
                "title": "Existing Methods Paper",
                "citation_key": "FreshKey2026",
                "year": 2026,
            },
        ]
    )

    result = import_references(test_project, payload, "json")

    assert result["created"] == 0
    assert result["skipped"] == 3
    assert result["duplicate_skipped"] == 3
    assert result["invalid_skipped"] == 0
    assert result["duplicate_reasons"]["citation_key"] == 1
    assert result["duplicate_reasons"]["doi"] == 1
    assert result["duplicate_reasons"]["title_year"] == 1


def test_import_references_creates_new_rows_and_skips_invalid_entries(app_context, test_project):
    payload = json.dumps(
        [
            {
                "title": "Imported Methods Review",
                "citation_key": "ImportedMethods2026",
                "authors": ["Doe, A."],
                "year": 2026,
            },
            {
                "citation_key": "MissingTitle2026",
                "year": 2026,
            },
        ]
    )

    result = import_references(test_project, payload, "json")

    assert result["created"] == 1
    assert result["skipped"] == 1
    assert result["duplicate_skipped"] == 0
    assert result["invalid_skipped"] == 1
    assert len(result["reference_ids"]) == 1

    created = Reference.query.filter_by(project_id=test_project.id, citation_key="ImportedMethods2026").first()
    assert created is not None
    assert created.title == "Imported Methods Review"
