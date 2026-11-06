"""The single implementation of permission resolution for the Client domain.

Precedence: direct DENY > direct ALLOW > role ALLOW > default DENY. There is no Super Admin here.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.modules.permissions import catalog as _catalog  # noqa: F401
from app.modules.permissions.models import Permission
from app.modules.permissions.registry import PermissionDefinition, registry
from app.modules.permissions.repository import PermissionRepository
from app.modules.roles.models import Role, RolePermission
from app.modules.users.models import User

DEFAULT_ROLE_NAME = "Member"
DEFAULT_ROLE_PERMISSIONS = ("profile.view", "profile.update", "activity.view")


def is_allowed(
    code: str, *, direct_deny: set[str], direct_allow: set[str], role_allow: set[str]
) -> bool:
    if code in direct_deny:
        return False
    if code in direct_allow:
        return True
    return code in role_allow


@dataclass(frozen=True)
class SyncResult:
    added: int
    updated: int
    deprecated: int


class PermissionService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repository = PermissionRepository(db)

    def effective_codes(self, user: User) -> set[str]:
        role_allow = self._repository.role_granted_codes(user.id)
        direct_allow, direct_deny = self._repository.direct_codes(user.id)
        return {
            item.code for item in registry.all()
            if is_allowed(item.code, direct_deny=direct_deny, direct_allow=direct_allow,
                          role_allow=role_allow)
        }

    def has(self, user: User, permission: PermissionDefinition) -> bool:
        return permission.code in self.effective_codes(user)

    def sync_registry(self) -> SyncResult:
        """Make the database match the registry. Definitions are deprecated, never deleted."""
        existing = {item.code: item for item in self._repository.list_all(include_deprecated=True)}
        added = updated = deprecated = 0
        for definition in registry.all():
            row = existing.pop(definition.code, None)
            if row is None:
                self._repository.add(Permission(
                    resource=definition.resource, action=definition.action,
                    code=definition.code, description=definition.description))
                added += 1
            elif row.description != definition.description or row.deprecated_at is not None:
                row.description = definition.description
                row.deprecated_at = None
                updated += 1
        for row in existing.values():
            if row.deprecated_at is None:
                row.deprecated_at = utcnow()
                deprecated += 1
        self._db.flush()
        return SyncResult(added, updated, deprecated)

    def ensure_default_role(self) -> None:
        """First-run seed only. Administrators may later rename or replace the role freely."""
        if self._db.scalar(select(Role.id).limit(1)) is not None:
            return
        role = Role(name=DEFAULT_ROLE_NAME, description="Default role for new users",
                    is_default=True)
        self._db.add(role)
        self._db.flush()
        rows = {item.code: item for item in self._repository.list_all()}
        self._db.add_all(RolePermission(role_id=role.id, permission_id=rows[code].id)
                         for code in DEFAULT_ROLE_PERMISSIONS)
        self._db.flush()
