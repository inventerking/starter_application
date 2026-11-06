"""Admin role definitions. A non-Super Admin can only touch roles within their own access."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFound
from app.core.request_context import RequestContext
from app.modules.admins.models import AdminUser
from app.modules.audit.actions import AuditAction
from app.modules.audit.service import AuditService
from app.modules.permissions.exceptions import InvalidPermission
from app.modules.permissions.models import Permission
from app.modules.permissions.repository import PermissionRepository
from app.modules.permissions.service import PermissionService
from app.modules.roles.exceptions import RoleExceedsActor, RoleNameTaken, SystemRoleProtected
from app.modules.roles.models import Role
from app.modules.roles.repository import RoleRepository

TARGET = "admin_role"


class AdminRoleService:
    def __init__(self, db: Session, context: RequestContext, actor: AdminUser) -> None:
        self._db = db
        self._context = context
        self._actor = actor
        self._roles = RoleRepository(db)
        self._permission_rows = PermissionRepository(db)
        self._permissions = PermissionService(db)
        self._audit = AuditService(db)

    def list_all(self) -> list[Role]:
        return self._roles.list_all()

    def get(self, role_id: UUID) -> Role:
        role = self._roles.get(role_id)
        if role is None:
            raise NotFound
        return role

    def permissions_of(self, role_id: UUID) -> list[Permission]:
        return self._roles.permissions_of(role_id)

    def create(self, name: str, description: str | None, permission_ids: list[UUID]) -> Role:
        if self._roles.name_taken(name):
            raise RoleNameTaken
        rows = self._resolve_permissions(permission_ids)
        self._permissions.ensure_can_grant(self._actor, {row.code for row in rows})
        role = self._roles.add(Role(name=name, description=description))
        self._roles.set_permissions(role.id, {row.id for row in rows})
        self._record(AuditAction.ROLE_CREATED, role, {"name": name})
        self._db.commit()
        return role

    def update(self, role_id: UUID, changes: dict) -> Role:
        role = self.get(role_id)
        self._ensure_can_manage(role)
        name = changes.get("name")
        if name is not None:
            if self._roles.name_taken(name, excluding=role.id):
                raise RoleNameTaken
            role.name = name
        if "description" in changes:
            role.description = changes["description"]
        self._record(AuditAction.ROLE_UPDATED, role, {"changed": sorted(changes)})
        self._db.commit()
        return role

    def set_permissions(self, role_id: UUID, permission_ids: list[UUID]) -> Role:
        role = self.get(role_id)
        self._ensure_can_manage(role)
        rows = self._resolve_permissions(permission_ids)
        self._permissions.ensure_can_grant(self._actor, {row.code for row in rows})
        self._roles.set_permissions(role.id, {row.id for row in rows})
        self._record(AuditAction.ROLE_UPDATED, role,
                     {"permissions": sorted(row.code for row in rows)})
        self._db.commit()
        return role

    def delete(self, role_id: UUID) -> None:
        role = self.get(role_id)
        self._ensure_can_manage(role)
        self._record(AuditAction.ROLE_DELETED, role, {"name": role.name})
        self._roles.delete(role)
        self._db.commit()

    def _ensure_can_manage(self, role: Role) -> None:
        if self._actor.is_superuser:
            return
        if role.is_system:
            raise SystemRoleProtected
        codes = {row.code for row in self._roles.permissions_of(role.id)}
        if not codes <= self._permissions.effective_codes(self._actor):
            raise RoleExceedsActor

    def _resolve_permissions(self, permission_ids: list[UUID]) -> list[Permission]:
        rows = [self._permission_rows.get_active(item) for item in set(permission_ids)]
        if any(row is None for row in rows):
            raise InvalidPermission
        return rows  # type: ignore[return-value]

    def _record(self, action: AuditAction, role: Role, details: dict) -> None:
        self._audit.record(action, self._context, actor_id=self._actor.id,
                           target_type=TARGET, target_id=role.id, details=details)
