"""Tests for Phase 6 Deduplication Service."""

from app.services.deduplication_service import DeduplicationService


def test_normalize_doi():
    svc = DeduplicationService()
    assert svc._normalize_doi("10.1000/TEST") == "10.1000/test"
    assert svc._normalize_doi("https://doi.org/10.1000/X") == "10.1000/x"
    assert svc._normalize_doi("") is None


def test_normalize_title():
    svc = DeduplicationService()
    assert (
        svc._normalize_title("The  Effects, of  Something!")
        == "the effects of something"
    )


def test_find_duplicates_exact_doi(app_context, test_project):
    from app.models.researcher import Reference
    from app.database import db

    r1 = Reference(
        project_id=test_project.id, title="A", doi="10.1000/same", citation_key="A2024"
    )
    r2 = Reference(
        project_id=test_project.id, title="B", doi="10.1000/same", citation_key="B2024"
    )
    db.session.add_all([r1, r2])
    db.session.commit()

    svc = DeduplicationService()
    pairs = svc.find_duplicates(test_project.id)
    assert len(pairs) >= 1
    assert pairs[0][2] == "doi_exact"


def test_merge_references(app_context, test_project, test_user):
    from app.models.researcher import Reference
    from app.database import db

    kept = Reference(
        project_id=test_project.id,
        title="Kept",
        doi="10.1000/a",
        citation_key="Kept2024",
    )
    removed = Reference(
        project_id=test_project.id,
        title="Removed",
        abstract="Has abstract",
        citation_key="Removed2024",
    )
    db.session.add_all([kept, removed])
    db.session.commit()

    svc = DeduplicationService()
    ok, msg = svc.merge(kept.id, removed.id, merged_by=test_user.id)
    assert ok
    assert "merged" in msg.lower()

    # Verify removed is gone
    assert db.session.get(Reference, removed.id) is None


def test_revert_merge(app_context, test_project, test_user):
    from app.models.researcher import Reference
    from app.services.deduplication_service import DuplicateMergeLog
    from app.database import db

    kept = Reference(
        project_id=test_project.id,
        title="Kept",
        doi="10.1000/r",
        citation_key="Kept2024",
    )
    removed = Reference(
        project_id=test_project.id,
        title="R",
        abstract="Data",
        year=2023,
        citation_key="R2023",
    )
    db.session.add_all([kept, removed])
    db.session.commit()

    # Create merge log directly
    log = DuplicateMergeLog(
        kept_id=kept.id,
        removed_id=removed.id,
        merged_by=test_user.id,
        revert_payload={
            "title": "R",
            "doi": "10.1000/r",
            "abstract": "Data",
            "year": 2023,
            "citation_key": "R2023",
        },
    )
    db.session.add(log)
    db.session.delete(removed)
    db.session.commit()

    svc = DeduplicationService()
    ok, msg = svc.revert(log.id)
    assert ok

    # Verify restored
    restored = Reference.query.filter_by(project_id=test_project.id, title="R").first()
    assert restored is not None
