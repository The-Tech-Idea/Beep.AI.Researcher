"""Tests for Phase 6 Smart Import Service."""

from unittest.mock import MagicMock

from app.services.smart_import_service import SmartImportService


def test_detect_doi():
    svc = SmartImportService()
    t, v = svc.detect_identifier("10.1038/s41586-021-03873-x")
    assert t == "doi"
    assert v == "10.1038/s41586-021-03873-x"


def test_detect_pmid():
    svc = SmartImportService()
    t, v = svc.detect_identifier("34567890")
    assert t == "pmid"


def test_detect_arxiv():
    svc = SmartImportService()
    t, v = svc.detect_identifier("2101.00001v1")
    assert t == "arxiv"


def test_detect_url_with_doi():
    svc = SmartImportService()
    t, v = svc.detect_identifier("https://doi.org/10.1000/test")
    # DOI extracted from URL
    assert t == "doi"
    assert v == "10.1000/test"


def test_detect_unknown():
    svc = SmartImportService()
    t, v = svc.detect_identifier("some random text")
    assert t is None


def test_check_duplicate_by_doi(app_context, test_project):
    from app.models.researcher import Reference

    ref = Reference(
        project_id=test_project.id,
        title="Test Paper",
        doi="10.1000/dup",
        citation_key="TestPaper2024",
    )
    from app.database import db

    db.session.add(ref)
    db.session.commit()

    svc = SmartImportService()
    metadata = {"doi": "10.1000/dup", "title": "Test Paper"}
    dup = svc.check_duplicate(test_project.id, metadata)
    assert dup is not None
    assert dup.id == ref.id


def test_check_duplicate_by_title(app_context, test_project):
    from app.models.researcher import Reference

    ref = Reference(
        project_id=test_project.id,
        title="The Effects of Something Important on Other Things",
        citation_key="Effects2024",
    )
    from app.database import db

    db.session.add(ref)
    db.session.commit()

    svc = SmartImportService()
    metadata = {"title": "The effects of something important on other things"}
    dup = svc.check_duplicate(test_project.id, metadata)
    assert dup is not None
    assert dup.id == ref.id
