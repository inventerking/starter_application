"""MFA business rules: enrollment, login challenges, recovery, disable and reset."""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crypto import SecretCipher, get_mfa_cipher
from app.core.database import utcnow
from app.core.request_context import RequestContext
from app.core.security import get_password_service, hash_token
from app.modules.audit.actions import AuditAction
from app.modules.audit.service import ACTOR_ANONYMOUS, AuditService
from app.modules.authentication.exceptions import InvalidCredentials
from app.modules.authentication.models import SCOPE_FULL, SCOPE_MFA_ENROLLMENT, UserSession
from app.modules.authentication.rate_limit import enforce_rate_limit
from app.modules.authentication.service import AuthenticationService, mfa_enrollment_needed
from app.modules.authentication.session_service import IssuedTokens, SessionService
from app.modules.mfa import recovery_codes, totp
from app.modules.mfa.exceptions import (
    InvalidMfaChallenge,
    InvalidMfaCode,
    MfaAlreadyEnabled,
    MfaNotEnabled,
    MfaSetupNotStarted,
)
from app.modules.mfa.models import MfaChallenge
from app.modules.mfa.repository import MfaRepository
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

DOMAIN = "client"
TARGET = "user"


def secret_owner(user_id: UUID) -> str:
    """Encryption associated data: ties a stored secret to this domain and this account."""
    return f"{DOMAIN}:{user_id}"


@dataclass(frozen=True)
class MfaSetup:
    secret: str
    provisioning_uri: str
    qr_code: str
    issuer: str
    account: str


class MfaService:
    def __init__(self, db: Session, context: RequestContext) -> None:
        self._db = db
        self._context = context
        self._settings = get_settings()
        self._cipher: SecretCipher = get_mfa_cipher()
        self._passwords = get_password_service()
        self._repository = MfaRepository(db)
        self._users = UserRepository(db)
        self._sessions = SessionService(db)
        self._audit = AuditService(db)

    # --- enrollment ----------------------------------------------------------------------------

    def setup(self, user: User, password: str) -> MfaSetup:
        """Create a pending secret. MFA stays disabled until a first code is confirmed."""
        self._limit(f"mfa-setup:{user.id}")
        if user.mfa_enabled:
            raise MfaAlreadyEnabled
        if not self._passwords.verify(user.password_hash, password):
            raise InvalidCredentials("The current password is incorrect.")
        secret = totp.generate_secret()
        user.mfa_secret_encrypted = self._cipher.encrypt(secret, secret_owner(user.id))
        user.mfa_key_id = self._cipher.key_id
        user.mfa_last_used_step = None
        self._db.commit()
        title = self._settings.mfa_title
        uri = totp.provisioning_uri(secret, user.email, title)
        return MfaSetup(secret, uri, totp.qr_code_data_uri(uri), title, user.email)

    def confirm(self, user: User, session: UserSession, code: str) -> list[str]:
        self._limit(f"mfa-confirm:{user.id}")
        if user.mfa_enabled:
            raise MfaAlreadyEnabled
        if not user.mfa_secret_encrypted:
            raise MfaSetupNotStarted
        self._require_code(user, code)
        user.mfa_enabled = True
        user.mfa_enrollment_required = False
        user.mfa_confirmed_at = utcnow()
        codes = self._store_new_recovery_codes(user.id)
        session.scope = SCOPE_FULL
        self._sessions.revoke_all(user.id, "mfa_enabled", except_session=session.id)
        self._audit.record(AuditAction.MFA_ENABLED, self._context, actor_id=user.id,
                           target_type=TARGET, target_id=user.id)
        self._db.commit()
        return codes

    # --- login ---------------------------------------------------------------------------------

    def verify_login(
        self, challenge_token: str, code: str | None, recovery_code: str | None
    ) -> IssuedTokens:
        self._limit(f"mfa-login:ip:{self._context.ip_address}", factor=5)
        challenge = self._repository.get_challenge_for_update(hash_token(challenge_token))
        now = utcnow()
        if (challenge is None or challenge.consumed_at or challenge.expires_at <= now
                or challenge.attempts >= self._settings.mfa_challenge_max_attempts):
            raise InvalidMfaChallenge
        user = self._users.get_for_update(challenge.user_id)
        if (user is None or not user.is_active or not user.mfa_enabled
                or (user.locked_until and user.locked_until > now)):
            challenge.consumed_at = now
            self._db.commit()
            raise InvalidMfaChallenge
        self._limit(f"mfa-login:user:{user.id}")

        used_recovery = False
        if recovery_code:
            used_recovery = verified = self._consume_recovery_code(user.id, recovery_code)
        else:
            verified = self._code_is_valid(user, code or "")
        if not verified:
            self._fail_challenge(challenge, user)

        challenge.consumed_at = now
        user.failed_login_count = 0
        user.locked_until = None
        if used_recovery:
            self._audit.record(AuditAction.MFA_RECOVERY_CODE_USED, self._context, actor_id=user.id,
                               target_type=TARGET, target_id=user.id)
        return AuthenticationService(self._db, self._context).complete_login(user, SCOPE_FULL)

    def _fail_challenge(self, challenge: MfaChallenge, user: User) -> None:
        challenge.attempts += 1
        if challenge.attempts >= self._settings.mfa_challenge_max_attempts:
            challenge.consumed_at = utcnow()
        # Failures count toward the account lockout, so new challenges cannot extend guessing.
        user.failed_login_count += 1
        if user.failed_login_count >= self._settings.login_max_failures:
            user.locked_until = utcnow() + timedelta(minutes=self._settings.login_lockout_minutes)
            user.failed_login_count = 0
        self._audit.record(AuditAction.MFA_CHALLENGE_FAILED, self._context,
                           actor_type=ACTOR_ANONYMOUS, target_type=TARGET, target_id=user.id)
        self._db.commit()
        raise InvalidMfaCode

    # --- management ----------------------------------------------------------------------------

    def status(self, user: User) -> tuple[bool, int]:
        return user.mfa_enabled, self._repository.count_unused_recovery_codes(user.id)

    def regenerate_recovery_codes(self, user: User, code: str) -> list[str]:
        self._limit(f"mfa-regenerate:{user.id}")
        if not user.mfa_enabled:
            raise MfaNotEnabled
        self._require_code(user, code)
        codes = self._store_new_recovery_codes(user.id)
        self._audit.record(AuditAction.MFA_RECOVERY_CODES_REGENERATED, self._context,
                           actor_id=user.id, target_type=TARGET, target_id=user.id)
        self._db.commit()
        return codes

    def disable(self, user: User, session: UserSession, password: str, code: str) -> None:
        self._limit(f"mfa-disable:{user.id}")
        if not user.mfa_enabled:
            raise MfaNotEnabled
        if not self._passwords.verify(user.password_hash, password):
            raise InvalidCredentials("The current password is incorrect.")
        self._require_code(user, code)
        self._clear(user)
        self._sessions.revoke_all(user.id, "mfa_disabled", except_session=session.id)
        if mfa_enrollment_needed(user):
            session.scope = SCOPE_MFA_ENROLLMENT
        self._audit.record(AuditAction.MFA_DISABLED, self._context, actor_id=user.id,
                           target_type=TARGET, target_id=user.id)
        self._db.commit()

    # --- helpers -------------------------------------------------------------------------------

    def _clear(self, user: User) -> None:
        user.mfa_enabled = False
        user.mfa_secret_encrypted = None
        user.mfa_key_id = None
        user.mfa_confirmed_at = None
        user.mfa_last_used_step = None
        self._repository.delete_recovery_codes(user.id)
        self._repository.invalidate_challenges(user.id, utcnow())

    def _limit(self, key: str, factor: int = 1) -> None:
        enforce_rate_limit(key, limit=self._settings.rate_limit_mfa_per_minute * factor)

    def _require_code(self, user: User, code: str) -> None:
        if not self._code_is_valid(user, code):
            raise InvalidMfaCode

    def _code_is_valid(self, user: User, code: str) -> bool:
        """Valid only once per time-step: a replayed code is rejected even if still in window."""
        if not user.mfa_secret_encrypted:
            return False
        secret = self._cipher.decrypt(user.mfa_secret_encrypted, secret_owner(user.id))
        step = totp.matching_step(secret, code, self._settings.mfa_totp_valid_window)
        if step is None or not self._repository.claim_totp_step(user.id, step):
            return False
        return True

    def _store_new_recovery_codes(self, user_id: UUID) -> list[str]:
        codes = recovery_codes.generate_codes()
        self._repository.replace_recovery_codes(
            user_id, [self._passwords.hash(item) for item in codes])
        return codes

    def _consume_recovery_code(self, user_id: UUID, raw_code: str) -> bool:
        candidate = recovery_codes.normalize(raw_code)
        for stored in self._repository.unused_recovery_codes(user_id):
            if self._passwords.verify(stored.code_hash, candidate):
                stored.used_at = utcnow()
                return True
        return False
