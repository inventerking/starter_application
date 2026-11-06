"""Admin Management permissions. They grant nothing in User Management."""

from app.modules.permissions.registry import registry

ADMINS_VIEW = registry.register("admins", "view", "View Admin accounts")
ADMINS_CREATE = registry.register("admins", "create", "Create Admin accounts")
ADMINS_UPDATE = registry.register("admins", "update", "Update Admin accounts")
ADMINS_DELETE = registry.register("admins", "delete", "Delete Admin accounts")
ADMINS_ACTIVATE = registry.register("admins", "activate", "Activate Admin accounts")
ADMINS_DEACTIVATE = registry.register("admins", "deactivate", "Deactivate Admin accounts")
ADMINS_ROLES_MANAGE = registry.register("admins.roles", "manage", "Assign and remove Admin roles")
ADMINS_PERMISSIONS_MANAGE = registry.register(
    "admins.permissions", "manage", "Manage direct Admin permission overrides")
ADMINS_MFA_VIEW_STATUS = registry.register("admins.mfa", "view_status", "View Admin MFA status")
ADMINS_MFA_RESET = registry.register("admins.mfa", "reset", "Reset another Admin's MFA")
ADMINS_PASSWORD_RESET = registry.register(
    "admins.password", "reset", "Issue a temporary password to an Admin")
ADMINS_SESSIONS_REVOKE = registry.register(
    "admins.sessions", "revoke", "Revoke another Admin's sessions")
ADMINS_ACTIVITY_VIEW = registry.register(
    "admins.activity", "view", "View an Admin's activity")
