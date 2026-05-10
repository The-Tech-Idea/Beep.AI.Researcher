"""Auto-extraction cache repository — data access for AutoExtractionCache."""

from __future__ import annotations

from typing import Optional

from app.extensions.db import db
from app.services.auto_extraction_service import AutoExtractionCache


class AutoExtractionCacheRepository:
    """Repository for AutoExtractionCache CRUD."""

    def get_by_document(self, document_id: int) -> Optional[AutoExtractionCache]:
        return (
            db.session.query(AutoExtractionCache)
            .filter_by(document_id=document_id)
            .first()
        )

    def add(self, cache: AutoExtractionCache) -> AutoExtractionCache:
        db.session.add(cache)
        db.session.flush()
        return cache

    def delete(self, cache: AutoExtractionCache) -> None:
        db.session.delete(cache)
        db.session.flush()

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()
