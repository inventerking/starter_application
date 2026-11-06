"""User Management permissions. They authorize Admin operators and grant nothing to Client users,
and they grant nothing in Admin Management."""

from app.modules.permissions.registry import registry

USERS_VIEW = registry.register("users", "view", "View Client users")
USERS_CREATE = registry.register("users", "create", "Create Client users")
USERS_UPDATE = registry.register("users", "update", "Update Client users")
USERS_DELETE = registry.register("users", "delete", "Delete Client users")
USERS_ACTIVATE = registry.register("users", "activate", "Activate Client users")
USERS_DEACTIVATE = registry.register("users", "deactivate", "Deactivate Client users")
USERS_ROLES_MANAGE = registry.register("users.roles", "manage", "Assign and remove Client roles")
USERS_PERMISSIONS_MANAGE = registry.register(
    "users.permissions", "manage", "Manage direct Client permission overrides")
USERS_MFA_VIEW_STATUS = registry.register("users.mfa", "view_status", "View Client user MFA status")
USERS_MFA_RESET = registry.register("users.mfa", "reset", "Reset a Client user's MFA")
USERS_PASSWORD_RESET = registry.register(
    "users.password", "reset", "Issue a temporary password to a Client user")
USERS_SESSIONS_REVOKE = registry.register(
    "users.sessions", "revoke", "Revoke a Client user's sessions")
USERS_ACTIVITY_VIEW = registry.register("users.activity", "view", "View a Client user's activity")
