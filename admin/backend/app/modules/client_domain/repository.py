"""Every read and write the Admin backend performs on the Client schema goes through this file."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.pagination import like_pattern
from app.modules.client_domain.models import (
    ClientAuditLog,
    ClientMfaChallenge,
    ClientPermission,
    ClientRecoveryCode,
    ClientRole,
    ClientRolePermission,
    ClientSession,
    ClientUser,
    ClientUserPermission,
    ClientUserRole,
)


class ClientUserRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, user_id: UUID) -> ClientUser | None:
        return self._db.scalar(
            select(ClientUser).where(ClientUser.id == user_id, ClientUser.deleted_at.is_(None)))

    def add(self, user: ClientUser) -> ClientUser:
        self._db.add(user)
        self._db.flush()
        return user

    def email_taken(self, email: str, *, excluding: UUID | None = None) -> bool:
        return self._exists(func.lower(ClientUser.email) == email.lower(), excluding)

    def username_taken(self, username: str, *, excluding: UUID | None = None) -> bool:
        return self._exists(func.lower(ClientUser.username) == username.lower(), excluding)

    def _exists(self, condition, excluding: UUID | None) -> bool:
        query = select(ClientUser.id).where(condition, ClientUser.deleted_at.is_(None))
        if excluding:
            query = query.where(ClientUser.id != excluding)
        return self._db.scalar(query) is not None

    def list_page(
        self, *, page: int, page_size: int, search: str | None
    ) -> tuple[list[ClientUser], int]:
        query = select(ClientUser).where(ClientUser.deleted_at.is_(None))
        if search:
            pattern = like_pattern(search)
            query = query.where(or_(ClientUser.email.ilike(pattern, escape="\\"),
                                    ClientUser.username.ilike(pattern, escape="\\"),
                                    ClientUser.full_name.ilike(pattern, escape="\\")))
        total = self._db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self._db.scalars(
            query.order_by(ClientUser.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)).all()
        return list(rows), total

    def revoke_sessions(self, user_id: UUID, reason: str, now: datetime) -> int:
        return self._db.execute(
            update(ClientSession)
            .where(ClientSession.user_id == user_id, ClientSession.revoked_at.is_(None))
            .values(revoked_at=now, revoke_reason=reason)
            .execution_options(synchronize_session=False)).rowcount

    def count_unused_recovery_codes(self, user_id: UUID) -> int:
        return self._db.scalar(
            select(func.count()).select_from(ClientRecoveryCode)
            .where(ClientRecoveryCode.user_id == user_id,
                   ClientRecoveryCode.used_at.is_(None))) or 0

    def clear_mfa_artifacts(self, user_id: UUID, now: datetime) -> None:
        self._db.execute(delete(ClientRecoveryCode).where(ClientRecoveryCode.user_id == user_id))
        self._db.execute(
            update(ClientMfaChallenge)
            .where(ClientMfaChallenge.user_id == user_id, ClientMfaChallenge.consumed_at.is_(None))
            .values(consumed_at=now)
            .execution_options(synchronize_session=False))


class ClientRoleRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_all(self) -> list[ClientRole]:
        return list(self._db.scalars(select(ClientRole).order_by(ClientRole.name)).all())

    def get(self, role_id: UUID) -> ClientRole | None:
        return self._db.get(ClientRole, role_id)

    def default_roles(self) -> list[ClientRole]:
        return list(self._db.scalars(
            select(ClientRole).where(ClientRole.is_default.is_(True))).all())

    def name_taken(self, name: str, *, excluding: UUID | None = None) -> bool:
        query = select(ClientRole.id).where(func.lower(ClientRole.name) == name.lower())
        if excluding:
            query = query.where(ClientRole.id != excluding)
        return self._db.scalar(query) is not None

    def add(self, role: ClientRole) -> ClientRole:
        self._db.add(role)
        self._db.flush()
        return role

    def delete(self, role: ClientRole) -> None:
        self._db.delete(role)

    def permissions_of(self, role_id: UUID) -> list[ClientPermission]:
        return list(self._db.scalars(
            select(ClientPermission)
            .join(ClientRolePermission, ClientRolePermission.permission_id == ClientPermission.id)
            .where(ClientRolePermission.role_id == role_id,
                   ClientPermission.deprecated_at.is_(None))
            .order_by(ClientPermission.code)).all())

    def set_permissions(self, role_id: UUID, permission_ids: set[UUID]) -> None:
        self._db.execute(
            delete(ClientRolePermission).where(ClientRolePermission.role_id == role_id))
        self._db.add_all(ClientRolePermission(role_id=role_id, permission_id=item)
                         for item in permission_ids)

    def roles_of_user(self, user_id: UUID) -> list[ClientRole]:
        return list(self._db.scalars(
            select(ClientRole).join(ClientUserRole, ClientUserRole.role_id == ClientRole.id)
            .where(ClientUserRole.user_id == user_id).order_by(ClientRole.name)).all())

    def get_assignment(self, user_id: UUID, role_id: UUID) -> ClientUserRole | None:
        return self._db.get(ClientUserRole, (user_id, role_id))

    def assign(self, user_id: UUID, role_id: UUID) -> None:
        self._db.add(ClientUserRole(user_id=user_id, role_id=role_id))

    def remove_assignment(self, assignment: ClientUserRole) -> None:
        self._db.delete(assignment)


class ClientPermissionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_active(self) -> list[ClientPermission]:
        return list(self._db.scalars(
            select(ClientPermission).where(ClientPermission.deprecated_at.is_(None))
            .order_by(ClientPermission.code)).all())

    def get_active(self, permission_id: UUID) -> ClientPermission | None:
        return self._db.scalar(select(ClientPermission).where(
            ClientPermission.id == permission_id, ClientPermission.deprecated_at.is_(None)))

    def get_override(self, user_id: UUID, permission_id: UUID) -> ClientUserPermission | None:
        return self._db.get(ClientUserPermission, (user_id, permission_id))

    def add_override(self, override: ClientUserPermission) -> None:
        self._db.add(override)

    def delete_override(self, override: ClientUserPermission) -> None:
        self._db.delete(override)

    def list_overrides(self, user_id: UUID) -> list[tuple[ClientUserPermission, ClientPermission]]:
        rows = self._db.execute(
            select(ClientUserPermission, ClientPermission)
            .join(ClientPermission, ClientUserPermission.permission_id == ClientPermission.id)
            .where(ClientUserPermission.user_id == user_id)
            .order_by(ClientPermission.code)).all()
        return [(row[0], row[1]) for row in rows]


class ClientAuditRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, entry: ClientAuditLog) -> None:
        self._db.add(entry)

    def list_for_user(
        self, user_id: UUID, *, page: int, page_size: int
    ) -> tuple[list[ClientAuditLog], int]:
        query = select(ClientAuditLog).where(
            or_(ClientAuditLog.actor_id == user_id, ClientAuditLog.target_id == user_id))
        total = self._db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self._db.scalars(
            query.order_by(ClientAuditLog.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size)).all()
        return list(rows), total
