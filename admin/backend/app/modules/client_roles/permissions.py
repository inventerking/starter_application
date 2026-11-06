"""Permissions for managing Client role definitions. Separate from Admin roles."""

from app.modules.permissions.registry import registry

CLIENT_ROLES_VIEW = registry.register("client_roles", "view", "View Client roles")
CLIENT_ROLES_CREATE = registry.register("client_roles", "create", "Create Client roles")
CLIENT_ROLES_UPDATE = registry.register("client_roles", "update", "Update Client roles")
CLIENT_ROLES_DELETE = registry.register("client_roles", "delete", "Delete Client roles")
CLIENT_PERMISSIONS_VIEW = registry.register(
    "client_permissions", "view", "View the Client permission registry")
