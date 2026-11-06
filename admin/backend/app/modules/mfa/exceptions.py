"""MFA errors."""

from app.core.exceptions import AppError, AuthenticationRequired, Conflict


class InvalidMfaCode(AppError):
    status_code = 400
    code = "invalid_mfa_code"
    message = "The verification code is incorrect."


class InvalidMfaChallenge(AuthenticationRequired):
    code = "invalid_mfa_challenge"
    message = "The sign-in attempt has expired. Please sign in again."


class MfaAlreadyEnabled(Conflict):
    code = "mfa_already_enabled"
    message = "Two-factor authentication is already enabled."


class MfaNotEnabled(Conflict):
    code = "mfa_not_enabled"
    message = "Two-factor authentication is not enabled."


class MfaSetupNotStarted(Conflict):
    code = "mfa_setup_not_started"
    message = "Start two-factor authentication setup first."
