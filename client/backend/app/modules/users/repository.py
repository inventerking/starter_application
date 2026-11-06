"""Persistence for client.users."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.pagination import like_pattern
from app.modules.users.models import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, user_id: UUID) -> User | None:
        return self._db.scalar(
            select(User).where(User.id == user_id, User.deleted_at.is_(None)))

    def get_for_update(self, user_id: UUID) -> User | None:
        return self._db.scalar(
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .with_for_update())

    def get_by_identifier(self, identifier: str) -> User | None:
        lowered = identifier.strip().lower()
        return self._db.scalar(
            select(User).where(
                or_(func.lower(User.email) == lowered,
                    func.lower(User.username) == lowered),
                User.deleted_at.is_(None),
            ))

    def email_taken(self, email: str, *, excluding: UUID | None = None) -> bool:
        return self._exists(func.lower(User.email) == email.lower(), excluding)

    def username_taken(self, username: str, *, excluding: UUID | None = None) -> bool:
        return self._exists(func.lower(User.username) == username.lower(), excluding)

    def _exists(self, condition, excluding: UUID | None) -> bool:
        query = select(User.id).where(condition, User.deleted_at.is_(None))
        if excluding:
            query = query.where(User.id != excluding)
        return self._db.scalar(query) is not None

    def add(self, user: User) -> User:
        self._db.add(user)
        self._db.flush()
        return user

    def list_page(
        self, *, page: int, page_size: int, search: str | None
    ) -> tuple[list[User], int]:
        query = select(User).where(User.deleted_at.is_(None))
        if search:
            pattern = like_pattern(search)
            query = query.where(or_(User.email.ilike(pattern, escape="\\"),
                                    User.username.ilike(pattern, escape="\\"),
                                    User.full_name.ilike(pattern, escape="\\")))
        total = self._db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self._db.scalars(
            query.order_by(User.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)).all()
        return list(rows), total
