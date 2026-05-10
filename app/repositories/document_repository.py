"""Researcher document repository — data access for ResearcherDocument."""

from __future__ import annotations

from typing import List, Optional, Tuple

from app.extensions.db import db
from app.models.researcher.researcher_documents import ResearcherDocument


class DocumentRepository:
    """Repository for ResearcherDocument CRUD and project-scoped queries."""

    def get(self, document_id: int) -> Optional[ResearcherDocument]:
        return db.session.get(ResearcherDocument, document_id)

    def get_by_project(
        self, project_id: int, *, limit: int = 100, offset: int = 0
    ) -> List[ResearcherDocument]:
        return (
            db.session.query(ResearcherDocument)
            .filter_by(project_id=project_id)
            .order_by(ResearcherDocument.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_by_project_and_id(
        self, project_id: int, document_id: int
    ) -> Optional[ResearcherDocument]:
        return (
            db.session.query(ResearcherDocument)
            .filter_by(id=document_id, project_id=project_id)
            .first()
        )

    def count_by_project(self, project_id: int) -> int:
        return (
            db.session.query(ResearcherDocument)
            .filter_by(project_id=project_id)
            .count()
        )

    def paginate_by_project(
        self,
        project_id: int,
        *,
        page: int = 1,
        per_page: int = 20,
        search: str = None,
    ) -> Tuple[List[ResearcherDocument], int]:
        query = db.session.query(ResearcherDocument).filter_by(project_id=project_id)
        if search:
            query = query.filter(
                db.or_(
                    ResearcherDocument.filename.ilike(f"%{search}%"),
                    ResearcherDocument.text_content.ilike(f"%{search}%"),
                )
            )
        total = query.count()
        items = (
            query.order_by(ResearcherDocument.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return items, total

    def add(self, document: ResearcherDocument) -> ResearcherDocument:
        db.session.add(document)
        db.session.flush()
        return document

    def add_all(self, documents: List[ResearcherDocument]) -> List[ResearcherDocument]:
        db.session.add_all(documents)
        db.session.flush()
        return documents

    def update(self, document: ResearcherDocument, **changes) -> ResearcherDocument:
        for key, value in changes.items():
            setattr(document, key, value)
        db.session.flush()
        return document

    def delete(self, document: ResearcherDocument) -> None:
        db.session.delete(document)
        db.session.flush()

    def delete_by_project(self, project_id: int) -> int:
        count = (
            db.session.query(ResearcherDocument)
            .filter_by(project_id=project_id)
            .count()
        )
        db.session.query(ResearcherDocument).filter_by(project_id=project_id).delete(
            synchronize_session=False
        )
        db.session.flush()
        return count

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()
