"""Reading list repository — data access for ReadingListItem."""

from __future__ import annotations

from typing import List, Optional

from app.extensions.db import db
from app.models.researcher.phase_1_models import ReadingListItem


class ReadingListRepository:
    """Repository for ReadingListItem CRUD and user-scoped queries."""

    def get(self, item_id: int) -> Optional[ReadingListItem]:
        return db.session.get(ReadingListItem, item_id)

    def get_by_user(self, user_id: int) -> List[ReadingListItem]:
        return (
            db.session.query(ReadingListItem)
            .filter_by(user_id=user_id)
            .order_by(ReadingListItem.created_at.desc())
            .all()
        )

    def get_by_user_and_external_id(
        self, user_id: int, external_id: str
    ) -> Optional[ReadingListItem]:
        return (
            db.session.query(ReadingListItem)
            .filter_by(user_id=user_id, external_id=external_id)
            .first()
        )

    def count_by_user(self, user_id: int) -> int:
        return db.session.query(ReadingListItem).filter_by(user_id=user_id).count()

    def add(self, item: ReadingListItem) -> ReadingListItem:
        db.session.add(item)
        db.session.flush()
        return item

    def update(self, item: ReadingListItem, **changes) -> ReadingListItem:
        for key, value in changes.items():
            setattr(item, key, value)
        db.session.flush()
        return item

    def delete(self, item: ReadingListItem) -> None:
        db.session.delete(item)
        db.session.flush()

    def delete_by_user(self, user_id: int) -> int:
        count = db.session.query(ReadingListItem).filter_by(user_id=user_id).count()
        db.session.query(ReadingListItem).filter_by(user_id=user_id).delete(
            synchronize_session=False
        )
        db.session.flush()
        return count

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()
