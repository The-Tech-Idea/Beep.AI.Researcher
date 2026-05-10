"""User repository — data access for User model."""

from __future__ import annotations

from typing import List, Optional

from app.extensions.db import db
from app.models.core import User


class UserRepository:
    """Repository for User CRUD and auth-related queries."""

    @property
    def model_class(self) -> type[User]:
        return User

    def get(self, user_id: int) -> Optional[User]:
        return db.session.get(User, user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        return (
            db.session.query(User)
            .filter(db.func.lower(User.email) == email.lower())
            .first()
        )

    def get_by_username(self, username: str) -> Optional[User]:
        return (
            db.session.query(User)
            .filter(db.func.lower(User.username) == username.lower())
            .first()
        )

    def get_all(self, *, limit: int = 100, offset: int = 0) -> List[User]:
        return (
            db.session.query(User)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count(self) -> int:
        return db.session.query(User).count()

    def add(self, user: User) -> User:
        db.session.add(user)
        db.session.flush()
        return user

    def update(self, user: User, **changes) -> User:
        for key, value in changes.items():
            setattr(user, key, value)
        db.session.flush()
        return user

    def delete(self, user: User) -> None:
        db.session.delete(user)
        db.session.flush()

    def commit(self) -> None:
        db.session.commit()

    def rollback(self) -> None:
        db.session.rollback()

    def exists(self) -> bool:
        """Check if any users exist (used for setup check)."""
        return db.session.query(User).first() is not None
