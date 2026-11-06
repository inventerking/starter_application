"""Password hashing (Argon2id) and opaque token primitives."""

import hashlib
import secrets
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError

PASSWORD_MAX_LENGTH = 128  # Bounds hashing cost for hostile input.


class WeakPassword(AppError):
    status_code = 422
    code = "weak_password"
    message = "The password does not meet the password policy."


class PasswordService:
    """Argon2id hashing. Each hash carries its own random salt and parameters."""

    def __init__(self, settings: Settings) -> None:
        self._hasher = PasswordHasher(
            time_cost=settings.argon2_time_cost,
            memory_cost=settings.argon2_memory_cost_kib,
            parallelism=settings.argon2_parallelism,
            type=Type.ID,
        )
        self._min_length = settings.password_min_length
        # Verified against when an account is unknown, so response timing does not reveal it.
        self._dummy_hash = self._hasher.hash(secrets.token_urlsafe(16))

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, stored_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(stored_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, stored_hash: str) -> bool:
        return self._hasher.check_needs_rehash(stored_hash)

    def dummy_verify(self, password: str) -> None:
        self.verify(self._dummy_hash, password)

    def validate_policy(self, password: str, *, forbidden: tuple[str, ...] = ()) -> None:
        if len(password) < self._min_length:
            raise WeakPassword(f"The password must have at least {self._min_length} characters.")
        if len(password) > PASSWORD_MAX_LENGTH:
            raise WeakPassword(f"The password must have at most {PASSWORD_MAX_LENGTH} characters.")
        lowered = password.lower()
        if any(item and item.lower() in lowered for item in forbidden):
            raise WeakPassword("The password must not contain your email or username.")


@lru_cache
def get_password_service() -> PasswordService:
    return PasswordService(get_settings())


def generate_token() -> str:
    """256-bit URL-safe random token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Digest for high-entropy tokens only. Passwords and recovery codes use Argon2id."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_temporary_password() -> str:
    return secrets.token_urlsafe(18)
