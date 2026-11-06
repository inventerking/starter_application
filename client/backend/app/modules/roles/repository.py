"""Reads client.roles. Administrators manage role definitions through the Admin control plane."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.roles.models import Role, UserRole


class RoleRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def default_roles(self) -> list[Role]:
        return list(self._db.scalars(select(Role).where(Role.is_default.is_(True))).all())

    def roles_of_user(self, user_id: UUID) -> list[Role]:
        return list(self._db.scalars(
            select(Role).join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id).order_by(Role.name)).all())
