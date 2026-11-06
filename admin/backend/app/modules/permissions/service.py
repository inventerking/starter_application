"""The single implementation of permission resolution for the Admin domain.

Precedence: Super Admin > direct DENY > direct ALLOW > role ALLOW > default DENY.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.modules.admins.models import AdminUser
from app.modules.permissions import catalog as _catalog  # noqa: F401
from app.modules.permissions.exceptions import PrivilegeEscalation
from app.modules.permissions.models import Permission
from app.modules.permissions.registry import PermissionDefinition, registry
from app.modules.permissions.repository import PermissionRepository


def is_allowed(
    code: str,
    *,
    is_superuser: bool,
    direct_deny: set[str],
    direct_allow: set[str],
    role_allow: set[str],
) -> bool:
    if is_superuser:
        return True
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

    def effective_codes(self, user: AdminUser) -> set[str]:
        role_allow = self._repository.role_granted_codes(user.id)
        direct_allow, direct_deny = self._repository.direct_codes(user.id)
        candidates = {item.code for item in registry.all()}
        return {
            code for code in candidates
            if is_allowed(code, is_superuser=user.is_superuser, direct_deny=direct_deny,
                          direct_allow=direct_allow, role_allow=role_allow)
        }

    def has(self, user: AdminUser, permission: PermissionDefinition) -> bool:
        return permission.code in self.effective_codes(user)

    def ensure_can_grant(self, actor: AdminUser, codes: set[str]) -> None:
        """No escalation: only a Super Admin can hand out access the actor does not hold."""
        if not actor.is_superuser and not codes <= self.effective_codes(actor):
            raise PrivilegeEscalation

    def sync_registry(self) -> SyncResult:
        """Make the database match the registry. Definitions are deprecated, never deleted,
        so that existing assignments keep their history and can be restored."""
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
