"""Persistence for admin.roles and its relationships."""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.modules.permissions.models import Permission
from app.modules.roles.models import Role, RolePermission, UserRole


class RoleRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_all(self) -> list[Role]:
        return list(self._db.scalars(select(Role).order_by(Role.name)).all())

    def get(self, role_id: UUID) -> Role | None:
        return self._db.get(Role, role_id)

    def name_taken(self, name: str, *, excluding: UUID | None = None) -> bool:
        query = select(Role.id).where(func.lower(Role.name) == name.lower())
        if excluding:
            query = query.where(Role.id != excluding)
        return self._db.scalar(query) is not None

    def add(self, role: Role) -> Role:
        self._db.add(role)
        self._db.flush()
        return role

    def delete(self, role: Role) -> None:
        self._db.delete(role)

    def permissions_of(self, role_id: UUID) -> list[Permission]:
        return list(self._db.scalars(
            select(Permission)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id, Permission.deprecated_at.is_(None))
            .order_by(Permission.code)).all())

    def set_permissions(self, role_id: UUID, permission_ids: set[UUID]) -> None:
        self._db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        self._db.add_all(RolePermission(role_id=role_id, permission_id=item)
                         for item in permission_ids)

    def roles_of_user(self, user_id: UUID) -> list[Role]:
        return list(self._db.scalars(
            select(Role).join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id).order_by(Role.name)).all())

    def get_assignment(self, user_id: UUID, role_id: UUID) -> UserRole | None:
        return self._db.get(UserRole, (user_id, role_id))

    def add_assignment(self, assignment: UserRole) -> None:
        self._db.add(assignment)

    def delete_assignment(self, assignment: UserRole) -> None:
        self._db.delete(assignment)
