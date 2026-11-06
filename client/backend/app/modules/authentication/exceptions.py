"""Authentication errors. Credential failures all look alike to prevent account enumeration."""

from app.core.exceptions import AppError, AuthenticationRequired, Conflict, PermissionDenied


class InvalidCredentials(AuthenticationRequired):
    code = "invalid_credentials"
    message = "The credentials are incorrect."


class InvalidRefreshToken(AuthenticationRequired):
    code = "invalid_refresh_token"
    message = "The session has expired. Please sign in again."


class RefreshInProgress(Conflict):
    code = "refresh_in_progress"
    message = "The session was just refreshed. Please retry."


class PasswordChangeRequired(PermissionDenied):
    code = "password_change_required"
    message = "You must change your password before continuing."


class MfaEnrollmentRequired(PermissionDenied):
    code = "mfa_enrollment_required"
    message = "You must set up two-factor authentication before continuing."


class RegistrationDisabled(PermissionDenied):
    code = "registration_disabled"
    message = "Registration is not available."


class DuplicateIdentity(Conflict):
    code = "duplicate_identity"
    message = "That email or username is already in use."


class InvalidPasswordResetToken(AppError):
    status_code = 400
    code = "invalid_reset_token"
    message = "The password reset link is invalid or has expired."
