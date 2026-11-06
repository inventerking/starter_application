"""User Management errors."""

from app.core.exceptions import AppError, Conflict


class DuplicateClientIdentity(Conflict):
    code = "duplicate_identity"
    message = "That email or username is already in use."


class InvalidClientPermission(AppError):
    status_code = 422
    code = "invalid_permission"
    message = "That Client permission does not exist or is no longer available."
