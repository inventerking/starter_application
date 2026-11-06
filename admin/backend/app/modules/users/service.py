"""User Management: Admin operators manage Client users. It never touches admin.users.

The Admin permission that allows the operation was already checked at the route. The roles and
permissions handled here belong to the Client domain and are looked up only in client.* tables.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.core.exceptions import NotFound
from app.core.request_context import RequestContext
from app.core.security import generate_temporary_password, get_password_service
from app.modules.admins.models import AdminUser
from app.modules.audit.actions import AuditAction
from app.modules.client_domain.audit import CrossDomainAudit
from app.modules.client_domain.models import (
    ClientAuditLog,
    ClientPermission,
    ClientRole,
    ClientUser,
    ClientUserPermission,
)
from app.modules.client_domain.repository import (
    ClientAuditRepository,
    ClientPermissionRepository,
    ClientRoleRepository,
    ClientUserRepository,
)
from app.modules.users.exceptions import DuplicateClientIdentity, InvalidClientPermission

TARGET = "client_user"


class ClientUserManagementService:
    def __init__(self, db: Session, context: RequestContext, actor: AdminUser) -> None:
        self._db = db
        self._users = ClientUserRepository(db)
        self._roles = ClientRoleRepository(db)
        self._permissions = ClientPermissionRepository(db)
        self._activity = ClientAuditRepository(db)
        self._audit = CrossDomainAudit(db, context, actor.id)
        self._passwords = get_password_service()

    # --- reads ---------------------------------------------------------------------------------

    def list_page(
        self, page: int, page_size: int, search: str | None
    ) -> tuple[list[ClientUser], int]:
        return self._users.list_page(page=page, page_size=page_size, search=search)

    def get(self, user_id: UUID) -> ClientUser:
        user = self._users.get(user_id)
        if user is None:
            raise NotFound
        return user

    def roles_of(self, user_id: UUID) -> list[ClientRole]:
        return self._roles.roles_of_user(self.get(user_id).id)

    def overrides_of(self, user_id: UUID) -> list[tuple[ClientUserPermission, ClientPermission]]:
        return self._permissions.list_overrides(self.get(user_id).id)

    def mfa_status(self, user_id: UUID) -> tuple[ClientUser, int]:
        user = self.get(user_id)
        return user, self._users.count_unused_recovery_codes(user.id)

    def activity(
        self, user_id: UUID, page: int, page_size: int
    ) -> tuple[list[ClientAuditLog], int]:
        return self._activity.list_for_user(
            self.get(user_id).id, page=page, page_size=page_size)

    # --- lifecycle -----------------------------------------------------------------------------

    def create(
        self, email: str, username: str, full_name: str | None, role_ids: list[UUID] | None
    ) -> tuple[ClientUser, str]:
        self._ensure_identity_free(email, username)
        roles = (self._roles.default_roles() if role_ids is None
                 else [self._get_role(item) for item in set(role_ids)])
        temporary_password = generate_temporary_password()
        user = self._users.add(ClientUser(
            email=email, username=username, full_name=full_name,
            password_hash=self._passwords.hash(temporary_password), must_change_password=True))
        for role in roles:
            self._roles.assign(user.id, role.id)
        self._audit.record(AuditAction.USER_CREATED, TARGET, user.id,
                           {"role_ids": [str(role.id) for role in roles]})
        self._db.commit()
        return user, temporary_password

    def update(self, user_id: UUID, changes: dict) -> ClientUser:
        user = self.get(user_id)
        self._ensure_identity_free(changes.get("email"), changes.get("username"), excluding=user.id)
        for field in ("email", "username"):
            if changes.get(field) is not None:
                setattr(user, field, changes[field])
        if "full_name" in changes:
            user.full_name = changes["full_name"]
        self._audit.record(AuditAction.USER_UPDATED, TARGET, user.id, {"changed": sorted(changes)})
        self._db.commit()
        return user

    def activate(self, user_id: UUID) -> ClientUser:
        user = self.get(user_id)
        user.is_active = True
        user.failed_login_count = 0
        user.locked_until = None
        self._audit.record(AuditAction.USER_ACTIVATED, TARGET, user.id)
        self._db.commit()
        return user

    def deactivate(self, user_id: UUID) -> ClientUser:
        user = self.get(user_id)
        user.is_active = False
        self._users.revoke_sessions(user.id, "account_deactivated", utcnow())
        self._audit.record(AuditAction.USER_DEACTIVATED, TARGET, user.id)
        self._db.commit()
        return user

    def delete(self, user_id: UUID) -> None:
        """A soft delete, so that audit history keeps its meaning."""
        user = self.get(user_id)
        now = utcnow()
        user.deleted_at = now
        user.is_active = False
        self._users.revoke_sessions(user.id, "account_deleted", now)
        self._audit.record(AuditAction.USER_DELETED, TARGET, user.id)
        self._db.commit()

    # --- security ------------------------------------------------------------------------------

    def issue_temporary_password(self, user_id: UUID) -> str:
        user = self.get(user_id)
        temporary_password = generate_temporary_password()
        user.password_hash = self._passwords.hash(temporary_password)
        user.must_change_password = True
        self._users.revoke_sessions(user.id, "password_reset_by_admin", utcnow())
        self._audit.record(AuditAction.PASSWORD_RESET_BY_ADMIN, TARGET, user.id)
        self._db.commit()
        return temporary_password

    def reset_mfa(self, user_id: UUID) -> None:
        user = self.get(user_id)
        now = utcnow()
        user.mfa_enabled = False
        user.mfa_enrollment_required = True
        user.mfa_secret_encrypted = None
        user.mfa_key_id = None
        user.mfa_confirmed_at = None
        user.mfa_last_used_step = None
        self._users.clear_mfa_artifacts(user.id, now)
        self._users.revoke_sessions(user.id, "mfa_reset", now)
        self._audit.record(AuditAction.MFA_RESET, TARGET, user.id)
        self._db.commit()

    def revoke_sessions(self, user_id: UUID) -> int:
        user = self.get(user_id)
        count = self._users.revoke_sessions(user.id, "revoked_by_admin", utcnow())
        self._audit.record(AuditAction.SESSION_REVOKED, TARGET, user.id, {"count": count})
        self._db.commit()
        return count

    # --- roles and overrides -------------------------------------------------------------------

    def assign_role(self, user_id: UUID, role_id: UUID) -> None:
        user = self.get(user_id)
        role = self._get_role(role_id)
        if self._roles.get_assignment(user.id, role.id) is None:
            self._roles.assign(user.id, role.id)
            self._audit.record(AuditAction.ROLE_ASSIGNED, TARGET, user.id,
                               {"role_id": str(role.id)})
        self._db.commit()

    def remove_role(self, user_id: UUID, role_id: UUID) -> None:
        user = self.get(user_id)
        assignment = self._roles.get_assignment(user.id, role_id)
        if assignment is None:
            raise NotFound
        self._roles.remove_assignment(assignment)
        self._audit.record(AuditAction.ROLE_REMOVED, TARGET, user.id, {"role_id": str(role_id)})
        self._db.commit()

    def set_override(
        self, user_id: UUID, permission_id: UUID, effect: str, reason: str | None
    ) -> None:
        user = self.get(user_id)
        permission = self._permissions.get_active(permission_id)
        if permission is None:
            raise InvalidClientPermission
        override = self._permissions.get_override(user.id, permission.id)
        if override is None:
            self._permissions.add_override(ClientUserPermission(
                user_id=user.id, permission_id=permission.id, effect=effect, reason=reason))
        else:
            override.effect = effect
            override.reason = reason
        action = (AuditAction.PERMISSION_GRANTED if effect == "ALLOW"
                  else AuditAction.PERMISSION_DENIED)
        self._audit.record(action, TARGET, user.id, {"permission_id": str(permission.id)})
        self._db.commit()

    def remove_override(self, user_id: UUID, permission_id: UUID) -> None:
        user = self.get(user_id)
        override = self._permissions.get_override(user.id, permission_id)
        if override is None:
            raise NotFound
        self._permissions.delete_override(override)
        self._audit.record(AuditAction.PERMISSION_OVERRIDE_REMOVED, TARGET, user.id,
                           {"permission_id": str(permission_id)})
        self._db.commit()

    # --- helpers -------------------------------------------------------------------------------

    def _ensure_identity_free(
        self, email: str | None, username: str | None, *, excluding: UUID | None = None
    ) -> None:
        if email and self._users.email_taken(email, excluding=excluding):
            raise DuplicateClientIdentity
        if username and self._users.username_taken(username, excluding=excluding):
            raise DuplicateClientIdentity

    def _get_role(self, role_id: UUID) -> ClientRole:
        role = self._roles.get(role_id)
        if role is None:
            raise NotFound("That Client role does not exist.")
        return role
