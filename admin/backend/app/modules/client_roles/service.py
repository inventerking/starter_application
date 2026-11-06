"""Client role definitions, managed by Admin operators. Stored only in client.* tables."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFound
from app.core.request_context import RequestContext
from app.modules.admins.models import AdminUser
from app.modules.audit.actions import AuditAction
from app.modules.client_domain.audit import CrossDomainAudit
from app.modules.client_domain.models import ClientPermission, ClientRole
from app.modules.client_domain.repository import ClientPermissionRepository, ClientRoleRepository
from app.modules.client_roles.exceptions import (
    ClientRoleNameTaken,
    ClientSystemRoleProtected,
    InvalidClientRolePermission,
)

TARGET = "client_role"


class ClientRoleManagementService:
    def __init__(self, db: Session, context: RequestContext, actor: AdminUser) -> None:
        self._db = db
        self._actor = actor
        self._roles = ClientRoleRepository(db)
        self._permissions = ClientPermissionRepository(db)
        self._audit = CrossDomainAudit(db, context, actor.id)

    def list_all(self) -> list[ClientRole]:
        return self._roles.list_all()

    def list_permissions(self) -> list[ClientPermission]:
        return self._permissions.list_active()

    def get(self, role_id: UUID) -> ClientRole:
        role = self._roles.get(role_id)
        if role is None:
            raise NotFound("That Client role does not exist.")
        return role

    def permissions_of(self, role_id: UUID) -> list[ClientPermission]:
        return self._roles.permissions_of(role_id)

    def create(
        self, name: str, description: str | None, is_default: bool, permission_ids: list[UUID]
    ) -> ClientRole:
        if self._roles.name_taken(name):
            raise ClientRoleNameTaken
        rows = self._resolve_permissions(permission_ids)
        role = self._roles.add(
            ClientRole(name=name, description=description, is_default=is_default))
        self._roles.set_permissions(role.id, {row.id for row in rows})
        self._audit.record(AuditAction.ROLE_CREATED, TARGET, role.id)
        self._db.commit()
        return role

    def update(self, role_id: UUID, changes: dict) -> ClientRole:
        role = self.get(role_id)
        self._ensure_editable(role)
        if changes.get("name") is not None:
            if self._roles.name_taken(changes["name"], excluding=role.id):
                raise ClientRoleNameTaken
            role.name = changes["name"]
        if "description" in changes:
            role.description = changes["description"]
        if changes.get("is_default") is not None:
            role.is_default = changes["is_default"]
        self._audit.record(AuditAction.ROLE_UPDATED, TARGET, role.id, {"changed": sorted(changes)})
        self._db.commit()
        return role

    def set_permissions(self, role_id: UUID, permission_ids: list[UUID]) -> ClientRole:
        role = self.get(role_id)
        self._ensure_editable(role)
        rows = self._resolve_permissions(permission_ids)
        self._roles.set_permissions(role.id, {row.id for row in rows})
        self._audit.record(AuditAction.ROLE_UPDATED, TARGET, role.id, {"changed": ["permissions"]})
        self._db.commit()
        return role

    def delete(self, role_id: UUID) -> None:
        role = self.get(role_id)
        self._ensure_editable(role)
        self._audit.record(AuditAction.ROLE_DELETED, TARGET, role.id)
        self._roles.delete(role)
        self._db.commit()

    def _ensure_editable(self, role: ClientRole) -> None:
        if role.is_system and not self._actor.is_superuser:
            raise ClientSystemRoleProtected

    def _resolve_permissions(self, permission_ids: list[UUID]) -> list[ClientPermission]:
        rows = [self._permissions.get_active(item) for item in set(permission_ids)]
        if any(row is None for row in rows):
            raise InvalidClientRolePermission
        return rows  # type: ignore[return-value]
