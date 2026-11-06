"""Permissions that Client users hold. They are unrelated to any Admin permission."""

from app.modules.permissions.registry import registry

PROFILE_VIEW = registry.register("profile", "view", "View your own profile")
PROFILE_UPDATE = registry.register("profile", "update", "Update your own profile")
ACTIVITY_VIEW = registry.register("activity", "view", "View your own account activity")
