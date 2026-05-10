"""Reference repository — data access for Reference model."""

from __future__ import annotations

from typing import List, Optional, Set, Tuple

from app.extensions.db import db
from app.models.researcher.researcher_references import Reference
from app.models.researcher.researcher_projects import ResearchProject


class ReferenceRepository:
    """Repository for Reference CRUD and project-scoped queries."""

    def get(self, ref_id: int) -> Optional[Reference]:
        return db.session.get(Reference, ref_id)

    def get_by_project(self, project_id: int) -> List[Reference]:
        return (
            db.session.query(Reference)
            .filter_by(project_id=project_id)
            .order_by(Reference.created_at.desc())
            .all()
        )

    def get_by_project_and_id(
        self, project_id: int, ref_id: int
    ) -> Optional[Reference]:
        return (
            db.session.query(Reference)
            .filter_by(id=ref_id, project_id=project_id)
            .first()
        )

    def paginate_by_project(
        self,
        project_id: int,
        *,
        page: int = 1,
        per_page: int = 20,
        search: str = None,
    ) -> Tuple[List[Reference], int]:
        query = db.session.query(Reference).filter_by(project_id=project_id)
        if search:
            query = query.filter(
                db.or_(
                    Reference.title.ilike(f"%{search}%"),
                    Reference.doi.ilike(f"%{search}%"),
                )
            )
        total = query.count()
        items = (
            query.order_by(Reference.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return items, total

    def count_by_project(self, project_id: int) -> int:
        return db.session.query(Reference).filter_by(project_id=project_id).count()

    def get_by_doi(self, project_id: int, doi: str) -> Optional[Reference]:
        return (
            db.session.query(Reference)
            .filter_by(project_id=project_id, doi=doi)
            .first()
        )

    def get_all_dois_for_project(self, project_id: int) -> Set[str]:
        rows = (
            db.session.query(Reference.doi)
            .filter_by(project_id=project_id)
            .filter(Reference.doi.isnot(None))
            .all()
        )
        return {row[0] for row in rows if row[0]}

    def get_titles_for_project(self, project_id: int) -> Set[str]:
        rows = (
            db.session.query(Reference.title)
            .filter_by(project_id=project_id)
            .filter(Reference.title.isnot(None))
            .all()
        )
        return {row[0] for row in rows if row[0]}

    def get_by_user_projects(self, user_id: int) -> List[Reference]:
        """Get all references from projects owned by the user."""
        return (
            db.session.query(Reference)
            .join(ResearchProject, Reference.project_id == ResearchProject.id)
            .filter(ResearchProject.owner_id == user_id)
            .all()
        )

    def add(self, reference: Reference) -> Reference:
        db.session.add(reference)
        db.session.flush()
        return reference

    def add_all(self, references: List[Reference]) -> List[Reference]:
        db.session.add_all(references)
        db.session.flush()
        return references

    def update(self, reference: Reference, **changes) -> Reference:
        for key, value in changes.items():
            setattr(reference, key, value)
        db.session.flush()
        return reference

    def delete(self, reference: Reference) -> None:
        db.session.delete(reference)
        db.session.flush()

    def delete_by_project(self, project_id: int) -> int:
        count = db.session.query(Reference).filter_by(project_id=project_id).count()
        db.session.query(Reference).filter_by(project_id=project_id).delete(
            synchronize_session=False
        )
        db.session.flush()
        return count

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()

    def flush(self) -> None:
        db.session.flush()
