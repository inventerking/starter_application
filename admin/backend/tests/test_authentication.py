from datetime import timedelta

import pytest
from sqlalchemy import select, text

from app.cli.create_superadmin import SuperAdminAlreadyExists, create_superadmin
from app.cli.set_superadmin import LastSuperAdmin, set_superadmin
from app.core.config import get_settings
from app.core.database import SCHEMA, utcnow
from app.core.http_security import refresh_cookie_name
from app.core.security import get_password_service, hash_token
from app.modules.admins.models import AdminUser
from app.modules.audit.models import AuditLog
from app.modules.authentication.models import PasswordResetToken, UserSession
from app.modules.authentication.password_reset_delivery import get_password_reset_delivery
from tests.conftest import ORIGIN_HEADERS, PASSWORD, auth_headers, login

ME = "/api/v1/auth/me"
REFRESH = "/api/v1/auth/refresh"


def _actions(db):
    db.expire_all()
    return [row.action for row in db.scalars(select(AuditLog)).all()]


class TestLogin:
    def test_valid_login_issues_tokens_and_httponly_cookie(self, client, make_admin, db):
        user = make_admin()
        response = login(client, user)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "authenticated" and body["access_token"]
        cookie = response.headers["set-cookie"]
        assert "HttpOnly" in cookie and "SameSite=strict" in cookie
        assert "Path=/api/v1/auth" in cookie
        assert "refresh" not in "".join(body.keys())
        assert "LOGIN_SUCCESS" in _actions(db)

    def test_login_by_username_case_insensitive(self, client, make_admin):
        user = make_admin()
        response = client.post("/api/v1/auth/login", json={
            "identifier": user.username.upper(), "password": PASSWORD})
        assert response.status_code == 200

    def test_failures_are_indistinguishable(self, client, make_admin, db):
        user = make_admin()
        inactive = make_admin(is_active=False)
        wrong = login(client, user, "wrong-password-123")
        unknown = client.post("/api/v1/auth/login", json={
            "identifier": "ghost@example.com", "password": PASSWORD})
        disabled = login(client, inactive)
        assert wrong.status_code == unknown.status_code == disabled.status_code == 401
        assert wrong.json() == unknown.json() == disabled.json()
        assert _actions(db).count("LOGIN_FAILURE") == 3

    def test_audit_never_contains_the_submitted_password(self, client, make_admin, db):
        login(client, make_admin(), "typed-secret-value-1")
        rows = db.execute(text(f'SELECT details::text FROM "{SCHEMA}".audit_logs')).scalars().all()
        assert rows and "typed-secret-value-1" not in " ".join(rows)

    def test_lockout_after_repeated_failures(self, client, make_admin):
        user = make_admin()
        for _ in range(get_settings().login_max_failures):
            assert login(client, user, "wrong-password-123").status_code == 401
        assert login(client, user).status_code == 401

    def test_rate_limit(self, client, make_admin):
        user = make_admin()
        statuses = [login(client, user, "wrong-password-123").status_code
                    for _ in range(get_settings().rate_limit_login_per_minute + 1)]
        assert statuses[-1] == 429

    def test_outdated_hash_is_upgraded_on_login(self, client, make_admin, db):
        from argon2 import PasswordHasher
        from argon2.low_level import Type

        old = PasswordHasher(time_cost=1, memory_cost=32, parallelism=1, type=Type.ID).hash(PASSWORD)
        user = make_admin(password_hash=old)
        assert login(client, user).status_code == 200
        db.expire_all()
        assert db.get(AdminUser, user.id).password_hash != old
        assert not get_password_service().needs_rehash(db.get(AdminUser, user.id).password_hash)

    def test_password_hash_never_returned(self, client, make_admin):
        user = make_admin()
        response = client.get(ME, headers=auth_headers(client, user))
        assert "password" not in response.text.replace("must_change_password", "")
        assert "argon2" not in response.text

    def test_csrf_guard_rejects_foreign_origin_and_missing_header(self, make_admin):
        from fastapi.testclient import TestClient

        from app.main import app

        user = make_admin()
        payload = {"identifier": user.email, "password": PASSWORD}
        bare = TestClient(app)
        assert bare.post("/api/v1/auth/login", json=payload).status_code == 403
        assert bare.post("/api/v1/auth/login", json=payload, headers={
            "Origin": "https://evil.example", "X-Requested-With": "x"}).status_code == 403
        assert bare.post("/api/v1/auth/login", json=payload, headers={
            "Origin": ORIGIN_HEADERS["Origin"]}).status_code == 403


class TestSessions:
    def test_unauthenticated_and_garbage_tokens_rejected(self, client):
        assert client.get(ME).status_code == 401
        assert client.get(ME, headers={"Authorization": "Bearer nonsense"}).status_code == 401

    def test_logout_revokes_session(self, client, make_admin):
        headers = auth_headers(client, make_admin())
        assert client.get(ME, headers=headers).status_code == 200
        assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
        assert client.get(ME, headers=headers).status_code == 401
        assert client.post(REFRESH).status_code == 401

    def test_access_token_expires(self, client, make_admin, db):
        user = make_admin()
        headers = auth_headers(client, user)
        session = db.scalar(select(UserSession).where(UserSession.user_id == user.id))
        session.access_expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
        assert client.get(ME, headers=headers).status_code == 401

    def test_session_expiry_blocks_refresh(self, client, make_admin, db):
        user = make_admin()
        login(client, user)
        session = db.scalar(select(UserSession).where(UserSession.user_id == user.id))
        session.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
        assert client.post(REFRESH).status_code == 401

    def test_deactivation_blocks_existing_token_immediately(self, client, make_admin, db):
        user = make_admin()
        headers = auth_headers(client, user)
        user.is_active = False
        db.commit()
        assert client.get(ME, headers=headers).status_code == 401
        assert client.post(REFRESH).status_code == 401

    def test_refresh_rotates_and_old_access_token_survives_until_expiry(self, client, make_admin):
        user = make_admin()
        first = login(client, user).json()["access_token"]
        old_cookie = client.cookies[refresh_cookie_name()]
        response = client.post(REFRESH)
        assert response.status_code == 200
        second = response.json()["access_token"]
        assert second != first and client.cookies[refresh_cookie_name()] != old_cookie
        for token in (first, second):
            assert client.get(ME, headers={"Authorization": f"Bearer {token}"}).status_code == 200

    def test_refresh_reuse_in_grace_is_conflict_without_new_tokens(self, client, make_admin):
        login(client, make_admin())
        old_cookie = client.cookies[refresh_cookie_name()]
        client.post(REFRESH)
        client.cookies.clear()
        client.cookies.set(refresh_cookie_name(), old_cookie, path="/api/v1/auth")
        response = client.post(REFRESH)
        assert response.status_code == 409 and response.json()["error"]["code"] == "refresh_in_progress"
        assert "set-cookie" not in response.headers

    def test_refresh_reuse_after_grace_revokes_session(self, client, make_admin, db):
        user = make_admin()
        login(client, user)
        old_cookie = client.cookies[refresh_cookie_name()]
        access = client.post(REFRESH).json()["access_token"]
        db.execute(text(
            f"""UPDATE "{SCHEMA}".refresh_tokens SET used_at = now() - interval '1 hour'
                WHERE used_at IS NOT NULL"""))
        db.commit()
        client.cookies.clear()
        client.cookies.set(refresh_cookie_name(), old_cookie, path="/api/v1/auth")
        assert client.post(REFRESH).status_code == 401
        assert client.get(ME, headers={"Authorization": f"Bearer {access}"}).status_code == 401
        assert "REFRESH_TOKEN_REUSE" in _actions(db)

    def test_tokens_are_stored_only_as_hashes(self, client, make_admin, db):
        user = make_admin()
        token = login(client, user).json()["access_token"]
        session = db.scalar(select(UserSession).where(UserSession.user_id == user.id))
        assert session.access_token_hash == hash_token(token) != token
        raw = db.execute(text(
            f"""SELECT token_hash FROM "{SCHEMA}".refresh_tokens""")).scalars().all()
        assert client.cookies[refresh_cookie_name()] not in raw

    def test_session_list_and_revocation(self, client, make_admin):
        user = make_admin()
        first = auth_headers(client, user)
        second = auth_headers(client, user)
        sessions = client.get("/api/v1/auth/sessions", headers=second).json()
        assert len(sessions) == 2 and sum(item["current"] for item in sessions) == 1
        other = next(item for item in sessions if not item["current"])
        assert client.delete(f"/api/v1/auth/sessions/{other['id']}", headers=second).status_code == 204
        assert client.get(ME, headers=first).status_code == 401
        assert client.get(ME, headers=second).status_code == 200

    def test_cannot_revoke_someone_elses_session(self, client, make_admin, db):
        victim, attacker = make_admin(), make_admin()
        login(client, victim)
        session = db.scalar(select(UserSession).where(UserSession.user_id == victim.id))
        headers = auth_headers(client, attacker)
        assert client.delete(f"/api/v1/auth/sessions/{session.id}", headers=headers).status_code == 404

    def test_revoke_others(self, client, make_admin):
        user = make_admin()
        first, second = auth_headers(client, user), auth_headers(client, user)
        assert client.post("/api/v1/auth/sessions/revoke-others", headers=second).json() == {"revoked": 1}
        assert client.get(ME, headers=first).status_code == 401


class TestPasswords:
    def test_change_password(self, client, make_admin, db):
        user = make_admin()
        other = auth_headers(client, user)
        current = auth_headers(client, user)
        response = client.post("/api/v1/auth/password/change", headers=current, json={
            "current_password": PASSWORD, "new_password": "a-brand-new-passphrase"})
        assert response.status_code == 204
        assert client.get(ME, headers=other).status_code == 401
        assert client.get(ME, headers=current).status_code == 200
        assert login(client, user).status_code == 401
        assert login(client, user, "a-brand-new-passphrase").status_code == 200
        assert "PASSWORD_CHANGED" in _actions(db)

    def test_change_requires_current_password_and_policy(self, client, make_admin):
        user = make_admin()
        headers = auth_headers(client, user)
        assert client.post("/api/v1/auth/password/change", headers=headers, json={
            "current_password": "wrong-password-123", "new_password": "a-brand-new-passphrase"
        }).status_code == 401
        assert client.post("/api/v1/auth/password/change", headers=headers, json={
            "current_password": PASSWORD, "new_password": "short"}).status_code == 422

    def test_must_change_password_restricts_access_until_changed(self, client, make_admin):
        user = make_admin(must_change_password=True)
        headers = auth_headers(client, user)
        assert client.get(ME, headers=headers).status_code == 200
        blocked = client.get("/api/v1/auth/sessions", headers=headers)
        assert blocked.status_code == 403
        assert blocked.json()["error"]["code"] == "password_change_required"
        client.post("/api/v1/auth/password/change", headers=headers, json={
            "current_password": PASSWORD, "new_password": "a-brand-new-passphrase"})
        assert client.get("/api/v1/auth/sessions", headers=headers).status_code == 200

    def test_reset_is_silent_and_creates_nothing_without_delivery(self, client, make_admin, db):
        user = make_admin()
        for email in (user.email, "ghost@example.com"):
            response = client.post("/api/v1/auth/password/reset/request", json={"email": email})
            assert response.status_code == 202 and response.json() == {"status": "accepted"}
        assert db.scalars(select(PasswordResetToken)).all() == []

    def test_reset_flow_with_delivery(self, client, make_admin, db):
        from app.main import app

        sent = []

        class Fake:
            enabled = True

            def send(self, email, token):
                sent.append((email, token))

        app.dependency_overrides[get_password_reset_delivery] = lambda: Fake()
        try:
            user = make_admin()
            headers = auth_headers(client, user)
            client.post("/api/v1/auth/password/reset/request", json={"email": user.email})
            client.post("/api/v1/auth/password/reset/request", json={"email": "ghost@example.com"})
        finally:
            app.dependency_overrides.clear()
        assert len(sent) == 1
        token = sent[0][1]
        stored = db.scalars(select(PasswordResetToken.token_hash)).one()
        assert stored == hash_token(token) != token
        confirm = "/api/v1/auth/password/reset/confirm"
        new = {"token": token, "new_password": "a-brand-new-passphrase"}
        assert client.post(confirm, json=new).status_code == 204
        assert client.get(ME, headers=headers).status_code == 401
        assert login(client, user, "a-brand-new-passphrase").status_code == 200
        assert client.post(confirm, json=new).status_code == 400


class TestSuperAdminCli:
    def test_creates_superadmin_with_argon2id_and_audit(self, db):
        user = create_superadmin(db, "root@example.com", "root", PASSWORD)
        assert user.is_superuser and user.password_hash.startswith("$argon2id$")
        assert PASSWORD not in user.password_hash
        assert "SUPER_ADMIN_CREATED" in _actions(db)

    def test_refuses_second_unless_explicit(self, db):
        create_superadmin(db, "root@example.com", "root", PASSWORD)
        with pytest.raises(SuperAdminAlreadyExists):
            create_superadmin(db, "two@example.com", "two", PASSWORD)
        assert create_superadmin(db, "two@example.com", "two", PASSWORD, additional=True)

    def test_rejects_weak_password(self, db):
        from app.core.security import WeakPassword

        with pytest.raises(WeakPassword):
            create_superadmin(db, "root@example.com", "root", "short")

    def test_last_superadmin_cannot_be_demoted(self, db, make_admin):
        user = make_admin(is_superuser=True)
        with pytest.raises(LastSuperAdmin):
            set_superadmin(db, user.email, grant=False)
        other = make_admin(is_superuser=True)
        set_superadmin(db, user.email, grant=False)
        db.expire_all()
        assert not db.get(AdminUser, user.id).is_superuser
        assert db.get(AdminUser, other.id).is_superuser


def test_no_public_registration_or_superadmin_endpoint():
    from app.main import app

    paths = set(app.openapi()["paths"])
    assert not any("register" in path or "superadmin" in path for path in paths)
