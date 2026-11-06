"""Persistence for admin.users."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.pagination import like_pattern
from app.modules.admins.models import AdminUser


class AdminRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, user_id: UUID) -> AdminUser | None:
        return self._db.scalar(
            select(AdminUser).where(AdminUser.id == user_id, AdminUser.deleted_at.is_(None)))

    def get_for_update(self, user_id: UUID) -> AdminUser | None:
        return self._db.scalar(
            select(AdminUser)
            .where(AdminUser.id == user_id, AdminUser.deleted_at.is_(None))
            .with_for_update())

    def get_by_identifier(self, identifier: str) -> AdminUser | None:
        lowered = identifier.strip().lower()
        return self._db.scalar(
            select(AdminUser).where(
                or_(func.lower(AdminUser.email) == lowered,
                    func.lower(AdminUser.username) == lowered),
                AdminUser.deleted_at.is_(None),
            ))

    def email_taken(self, email: str, *, excluding: UUID | None = None) -> bool:
        return self._exists(func.lower(AdminUser.email) == email.lower(), excluding)

    def username_taken(self, username: str, *, excluding: UUID | None = None) -> bool:
        return self._exists(func.lower(AdminUser.username) == username.lower(), excluding)

    def _exists(self, condition, excluding: UUID | None) -> bool:
        query = select(AdminUser.id).where(condition, AdminUser.deleted_at.is_(None))
        if excluding:
            query = query.where(AdminUser.id != excluding)
        return self._db.scalar(query) is not None

    def add(self, user: AdminUser) -> AdminUser:
        self._db.add(user)
        self._db.flush()
        return user

    def list(self, *, page: int, page_size: int, search: str | None) -> tuple[list[AdminUser], int]:
        query = select(AdminUser).where(AdminUser.deleted_at.is_(None))
        if search:
            pattern = like_pattern(search)
            query = query.where(or_(AdminUser.email.ilike(pattern, escape="\\"),
                                    AdminUser.username.ilike(pattern, escape="\\"),
                                    AdminUser.full_name.ilike(pattern, escape="\\")))
        total = self._db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self._db.scalars(
            query.order_by(AdminUser.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)).all()
        return list(rows), total

    def count_active_superusers(self, *, excluding: UUID | None = None) -> int:
        query = select(func.count()).select_from(AdminUser).where(
            AdminUser.is_superuser.is_(True),
            AdminUser.is_active.is_(True),
            AdminUser.deleted_at.is_(None),
        )
        if excluding:
            query = query.where(AdminUser.id != excluding)
        return self._db.scalar(query) or 0
