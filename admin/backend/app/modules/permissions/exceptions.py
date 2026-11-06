"""Authorization errors."""

from app.core.exceptions import AppError, PermissionDenied


class PrivilegeEscalation(PermissionDenied):
    code = "privilege_escalation"
    message = "You cannot grant access that you do not have yourself."


class InvalidPermission(AppError):
    status_code = 422
    code = "invalid_permission"
    message = "That permission does not exist or is no longer available."
