"""Role errors."""

from app.core.exceptions import Conflict, PermissionDenied


class SystemRoleProtected(PermissionDenied):
    code = "system_role_protected"
    message = "Only a Super Admin can change a system role."


class RoleExceedsActor(PermissionDenied):
    code = "role_exceeds_actor"
    message = "You cannot manage a role that grants access you do not have."


class RoleNameTaken(Conflict):
    code = "role_name_taken"
    message = "A role with that name already exists."
