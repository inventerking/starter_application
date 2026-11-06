"""Client role management errors."""

from app.core.exceptions import AppError, Conflict, PermissionDenied


class ClientRoleNameTaken(Conflict):
    code = "role_name_taken"
    message = "A Client role with that name already exists."


class ClientSystemRoleProtected(PermissionDenied):
    code = "system_role_protected"
    message = "Only a Super Admin can change a system role."


class InvalidClientRolePermission(AppError):
    status_code = 422
    code = "invalid_permission"
    message = "That Client permission does not exist or is no longer available."
