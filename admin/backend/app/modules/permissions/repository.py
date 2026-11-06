"""Persistence for permission definitions, roles' grants and direct overrides."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.permissions.models import Permission, UserPermission
from app.modules.roles.models import RolePermission, UserRole


class PermissionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_all(self, *, include_deprecated: bool = False) -> list[Permission]:
        query = select(Permission).order_by(Permission.code)
        if not include_deprecated:
            query = query.where(Permission.deprecated_at.is_(None))
        return list(self._db.scalars(query).all())

    def get_active(self, permission_id: UUID) -> Permission | None:
        return self._db.scalar(select(Permission).where(
            Permission.id == permission_id, Permission.deprecated_at.is_(None)))

    def add(self, permission: Permission) -> None:
        self._db.add(permission)

    def role_granted_codes(self, user_id: UUID) -> set[str]:
        return set(self._db.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(UserRole.user_id == user_id, Permission.deprecated_at.is_(None))).all())

    def direct_codes(self, user_id: UUID) -> tuple[set[str], set[str]]:
        """Return the (allowed, denied) codes from direct overrides."""
        rows = self._db.execute(
            select(Permission.code, UserPermission.effect)
            .join(UserPermission, UserPermission.permission_id == Permission.id)
            .where(UserPermission.user_id == user_id, Permission.deprecated_at.is_(None))).all()
        return ({code for code, effect in rows if effect == "ALLOW"},
                {code for code, effect in rows if effect == "DENY"})

    def get_override(self, user_id: UUID, permission_id: UUID) -> UserPermission | None:
        return self._db.get(UserPermission, (user_id, permission_id))

    def add_override(self, override: UserPermission) -> None:
        self._db.add(override)

    def delete_override(self, override: UserPermission) -> None:
        self._db.delete(override)

    def list_overrides(self, user_id: UUID) -> list[tuple[UserPermission, Permission]]:
        rows = self._db.execute(
            select(UserPermission, Permission)
            .join(Permission, UserPermission.permission_id == Permission.id)
            .where(UserPermission.user_id == user_id)
            .order_by(Permission.code)).all()
        return [(row[0], row[1]) for row in rows]
