"""Permissions for managing Admin role definitions."""

from app.modules.permissions.registry import registry

ADMIN_ROLES_VIEW = registry.register("admin_roles", "view", "View Admin roles")
ADMIN_ROLES_CREATE = registry.register("admin_roles", "create", "Create Admin roles")
ADMIN_ROLES_UPDATE = registry.register("admin_roles", "update", "Update Admin roles")
ADMIN_ROLES_DELETE = registry.register("admin_roles", "delete", "Delete Admin roles")
