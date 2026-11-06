"""Admin Management: operates on admin.users only and never touches Client data."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.core.exceptions import NotFound
from app.core.request_context import RequestContext
from app.core.security import generate_temporary_password, get_password_service
from app.modules.admins.exceptions import (
    DuplicateIdentity,
    LastSuperAdmin,
    SelfActionForbidden,
    SuperAdminDeletionForbidden,
    SuperAdminProtected,
    TargetMorePrivileged,
)
from app.modules.admins.models import AdminUser
from app.modules.admins.repository import AdminRepository
from app.modules.audit.actions import AuditAction
from app.modules.audit.models import AuditLog
from app.modules.audit.repository import AuditRepository
from app.modules.audit.service import AuditService
from app.modules.authentication.session_service import SessionService
from app.modules.mfa.repository import MfaRepository
from app.modules.mfa.service import MfaService
from app.modules.permissions.exceptions import InvalidPermission
from app.modules.permissions.models import Permission, UserPermission
from app.modules.permissions.repository import PermissionRepository
from app.modules.permissions.service import PermissionService
from app.modules.roles.models import Role, UserRole
from app.modules.roles.repository import RoleRepository

TARGET = "admin"


class AdminManagementService:
    def __init__(self, db: Session, context: RequestContext, actor: AdminUser) -> None:
        self._db = db
        self._context = context
        self._actor = actor
        self._admins = AdminRepository(db)
        self._roles = RoleRepository(db)
        self._permission_rows = PermissionRepository(db)
        self._permissions = PermissionService(db)
        self._sessions = SessionService(db)
        self._mfa = MfaRepository(db)
        self._audit = AuditService(db)
        self._passwords = get_password_service()

    # --- reads ---------------------------------------------------------------------------------

    def list_page(
        self, page: int, page_size: int, search: str | None
    ) -> tuple[list[AdminUser], int]:
        return self._admins.list_page(page=page, page_size=page_size, search=search)

    def get(self, admin_id: UUID) -> AdminUser:
        admin = self._admins.get(admin_id)
        if admin is None:
            raise NotFound
        return admin

    def roles_of(self, admin_id: UUID) -> list[Role]:
        return self._roles.roles_of_user(self.get(admin_id).id)

    def overrides_of(self, admin_id: UUID) -> list[tuple[UserPermission, Permission]]:
        return self._permission_rows.list_overrides(self.get(admin_id).id)

    def effective_permissions_of(self, admin_id: UUID) -> list[str]:
        return sorted(self._permissions.effective_codes(self.get(admin_id)))

    def mfa_status(self, admin_id: UUID) -> tuple[AdminUser, int]:
        admin = self.get(admin_id)
        return admin, self._mfa.count_unused_recovery_codes(admin.id)

    def activity(self, admin_id: UUID, page: int, page_size: int) -> tuple[list[AuditLog], int]:
        return AuditRepository(self._db).list_page(
            page=page, page_size=page_size, involving=self.get(admin_id).id)

    # --- account lifecycle ---------------------------------------------------------------------

    def create(self, email: str, username: str, full_name: str | None) -> tuple[AdminUser, str]:
        """New accounts are never Super Admins and hold no roles or permissions."""
        self._ensure_identity_free(email, username)
        temporary_password = generate_temporary_password()
        admin = self._admins.add(AdminUser(
            email=email, username=username, full_name=full_name,
            password_hash=self._passwords.hash(temporary_password),
            must_change_password=True, created_by=self._actor.id))
        self._record(AuditAction.ADMIN_CREATED, admin)
        self._db.commit()
        return admin, temporary_password

    def update(self, admin_id: UUID, changes: dict) -> AdminUser:
        admin = self.get(admin_id)
        self._ensure_can_manage(admin)
        self._ensure_identity_free(
            changes.get("email"), changes.get("username"), excluding=admin.id)
        for field in ("email", "username"):
            if changes.get(field) is not None:
                setattr(admin, field, changes[field])
        if "full_name" in changes:
            admin.full_name = changes["full_name"]
        self._record(AuditAction.ADMIN_UPDATED, admin, {"changed": sorted(changes)})
        self._db.commit()
        return admin

    def activate(self, admin_id: UUID) -> AdminUser:
        admin = self.get(admin_id)
        self._ensure_can_manage(admin)
        admin.is_active = True
        admin.failed_login_count = 0
        admin.locked_until = None
        self._record(AuditAction.ADMIN_ACTIVATED, admin)
        self._db.commit()
        return admin

    def deactivate(self, admin_id: UUID) -> AdminUser:
        admin = self.get(admin_id)
        self._ensure_not_self(admin)
        self._ensure_can_manage(admin)
        if admin.is_superuser:
            self._ensure_another_superuser_remains(admin)
        admin.is_active = False
        self._sessions.revoke_all(admin.id, "account_deactivated")
        self._record(AuditAction.ADMIN_DEACTIVATED, admin)
        self._db.commit()
        return admin

    def delete(self, admin_id: UUID) -> None:
        """A soft delete, so that audit history keeps its meaning."""
        admin = self.get(admin_id)
        self._ensure_not_self(admin)
        if admin.is_superuser:
            raise SuperAdminDeletionForbidden
        self._ensure_can_manage(admin)
        admin.deleted_at = utcnow()
        admin.is_active = False
        self._sessions.revoke_all(admin.id, "account_deleted")
        self._record(AuditAction.ADMIN_DELETED, admin)
        self._db.commit()

    # --- security actions ----------------------------------------------------------------------

    def issue_temporary_password(self, admin_id: UUID) -> str:
        admin = self.get(admin_id)
        self._ensure_not_self(admin)
        self._ensure_can_manage(admin)
        temporary_password = generate_temporary_password()
        admin.password_hash = self._passwords.hash(temporary_password)
        admin.must_change_password = True
        self._sessions.revoke_all(admin.id, "password_reset_by_admin")
        self._record(AuditAction.PASSWORD_RESET_BY_ADMIN, admin)
        self._db.commit()
        return temporary_password

    def reset_mfa(self, admin_id: UUID) -> None:
        admin = self.get(admin_id)
        self._ensure_not_self(admin)
        self._ensure_can_manage(admin)
        MfaService(self._db, self._context).reset_by_admin(admin, self._actor.id)
        self._db.commit()

    def revoke_sessions(self, admin_id: UUID) -> int:
        admin = self.get(admin_id)
        self._ensure_not_self(admin)
        self._ensure_can_manage(admin)
        count = self._sessions.revoke_all(admin.id, "revoked_by_admin")
        self._record(AuditAction.SESSION_REVOKED, admin, {"count": count})
        self._db.commit()
        return count

    # --- roles and overrides -------------------------------------------------------------------

    def assign_role(self, admin_id: UUID, role_id: UUID) -> None:
        admin = self.get(admin_id)
        self._ensure_can_change_access(admin)
        role = self._get_role(role_id)
        self._permissions.ensure_can_grant(
            self._actor, {row.code for row in self._roles.permissions_of(role.id)})
        if self._roles.get_assignment(admin.id, role.id) is None:
            self._roles.add_assignment(UserRole(
                user_id=admin.id, role_id=role.id, assigned_by=self._actor.id))
            self._record(AuditAction.ROLE_ASSIGNED, admin, {"role": role.name})
        self._db.commit()

    def remove_role(self, admin_id: UUID, role_id: UUID) -> None:
        admin = self.get(admin_id)
        self._ensure_can_change_access(admin)
        role = self._get_role(role_id)
        self._permissions.ensure_can_grant(
            self._actor, {row.code for row in self._roles.permissions_of(role.id)})
        assignment = self._roles.get_assignment(admin.id, role.id)
        if assignment is None:
            raise NotFound
        self._roles.delete_assignment(assignment)
        self._record(AuditAction.ROLE_REMOVED, admin, {"role": role.name})
        self._db.commit()

    def set_override(
        self, admin_id: UUID, permission_id: UUID, effect: str, reason: str | None
    ) -> None:
        admin = self.get(admin_id)
        self._ensure_can_change_access(admin)
        permission = self._permission_rows.get_active(permission_id)
        if permission is None:
            raise InvalidPermission
        self._permissions.ensure_can_grant(self._actor, {permission.code})
        override = self._permission_rows.get_override(admin.id, permission.id)
        if override is None:
            self._permission_rows.add_override(UserPermission(
                user_id=admin.id, permission_id=permission.id, effect=effect, reason=reason,
                granted_by=self._actor.id))
        else:
            override.effect = effect
            override.reason = reason
            override.granted_by = self._actor.id
        action = (AuditAction.PERMISSION_GRANTED if effect == "ALLOW"
                  else AuditAction.PERMISSION_DENIED)
        self._record(action, admin, {"permission": permission.code})
        self._db.commit()

    def remove_override(self, admin_id: UUID, permission_id: UUID) -> None:
        admin = self.get(admin_id)
        self._ensure_can_change_access(admin)
        override = self._permission_rows.get_override(admin.id, permission_id)
        if override is None:
            raise NotFound
        permission = self._db.get(Permission, permission_id)
        self._permissions.ensure_can_grant(self._actor, {permission.code})
        self._permission_rows.delete_override(override)
        self._record(AuditAction.PERMISSION_OVERRIDE_REMOVED, admin,
                     {"permission": permission.code})
        self._db.commit()

    # --- safeguards ----------------------------------------------------------------------------

    def _ensure_not_self(self, target: AdminUser) -> None:
        if target.id == self._actor.id:
            raise SelfActionForbidden

    def _ensure_can_manage(self, target: AdminUser) -> None:
        """Holding a management permission is not enough to take over a stronger account."""
        if self._actor.is_superuser or target.id == self._actor.id:
            return
        if target.is_superuser:
            raise SuperAdminProtected
        if not (self._permissions.effective_codes(target)
                <= self._permissions.effective_codes(self._actor)):
            raise TargetMorePrivileged

    def _ensure_can_change_access(self, target: AdminUser) -> None:
        if self._actor.is_superuser:
            return
        self._ensure_not_self(target)
        self._ensure_can_manage(target)

    def _ensure_another_superuser_remains(self, target: AdminUser) -> None:
        # Locking serializes two Super Admins deactivating each other at the same moment.
        self._admins.lock_superusers()
        if self._admins.count_active_superusers(excluding=target.id) == 0:
            raise LastSuperAdmin

    def _ensure_identity_free(
        self, email: str | None, username: str | None, *, excluding: UUID | None = None
    ) -> None:
        if email and self._admins.email_taken(email, excluding=excluding):
            raise DuplicateIdentity
        if username and self._admins.username_taken(username, excluding=excluding):
            raise DuplicateIdentity

    def _get_role(self, role_id: UUID) -> Role:
        role = self._roles.get(role_id)
        if role is None:
            raise NotFound("That Admin role does not exist.")
        return role

    def _record(self, action: AuditAction, target: AdminUser, details: dict | None = None) -> None:
        self._audit.record(action, self._context, actor_id=self._actor.id, target_type=TARGET,
                           target_id=target.id, details=details)
