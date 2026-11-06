"""Authentication business rules: login, refresh, logout, password change and reset."""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import utcnow
from app.core.exceptions import NotFound
from app.core.request_context import RequestContext
from app.core.security import generate_token, get_password_service, hash_token
from app.modules.audit.actions import AuditAction
from app.modules.audit.service import ACTOR_ANONYMOUS, ACTOR_USER, AuditService
from app.modules.authentication.exceptions import (
    DuplicateIdentity,
    InvalidCredentials,
    InvalidPasswordResetToken,
    InvalidRefreshToken,
    RefreshInProgress,
    RegistrationDisabled,
)
from app.modules.authentication.models import (
    SCOPE_FULL,
    SCOPE_MFA_ENROLLMENT,
    PasswordResetToken,
    UserSession,
)
from app.modules.authentication.password_reset_delivery import PasswordResetDelivery
from app.modules.authentication.rate_limit import enforce_rate_limit
from app.modules.authentication.repository import PasswordResetRepository, SessionRepository
from app.modules.authentication.session_service import IssuedTokens, SessionService
from app.modules.mfa.repository import MfaRepository
from app.modules.roles.models import UserRole
from app.modules.roles.repository import RoleRepository
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

TARGET = "user"


def mfa_enrollment_needed(user: User) -> bool:
    """Enforced in the backend: the global setting or a reset forces enrollment."""
    required = get_settings().client_mfa_required or user.mfa_enrollment_required
    return required and not user.mfa_enabled


@dataclass(frozen=True)
class LoginResult:
    status: str
    tokens: IssuedTokens | None = None
    challenge_token: str | None = None
    challenge_expires_in: int | None = None


class AuthenticationService:
    def __init__(self, db: Session, context: RequestContext) -> None:
        self._db = db
        self._context = context
        self._settings = get_settings()
        self._passwords = get_password_service()
        self._users = UserRepository(db)
        self._sessions = SessionRepository(db)
        self._session_service = SessionService(db)
        self._resets = PasswordResetRepository(db)
        self._mfa = MfaRepository(db)
        self._audit = AuditService(db)

    # --- registration --------------------------------------------------------------------------

    def register(
        self, email: str, username: str, full_name: str | None, password: str
    ) -> None:
        """Off by default. A deployment turns it on once it has chosen a registration policy."""
        if not self._settings.registration_enabled:
            raise RegistrationDisabled
        enforce_rate_limit(f"register:ip:{self._context.ip_address}",
                           limit=self._settings.rate_limit_login_per_minute)
        if self._users.email_taken(email) or self._users.username_taken(username):
            raise DuplicateIdentity
        self._passwords.validate_policy(password, forbidden=(email, username))
        user = self._users.add(User(
            email=email, username=username, full_name=full_name,
            password_hash=self._passwords.hash(password)))
        for role in RoleRepository(self._db).default_roles():
            self._db.add(UserRole(user_id=user.id, role_id=role.id))
        self._audit.record(AuditAction.USER_REGISTERED, self._context, actor_id=user.id,
                           target_type=TARGET, target_id=user.id)
        self._db.commit()

    # --- login ---------------------------------------------------------------------------------

    def login(self, identifier: str, password: str) -> LoginResult:
        limit = self._settings.rate_limit_login_per_minute
        normalized = identifier.strip().lower()
        enforce_rate_limit(f"login:ip:{self._context.ip_address}", limit=limit * 5)
        enforce_rate_limit(f"login:identifier:{normalized}", limit=limit)

        user = self._users.get_by_identifier(identifier)
        if user is None:
            self._passwords.dummy_verify(password)
            self._fail_login(None, "unknown_account")
        now = utcnow()
        if user.locked_until and user.locked_until > now:
            self._passwords.dummy_verify(password)
            self._fail_login(user, "account_locked")
        if not self._passwords.verify(user.password_hash, password):
            user.failed_login_count += 1
            if user.failed_login_count >= self._settings.login_max_failures:
                user.locked_until = now + timedelta(minutes=self._settings.login_lockout_minutes)
                user.failed_login_count = 0
            self._fail_login(user, "bad_password")
        if not user.is_active:
            self._fail_login(user, "account_inactive")

        user.failed_login_count = 0
        user.locked_until = None
        if self._passwords.needs_rehash(user.password_hash):
            user.password_hash = self._passwords.hash(password)
        return self._after_password_verified(user)

    def _fail_login(self, user: User | None, reason: str) -> None:
        # The attempted identifier is not recorded: users sometimes type a password into that field.
        self._audit.record(
            AuditAction.LOGIN_FAILURE,
            self._context,
            actor_type=ACTOR_ANONYMOUS,
            target_type=TARGET if user else None,
            target_id=user.id if user else None,
            details={"reason": reason},
        )
        self._db.commit()
        raise InvalidCredentials

    def _after_password_verified(self, user: User) -> LoginResult:
        if user.mfa_enabled:
            token = generate_token()
            lifetime = self._settings.mfa_challenge_expire_seconds
            self._mfa.create_challenge(
                user.id, hash_token(token), utcnow() + timedelta(seconds=lifetime),
                self._context.ip_address)
            self._db.commit()
            return LoginResult("mfa_required", challenge_token=token,
                               challenge_expires_in=lifetime)
        if mfa_enrollment_needed(user):
            tokens = self.complete_login(user, SCOPE_MFA_ENROLLMENT)
            return LoginResult("mfa_enrollment_required", tokens=tokens)
        return LoginResult("authenticated", tokens=self.complete_login(user, SCOPE_FULL))

    def complete_login(self, user: User, scope: str) -> IssuedTokens:
        tokens = self._session_service.issue(user.id, scope, self._context)
        user.last_login_at = utcnow()
        self._audit.record(
            AuditAction.LOGIN_SUCCESS, self._context, actor_id=user.id,
            target_type=TARGET, target_id=user.id, details={"scope": scope})
        self._db.commit()
        return tokens

    # --- refresh and logout --------------------------------------------------------------------

    def refresh(self, raw_token: str | None) -> IssuedTokens:
        if not raw_token:
            raise InvalidRefreshToken
        token = self._sessions.get_refresh_token(hash_token(raw_token))
        if token is None:
            raise InvalidRefreshToken
        session = self._sessions.get_for_update(token.session_id)
        now = utcnow()
        if session is None or session.revoked_at or session.expires_at <= now:
            raise InvalidRefreshToken
        if token.used_at:
            age = (now - token.used_at).total_seconds()
            if age <= self._settings.refresh_reuse_grace_seconds:
                # Two tabs refreshing at once. Nothing is issued, so this gives an attacker nothing.
                self._db.rollback()
                raise RefreshInProgress
            self._session_service.revoke(session, "refresh_token_reuse")
            self._audit.record(
                AuditAction.REFRESH_TOKEN_REUSE, self._context, actor_id=session.user_id,
                target_type=TARGET, target_id=session.user_id)
            self._db.commit()
            raise InvalidRefreshToken
        user = self._users.get(session.user_id)
        if user is None or not user.is_active:
            self._session_service.revoke(session, "account_inactive")
            self._db.commit()
            raise InvalidRefreshToken
        token.used_at = now
        tokens = self._session_service.rotate(session)
        self._db.commit()
        return tokens

    def logout(self, *, session: UserSession | None, raw_refresh_token: str | None) -> None:
        if session is None and raw_refresh_token:
            token = self._sessions.get_refresh_token(hash_token(raw_refresh_token))
            session = self._sessions.get_for_update(token.session_id) if token else None
        if session is None or session.revoked_at:
            return
        self._session_service.revoke(session, "logout")
        self._audit.record(AuditAction.LOGOUT, self._context, actor_id=session.user_id,
                           target_type=TARGET, target_id=session.user_id)
        self._db.commit()

    # --- sessions ------------------------------------------------------------------------------

    def list_sessions(self, user_id: UUID) -> list[UserSession]:
        return self._sessions.list_active(user_id, utcnow())

    def revoke_session(self, user_id: UUID, session_id: UUID) -> None:
        session = self._sessions.get_for_update(session_id)
        if session is None or session.user_id != user_id:
            raise NotFound
        self._session_service.revoke(session, "user_revoked")
        self._audit.record(AuditAction.SESSION_REVOKED, self._context, actor_id=user_id,
                           target_type=TARGET, target_id=user_id)
        self._db.commit()

    def revoke_other_sessions(self, user_id: UUID, current_session: UUID) -> int:
        count = self._session_service.revoke_all(
            user_id, "user_revoked", except_session=current_session)
        self._audit.record(AuditAction.SESSION_REVOKED, self._context, actor_id=user_id,
                           target_type=TARGET, target_id=user_id, details={"count": count})
        self._db.commit()
        return count

    # --- passwords -----------------------------------------------------------------------------

    def change_password(
        self, user: User, session: UserSession, current: str, new: str
    ) -> None:
        enforce_rate_limit(f"password-change:{user.id}",
                           limit=self._settings.rate_limit_login_per_minute)
        if not self._passwords.verify(user.password_hash, current):
            raise InvalidCredentials("The current password is incorrect.")
        self._set_password(user, new)
        self._session_service.revoke_all(user.id, "password_changed", except_session=session.id)
        self._audit.record(AuditAction.PASSWORD_CHANGED, self._context, actor_id=user.id,
                           target_type=TARGET, target_id=user.id)
        self._db.commit()

    def request_password_reset(self, email: str, delivery: PasswordResetDelivery) -> None:
        """Always succeeds from the caller's view, so it cannot be used to discover accounts."""
        enforce_rate_limit(f"password-reset:ip:{self._context.ip_address}",
                           limit=self._settings.rate_limit_login_per_minute)
        enforce_rate_limit(f"password-reset:email:{email.lower()}", limit=5, window_seconds=3600)
        user = self._users.get_by_identifier(email)
        if not delivery.enabled or user is None or not user.is_active:
            return
        now = utcnow()
        self._resets.invalidate_for_user(user.id, now)
        token = generate_token()
        self._resets.add(PasswordResetToken(
            user_id=user.id, token_hash=hash_token(token),
            expires_at=now + timedelta(minutes=self._settings.password_reset_expire_minutes)))
        self._audit.record(AuditAction.PASSWORD_RESET_REQUESTED, self._context,
                           actor_type=ACTOR_ANONYMOUS, target_type=TARGET, target_id=user.id)
        self._db.commit()
        delivery.send(user.email, token)

    def confirm_password_reset(self, raw_token: str, new_password: str) -> None:
        enforce_rate_limit(f"password-reset-confirm:ip:{self._context.ip_address}",
                           limit=self._settings.rate_limit_login_per_minute)
        token = self._resets.get_for_update(hash_token(raw_token))
        now = utcnow()
        if token is None or token.used_at or token.expires_at <= now:
            raise InvalidPasswordResetToken
        user = self._users.get_for_update(token.user_id)
        if user is None or not user.is_active:
            raise InvalidPasswordResetToken
        self._set_password(user, new_password)
        token.used_at = now
        user.failed_login_count = 0
        user.locked_until = None
        self._session_service.revoke_all(user.id, "password_reset")
        self._audit.record(AuditAction.PASSWORD_RESET_COMPLETED, self._context,
                           actor_type=ACTOR_USER, actor_id=user.id,
                           target_type=TARGET, target_id=user.id)
        self._db.commit()

    def _set_password(self, user: User, new_password: str) -> None:
        self._passwords.validate_policy(new_password, forbidden=(user.email, user.username))
        user.password_hash = self._passwords.hash(new_password)
        user.password_changed_at = utcnow()
        user.must_change_password = False
