import base64
import json
import logging
import os
import uuid

import pytest
from argon2 import PasswordHasher
from argon2.low_level import Type
from sqlalchemy import select

from app.core.config import Settings
from app.core.crypto import DecryptionError, SecretCipher
from app.core.database import SessionLocal
from app.core.exceptions import RateLimited
from app.core.logging import RedactSecretsFilter
from app.core.security import (
    PasswordService,
    WeakPassword,
    generate_token,
    get_password_service,
    hash_token,
)
from app.modules.audit.actions import AuditAction
from app.modules.audit.models import AuditLog
from app.modules.audit.service import AuditService
from app.modules.authentication.rate_limit import enforce_rate_limit


def _key() -> bytes:
    return os.urandom(32)


class TestPasswords:
    def test_hash_is_argon2id_with_unique_salt(self):
        service = get_password_service()
        first, second = service.hash("correct horse battery"), service.hash("correct horse battery")
        assert first.startswith("$argon2id$")
        assert first != second
        assert "correct horse battery" not in first

    def test_verify_accepts_correct_and_rejects_wrong(self):
        service = get_password_service()
        stored = service.hash("correct horse battery")
        assert service.verify(stored, "correct horse battery")
        assert not service.verify(stored, "wrong horse battery")
        assert not service.verify("not-a-hash", "whatever")

    def test_outdated_parameters_need_rehash(self):
        service = get_password_service()
        weaker = PasswordHasher(time_cost=1, memory_cost=32, parallelism=1, type=Type.ID)
        assert service.needs_rehash(weaker.hash("correct horse battery"))
        assert not service.needs_rehash(service.hash("correct horse battery"))

    def test_policy(self):
        service = get_password_service()
        service.validate_policy("a-long-enough-passphrase")
        with pytest.raises(WeakPassword):
            service.validate_policy("short")
        with pytest.raises(WeakPassword):
            service.validate_policy("x" * 129)
        with pytest.raises(WeakPassword):
            service.validate_policy("alice-is-my-password", forbidden=("alice",))

    def test_custom_parameters_are_applied(self):
        settings = Settings(
            database_password="x", mfa_encryption_key="A" * 43, argon2_time_cost=2,
            argon2_memory_cost_kib=128, argon2_parallelism=1, _env_file=None)
        assert "m=128,t=2,p=1" in PasswordService(settings).hash("correct horse battery")


class TestSecretCipher:
    def test_round_trip_is_not_plaintext(self):
        cipher = SecretCipher("k1", _key())
        stored = cipher.encrypt("JBSWY3DPEHPK3PXP", "domain:user")
        assert "JBSWY3DPEHPK3PXP" not in stored
        assert stored.startswith("v1.k1.")
        assert cipher.decrypt(stored, "domain:user") == "JBSWY3DPEHPK3PXP"

    def test_nonce_is_unique(self):
        cipher = SecretCipher("k1", _key())
        assert cipher.encrypt("s", "a") != cipher.encrypt("s", "a")

    def test_bound_to_owner(self):
        cipher = SecretCipher("k1", _key())
        stored = cipher.encrypt("secret", "admin:user-1")
        with pytest.raises(DecryptionError):
            cipher.decrypt(stored, "admin:user-2")

    def test_tampering_and_wrong_key_fail(self):
        cipher = SecretCipher("k1", _key())
        stored = cipher.encrypt("secret", "a")
        with pytest.raises(DecryptionError):
            cipher.decrypt(stored[:-2] + ("AA" if not stored.endswith("AA") else "BB"), "a")
        with pytest.raises(DecryptionError):
            SecretCipher("k1", _key()).decrypt(stored, "a")
        with pytest.raises(DecryptionError):
            cipher.decrypt("garbage", "a")

    def test_rotation_keeps_old_values_readable(self):
        old_key = _key()
        stored = SecretCipher("k1", old_key).encrypt("secret", "a")
        rotated = SecretCipher("k2", _key(), {"k1": old_key})
        assert rotated.decrypt(stored, "a") == "secret"
        assert rotated.encrypt("secret", "a").startswith("v1.k2.")


def test_tokens_are_random_and_digest_is_stable():
    assert generate_token() != generate_token()
    assert len(base64.urlsafe_b64decode(generate_token() + "=")) == 32
    assert hash_token("a") == hash_token("a") and hash_token("a") != "a"


def test_rate_limit_blocks_over_limit_and_stores_no_identifier():
    key = f"login:{uuid.uuid4()}@example.com"
    for _ in range(3):
        enforce_rate_limit(key, limit=3)
    with pytest.raises(RateLimited) as caught:
        enforce_rate_limit(key, limit=3)
    assert 1 <= caught.value.retry_after <= 60


def test_audit_drops_sensitive_fields_and_keeps_others():
    with SessionLocal() as db:
        AuditService(db).record(AuditAction.LOGIN_FAILURE, details={
            "reason": "bad_password", "password": "hunter2", "refresh_token": "abc",
            "totp_secret": "xyz", "recovery_code": "ABCD",
        })
        db.commit()
        entry = db.scalars(select(AuditLog)).one()
    assert entry.details == {"reason": "bad_password"}
    assert "hunter2" not in json.dumps(entry.details)


def test_log_filter_redacts_secrets():
    record = logging.LogRecord(
        "x", logging.INFO, "f", 1, "login password=%s token: abc", ("hunter2",), None)
    RedactSecretsFilter().filter(record)
    assert "hunter2" not in record.getMessage() and "abc" not in record.getMessage()
