"""Permissions of the permissions module."""

from app.modules.permissions.registry import registry

ADMIN_PERMISSIONS_VIEW = registry.register(
    "admin_permissions", "view", "View the Admin permission registry")
