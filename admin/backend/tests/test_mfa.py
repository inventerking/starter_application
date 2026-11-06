from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlparse

import pytest
from sqlalchemy import select, text

from app.cli.rotate_mfa_key import rotate
from app.core.config import Settings, get_settings
from app.core.crypto import SecretCipher, get_mfa_cipher
from app.core.database import SCHEMA, utcnow
from app.modules.admins.models import AdminUser
from app.modules.audit.models import AuditLog
from app.modules.authentication.models import UserSession
from app.modules.mfa import recovery_codes, totp
from app.modules.mfa.models import MfaChallenge, MfaRecoveryCode
from app.modules.mfa.service import secret_owner
from tests.conftest import PASSWORD, auth_headers, enroll_mfa, login, totp_code

SETUP = "/api/v1/auth/mfa/setup"
CONFIRM = "/api/v1/auth/mfa/confirm"
VERIFY = "/api/v1/auth/mfa/verify-login"
DISABLE = "/api/v1/auth/mfa/disable"
REGENERATE = "/api/v1/auth/mfa/recovery-codes/regenerate"
ME = "/api/v1/auth/me"


def _actions(db):
    db.expire_all()
    return [row.action for row in db.scalars(select(AuditLog)).all()]


def _user(db, user):
    db.expire_all()
    return db.get(AdminUser, user.id)


class TestTotp:
    def test_secret_is_valid_base32_160_bits(self):
        secret = totp.generate_secret()
        assert len(secret) == 32 and secret != totp.generate_secret()

    def test_uses_mfa_title_and_standard_parameters(self):
        uri = totp.provisioning_uri("JBSWY3DPEHPK3PXP", "admin@example.com", "Starter Application")
        parsed = urlparse(uri)
        assert parsed.scheme == "otpauth" and parsed.netloc == "totp"
        assert unquote(parsed.path) == "/Starter Application:admin@example.com"
        query = parse_qs(parsed.query)
        assert query["issuer"] == ["Starter Application"]
        assert query.get("algorithm", ["SHA1"]) == ["SHA1"]
        assert query.get("digits", ["6"]) == ["6"] and query.get("period", ["30"]) == ["30"]
        assert "+" not in uri  # Some apps would display a plus sign literally.

    def test_matching_step_tolerates_skew_only_within_window(self):
        secret = totp.generate_secret()
        now = 1_700_000_010.0
        code = totp._totp(secret).at(int(now))
        assert totp.matching_step(secret, code, 1, now) == int(now) // 30
        assert totp.matching_step(secret, code, 1, now + 30) == int(now) // 30
        assert totp.matching_step(secret, code, 1, now + 90) is None
        assert totp.matching_step(secret, "abcdef", 1, now) is None
        assert totp.matching_step(secret, "12345", 1, now) is None

    def test_qr_code_is_local_svg_data_uri(self):
        assert totp.qr_code_data_uri("otpauth://totp/x").startswith("data:image/svg+xml")

    def test_recovery_code_format_and_normalization(self):
        codes = recovery_codes.generate_codes()
        assert len(codes) == 10 and len(set(codes)) == 10
        assert all(len(code) == 9 and code[4] == "-" for code in codes)
        assert recovery_codes.normalize(" abcd efgh ") == "ABCD-EFGH"


class TestSetup:
    def test_setup_does_not_enable_mfa(self, client, make_admin, db):
        user = make_admin()
        response = client.post(SETUP, headers=auth_headers(client, user), json={"password": PASSWORD})
        assert response.status_code == 200
        body = response.json()
        assert body["issuer"] == get_settings().mfa_title and body["account"] == user.email
        assert body["qr_code"].startswith("data:image/svg+xml")
        assert not _user(db, user).mfa_enabled
        assert login(client, user).json()["status"] == "authenticated"

    def test_setup_requires_password(self, client, make_admin):
        headers = auth_headers(client, make_admin())
        assert client.post(SETUP, headers=headers, json={"password": "wrong-password-1"}).status_code == 401

    def test_secret_is_encrypted_at_rest(self, client, make_admin, db):
        user = make_admin()
        secret = client.post(SETUP, headers=auth_headers(client, user),
                             json={"password": PASSWORD}).json()["secret"]
        stored = _user(db, user)
        assert secret not in stored.mfa_secret_encrypted
        assert stored.mfa_key_id == "k1"
        assert get_mfa_cipher().decrypt(stored.mfa_secret_encrypted, secret_owner(user.id)) == secret

    def test_wrong_code_does_not_enable(self, client, make_admin, db):
        user = make_admin()
        headers = auth_headers(client, user)
        client.post(SETUP, headers=headers, json={"password": PASSWORD})
        assert client.post(CONFIRM, headers=headers, json={"code": "000000"}).status_code == 400
        assert not _user(db, user).mfa_enabled

    def test_confirm_without_setup(self, client, make_admin):
        headers = auth_headers(client, make_admin())
        response = client.post(CONFIRM, headers=headers, json={"code": "123456"})
        assert response.status_code == 409 and response.json()["error"]["code"] == "mfa_setup_not_started"

    def test_confirm_enables_and_returns_hashed_recovery_codes(self, client, make_admin, db):
        user = make_admin()
        _, codes = enroll_mfa(client, auth_headers(client, user))
        assert _user(db, user).mfa_enabled and len(codes) == 10
        stored = db.scalars(select(MfaRecoveryCode.code_hash).where(
            MfaRecoveryCode.user_id == user.id)).all()
        assert len(stored) == 10 and all(value.startswith("$argon2id$") for value in stored)
        assert not set(codes) & set(stored)
        assert "MFA_ENABLED" in _actions(db)

    def test_secret_not_available_after_confirmation(self, client, make_admin):
        user = make_admin()
        headers = auth_headers(client, user)
        secret, _ = enroll_mfa(client, headers)
        assert client.post(SETUP, headers=headers, json={"password": PASSWORD}).status_code == 409
        for path in ("/api/v1/auth/mfa/status", ME):
            assert secret not in client.get(path, headers=headers).text

    def test_enabling_revokes_other_sessions(self, client, make_admin):
        user = make_admin()
        other, current = auth_headers(client, user), auth_headers(client, user)
        enroll_mfa(client, current)
        assert client.get(ME, headers=other).status_code == 401
        assert client.get(ME, headers=current).status_code == 200

    def test_changing_title_affects_new_provisioning_only(self, client, make_admin):
        settings = get_settings()
        original = settings.mfa_title
        settings.mfa_title = "Renamed Product"
        try:
            body = client.post(SETUP, headers=auth_headers(client, make_admin()),
                               json={"password": PASSWORD}).json()
        finally:
            settings.mfa_title = original
        assert body["issuer"] == "Renamed Product"
        assert "Renamed%20Product" in body["provisioning_uri"]


def _enrolled(client, make_admin):
    user = make_admin()
    secret, codes = enroll_mfa(client, auth_headers(client, user))
    client.cookies.clear()
    return user, secret, codes


class TestLoginChallenge:
    def test_password_alone_gives_no_session(self, client, make_admin, db):
        user, _, _ = _enrolled(client, make_admin)
        before = len(db.scalars(select(UserSession.id)).all())
        response = login(client, user)
        body = response.json()
        assert body["status"] == "mfa_required" and body["challenge_token"]
        assert body["access_token"] is None and "set-cookie" not in response.headers
        assert len(db.scalars(select(UserSession.id)).all()) == before

    def test_challenge_token_cannot_access_protected_apis(self, client, make_admin):
        user, _, _ = _enrolled(client, make_admin)
        challenge = login(client, user).json()["challenge_token"]
        headers = {"Authorization": f"Bearer {challenge}"}
        assert client.get(ME, headers=headers).status_code == 401
        assert client.post("/api/v1/auth/refresh").status_code == 401

    def test_valid_code_completes_login(self, client, make_admin):
        user, secret, _ = _enrolled(client, make_admin)
        challenge = login(client, user).json()["challenge_token"]
        response = client.post(VERIFY, json={"challenge_token": challenge, "code": totp_code(secret, 1)})
        assert response.status_code == 200 and response.json()["status"] == "authenticated"
        token = response.json()["access_token"]
        assert client.get(ME, headers={"Authorization": f"Bearer {token}"}).status_code == 200

    def test_challenge_is_single_use(self, client, make_admin):
        user, secret, _ = _enrolled(client, make_admin)
        challenge = login(client, user).json()["challenge_token"]
        assert client.post(VERIFY, json={"challenge_token": challenge, "code": totp_code(secret, 1)}).status_code == 200
        again = client.post(VERIFY, json={"challenge_token": challenge, "code": totp_code(secret, 1)})
        assert again.status_code == 401 and again.json()["error"]["code"] == "invalid_mfa_challenge"

    def test_expired_challenge_rejected(self, client, make_admin, db):
        user, secret, _ = _enrolled(client, make_admin)
        challenge = login(client, user).json()["challenge_token"]
        row = db.scalar(select(MfaChallenge).where(MfaChallenge.user_id == user.id))
        row.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
        assert client.post(VERIFY, json={"challenge_token": challenge, "code": totp_code(secret, 1)}).status_code == 401

    def test_totp_replay_rejected_across_challenges(self, client, make_admin):
        user, secret, _ = _enrolled(client, make_admin)
        code = totp_code(secret, 1)
        first = login(client, user).json()["challenge_token"]
        assert client.post(VERIFY, json={"challenge_token": first, "code": code}).status_code == 200
        second = login(client, user).json()["challenge_token"]
        replay = client.post(VERIFY, json={"challenge_token": second, "code": code})
        assert replay.status_code == 400 and replay.json()["error"]["code"] == "invalid_mfa_code"

    def test_brute_force_exhausts_challenge_and_locks_account(self, client, make_admin, db):
        user, secret, _ = _enrolled(client, make_admin)
        challenge = login(client, user).json()["challenge_token"]
        for _ in range(get_settings().mfa_challenge_max_attempts):
            assert client.post(VERIFY, json={"challenge_token": challenge, "code": "000000"}).status_code == 400
        final = client.post(VERIFY, json={"challenge_token": challenge, "code": totp_code(secret, 1)})
        assert final.status_code == 401
        assert _user(db, user).locked_until is not None
        assert "MFA_CHALLENGE_FAILED" in _actions(db)

    def test_inactive_user_cannot_complete_challenge(self, client, make_admin, db):
        user, secret, _ = _enrolled(client, make_admin)
        challenge = login(client, user).json()["challenge_token"]
        _user(db, user).is_active = False
        db.commit()
        assert client.post(VERIFY, json={"challenge_token": challenge, "code": totp_code(secret, 1)}).status_code == 401

    @pytest.mark.parametrize("payload", [{}, {"code": "123456", "recovery_code": "ABCD-EFGH"}])
    def test_requires_exactly_one_factor(self, client, make_admin, payload):
        user, _, _ = _enrolled(client, make_admin)
        challenge = login(client, user).json()["challenge_token"]
        assert client.post(VERIFY, json={"challenge_token": challenge, **payload}).status_code == 422


class TestRecoveryCodes:
    def test_code_works_once(self, client, make_admin, db):
        user, _, codes = _enrolled(client, make_admin)
        challenge = login(client, user).json()["challenge_token"]
        assert client.post(VERIFY, json={"challenge_token": challenge, "recovery_code": codes[0].lower()}).status_code == 200
        assert "MFA_RECOVERY_CODE_USED" in _actions(db)
        used = db.scalars(select(MfaRecoveryCode).where(MfaRecoveryCode.used_at.is_not(None))).all()
        assert len(used) == 1
        next_challenge = login(client, user).json()["challenge_token"]
        assert client.post(VERIFY, json={"challenge_token": next_challenge, "recovery_code": codes[0]}).status_code == 400

    def test_wrong_code_rejected(self, client, make_admin):
        user, _, _ = _enrolled(client, make_admin)
        challenge = login(client, user).json()["challenge_token"]
        assert client.post(VERIFY, json={"challenge_token": challenge, "recovery_code": "AAAA-BBBB"}).status_code == 400

    def test_regeneration_invalidates_old_codes(self, client, make_admin, db):
        user = make_admin()
        headers = auth_headers(client, user)
        secret, old_codes = enroll_mfa(client, headers)
        response = client.post(REGENERATE, headers=headers, json={"code": totp_code(secret, 1)})
        assert response.status_code == 200
        new_codes = response.json()["recovery_codes"]
        assert len(new_codes) == 10 and not set(new_codes) & set(old_codes)
        assert len(db.scalars(select(MfaRecoveryCode.id)).all()) == 10
        challenge = login(client, user).json()["challenge_token"]
        assert client.post(VERIFY, json={"challenge_token": challenge, "recovery_code": old_codes[0]}).status_code == 400
        assert client.post(VERIFY, json={"challenge_token": challenge, "recovery_code": new_codes[0]}).status_code == 200
        assert "MFA_RECOVERY_CODES_REGENERATED" in _actions(db)


class TestDisable:
    def test_requires_password_and_code(self, client, make_admin, db):
        user = make_admin()
        headers = auth_headers(client, user)
        secret, _ = enroll_mfa(client, headers)
        assert client.post(DISABLE, headers=headers, json={"password": "wrong-password-1", "code": totp_code(secret, 1)}).status_code == 401
        assert client.post(DISABLE, headers=headers, json={"password": PASSWORD, "code": "000000"}).status_code == 400
        assert _user(db, user).mfa_enabled

    def test_disable_clears_everything(self, client, make_admin, db):
        user = make_admin()
        other_session = None
        headers = auth_headers(client, user)
        secret, _ = enroll_mfa(client, headers)
        other = client.post(VERIFY, json={
            "challenge_token": login(client, user).json()["challenge_token"],
            "code": totp_code(secret, 1)}).json()["access_token"]
        other_session = {"Authorization": f"Bearer {other}"}
        response = client.post(DISABLE, headers=headers, json={"password": PASSWORD, "code": totp_code(secret, -1)})
        # The -1 step is older than the step just used, so it counts as replayed.
        assert response.status_code == 400
        db.execute(text(f'UPDATE "{SCHEMA}".users SET mfa_last_used_step = NULL'))
        db.commit()
        response = client.post(DISABLE, headers=headers, json={"password": PASSWORD, "code": totp_code(secret)})
        assert response.status_code == 204
        stored = _user(db, user)
        assert not stored.mfa_enabled and stored.mfa_secret_encrypted is None
        assert db.scalars(select(MfaRecoveryCode.id)).all() == []
        assert client.get(ME, headers=other_session).status_code == 401
        assert "MFA_DISABLED" in _actions(db)
        assert login(client, user).json()["status"] == "authenticated"


class TestEnforcement:
    @pytest.fixture
    def mfa_required(self):
        settings = get_settings()
        settings.admin_mfa_required = True
        yield
        settings.admin_mfa_required = False

    def test_unenrolled_user_restricted_to_enrollment(self, client, make_admin, mfa_required):
        user = make_admin()
        body = login(client, user).json()
        assert body["status"] == "mfa_enrollment_required"
        headers = {"Authorization": f"Bearer {body['access_token']}"}
        blocked = client.get("/api/v1/auth/sessions", headers=headers)
        assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "mfa_enrollment_required"
        assert client.get(ME, headers=headers).json()["mfa_enrollment_required"] is True
        enroll_mfa(client, headers)
        assert client.get("/api/v1/auth/sessions", headers=headers).status_code == 200

    def test_existing_full_session_is_restricted_when_policy_turns_on(self, client, make_admin):
        headers = auth_headers(client, make_admin())
        settings = get_settings()
        settings.admin_mfa_required = True
        try:
            assert client.get("/api/v1/auth/sessions", headers=headers).status_code == 403
        finally:
            settings.admin_mfa_required = False

    def test_refresh_keeps_restricted_scope(self, client, make_admin, mfa_required):
        login(client, make_admin())
        response = client.post("/api/v1/auth/refresh")
        assert response.json()["status"] == "mfa_enrollment_required"


class TestKeyRotation:
    def test_rotation_keeps_mfa_working(self, client, make_admin, db):
        user = make_admin()
        secret, _ = enroll_mfa(client, auth_headers(client, user))
        old_cipher = get_mfa_cipher()
        new_cipher = SecretCipher("k2", b"\x07" * 32, {"k1": old_cipher._keys["k1"]})
        with patch("app.cli.rotate_mfa_key.get_mfa_cipher", return_value=new_cipher):
            assert rotate(db) == 1
            assert rotate(db) == 0
        stored = _user(db, user)
        assert stored.mfa_key_id == "k2" and stored.mfa_secret_encrypted.startswith("v1.k2.")
        assert new_cipher.decrypt(stored.mfa_secret_encrypted, secret_owner(user.id)) == secret


def test_missing_key_fails_fast(monkeypatch):
    from pydantic import ValidationError

    monkeypatch.delenv("MFA_ENCRYPTION_KEY")
    with pytest.raises(ValidationError):
        Settings(database_password="x", _env_file=None)
