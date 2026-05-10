"""Knowledge graph cache repository — data access for KnowledgeGraphCache."""

from __future__ import annotations

from typing import Optional

from app.extensions.db import db
from app.services.knowledge_graph_service import KnowledgeGraphCache


class KnowledgeGraphCacheRepository:
    """Repository for KnowledgeGraphCache CRUD."""

    def get_ready(
        self, user_id: int, project_id: Optional[int] = None
    ) -> Optional[KnowledgeGraphCache]:
        query = db.session.query(KnowledgeGraphCache).filter_by(
            user_id=user_id, status="ready"
        )
        if project_id is not None:
            query = query.filter_by(project_id=project_id)
        return query.first()

    def add(self, cache: KnowledgeGraphCache) -> KnowledgeGraphCache:
        db.session.add(cache)
        db.session.flush()
        return cache

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()
