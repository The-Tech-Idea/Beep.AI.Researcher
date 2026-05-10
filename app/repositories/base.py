"""Repository pattern base class.

All repositories inherit from this ABC, which provides standard CRUD
operations over SQLAlchemy sessions. This abstracts database access
away from services so they only talk to repositories.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Sequence
from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """Base repository with standard CRUD operations.

    Subclasses must implement `model_class` and any custom queries.
    """

    def __init__(self, session: Session):
        self._session = session

    @property
    @abstractmethod
    def model_class(self) -> type[T]:
        """Return the SQLAlchemy model class for this repository."""
        ...

    # ── Read ────────────────────────────────────────────────────────────────

    def get(self, id: int) -> Optional[T]:
        """Get a single entity by primary key."""
        return self._session.get(self.model_class, id)

    def get_all(self) -> List[T]:
        """Get all entities."""
        return self._session.query(self.model_class).all()

    def get_by(self, **filters) -> List[T]:
        """Get entities matching the given column=value filters."""
        query = self._session.query(self.model_class)
        for key, value in filters.items():
            query = query.filter(getattr(self.model_class, key) == value)
        return query.all()

    def get_one_by(self, **filters) -> Optional[T]:
        """Get a single entity matching filters, or None."""
        query = self._session.query(self.model_class)
        for key, value in filters.items():
            query = query.filter(getattr(self.model_class, key) == value)
        return query.first()

    def count(self, **filters) -> int:
        """Count entities matching optional filters."""
        query = self._session.query(self.model_class)
        for key, value in filters.items():
            query = query.filter(getattr(self.model_class, key) == value)
        return query.count()

    def paginate(
        self,
        page: int = 1,
        per_page: int = 20,
        order_by: Optional[str] = None,
        **filters,
    ) -> tuple[List[T], int]:
        """Paginated query with optional filters and ordering.

        Returns (items, total_count).
        """
        query = self._session.query(self.model_class)
        for key, value in filters.items():
            query = query.filter(getattr(self.model_class, key) == value)
        if order_by:
            column = getattr(self.model_class, order_by, None)
            if column is not None:
                query = query.order_by(column.desc())
        total = query.count()
        items = query.offset((page - 1) * per_page).limit(per_page).all()
        return items, total

    # ── Write ───────────────────────────────────────────────────────────────

    def add(self, entity: T) -> T:
        """Add a new entity to the session."""
        self._session.add(entity)
        self._session.flush()
        return entity

    def add_all(self, entities: Sequence[T]) -> List[T]:
        """Add multiple entities."""
        self._session.add_all(entities)
        self._session.flush()
        return list(entities)

    def update(self, entity: T, **changes) -> T:
        """Update attributes on an entity and flush."""
        for key, value in changes.items():
            setattr(entity, key, value)
        self._session.flush()
        return entity

    def delete(self, entity: T) -> None:
        """Delete an entity from the session."""
        self._session.delete(entity)
        self._session.flush()

    def delete_by(self, **filters) -> int:
        """Delete all entities matching filters. Returns count deleted."""
        query = self._session.query(self.model_class)
        for key, value in filters.items():
            query = query.filter(getattr(self.model_class, key) == value)
        count = query.count()
        query.delete(synchronize_session="fetch")
        self._session.flush()
        return count

    # ── Transaction ─────────────────────────────────────────────────────────

    def commit(self) -> None:
        """Commit the current transaction."""
        self._session.commit()

    def rollback(self) -> None:
        """Rollback the current transaction."""
        self._session.rollback()

    def flush(self) -> None:
        """Flush pending changes without committing."""
        self._session.flush()
