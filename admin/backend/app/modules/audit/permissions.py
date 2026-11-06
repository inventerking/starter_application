"""Audit permissions."""

from app.modules.permissions.registry import registry

AUDIT_VIEW = registry.register("audit", "view", "View the Admin audit log")
