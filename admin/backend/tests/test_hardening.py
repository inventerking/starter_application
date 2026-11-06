"""Sweeps over every route and every module boundary, so new code cannot silently skip a rule."""

import ast
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.cli.cleanup_expired import cleanup
from app.cli.recover_admin import recover_mfa, recover_password
from app.core.config import Settings
from app.core.database import engine, utcnow
from app.main import app
from app.modules.admins.models import AdminUser
from app.modules.audit.models import AuditLog
from app.modules.authentication.models import UserSession
from app.modules.mfa.models import MfaChallenge
from tests.conftest import PASSWORD, auth_headers, enroll_mfa, login

APP_DIR = Path(__file__).resolve().parents[1] / "app"
PUBLIC = {
    ("get", "/api/v1/health"),
    ("get", "/api/v1/health/ready"),
    ("post", "/api/v1/auth/login"),
    ("post", "/api/v1/auth/refresh"),
    ("post", "/api/v1/auth/logout"),
    ("post", "/api/v1/auth/mfa/verify-login"),
    ("post", "/api/v1/auth/password/reset/request"),
    ("post", "/api/v1/auth/password/reset/confirm"),
}
SELF_SERVICE_PREFIXES = ("/api/v1/auth/", "/api/v1/dashboard/")


def _routes():
    for path, methods in app.openapi()["paths"].items():
        for method in methods:
            yield method, path


def _call(client, method, path, **kwargs):
    url = path
    for parameter in ("admin_id", "user_id", "role_id", "permission_id", "session_id"):
        url = url.replace(f"{{{parameter}}}", str(uuid.uuid4()))
    return client.request(method.upper(), url, **kwargs)


class TestRouteSweep:
    def test_every_non_public_route_rejects_anonymous_requests(self, client):
        checked = 0
        for method, path in _routes():
            if (method, path) in PUBLIC:
                continue
            response = _call(client, method, path, json={})
            assert response.status_code == 401, f"{method} {path} -> {response.status_code}"
            checked += 1
        assert checked > 50

    def test_every_management_route_rejects_an_admin_without_permissions(self, client, make_admin, permissions):
        headers = auth_headers(client, make_admin())
        checked = 0
        for method, path in _routes():
            if (method, path) in PUBLIC or path.startswith(SELF_SERVICE_PREFIXES):
                continue
            response = _call(client, method, path, headers=headers, json={})
            assert response.status_code == 403, f"{method} {path} -> {response.status_code}"
            checked += 1
        assert checked > 40

    def test_management_routes_are_blocked_during_forced_mfa_enrollment(self, client, make_admin, permissions):
        user = make_admin(is_superuser=True, mfa_enrollment_required=True)
        body = login(client, user).json()
        assert body["status"] == "mfa_enrollment_required"
        headers = {"Authorization": f"Bearer {body['access_token']}"}
        for path in ("/api/v1/admins", "/api/v1/users", "/api/v1/audit-logs", "/api/v1/dashboard/summary"):
            assert client.get(path, headers=headers).status_code == 403

    def test_responses_never_expose_sensitive_field_names(self):
        forbidden = {"password_hash", "mfa_secret_encrypted", "code_hash", "token_hash",
                     "access_token_hash", "mfa_key_id"}
        for name, schema in app.openapi()["components"]["schemas"].items():
            assert not forbidden & set(schema.get("properties", {})), name


def _imports(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


class TestModuleBoundaries:
    def test_only_user_management_code_may_reach_the_client_schema(self):
        allowed = {"users", "client_domain", "client_roles", "dashboard"}
        for path in (APP_DIR / "modules").rglob("*.py"):
            module = path.relative_to(APP_DIR / "modules").parts[0]
            if module in allowed:
                continue
            assert not any("client_domain" in item or "modules.users" in item or "client_roles" in item
                           for item in _imports(path) if not item.endswith("catalog")) or path.name == "catalog.py", path

    def test_admin_management_does_not_import_user_management(self):
        for path in (APP_DIR / "modules" / "admins").rglob("*.py"):
            assert not any("modules.users" in item or "client" in item for item in _imports(path)), path

    def test_user_management_does_not_use_admin_management_services(self):
        for folder in ("users", "client_roles", "client_domain"):
            for path in (APP_DIR / "modules" / folder).rglob("*.py"):
                for item in _imports(path):
                    assert item not in {"app.modules.admins.service", "app.modules.roles.service",
                                        "app.modules.roles.models", "app.modules.permissions.models"}, path

    def test_routes_build_no_database_queries(self):
        builders = {"select", "insert", "update", "delete", "text"}
        for path in (APP_DIR / "modules").rglob("routes.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("sqlalchemy"):
                    assert not builders & {alias.name for alias in node.names}, path

    def test_admin_backend_has_no_client_mfa_key_setting(self):
        assert not [field for field in Settings.model_fields if "client" in field and "key" in field]

    def test_no_client_backend_code_is_imported(self):
        for path in APP_DIR.rglob("*.py"):
            assert not any(item.startswith("client.") for item in _imports(path)), path


class TestIdentityIsolation:
    def test_client_credentials_cannot_sign_in_to_admin(self, client, make_client_user):
        user = make_client_user()
        response = client.post("/api/v1/auth/login", json={"identifier": user.email, "password": PASSWORD})
        assert response.status_code == 401

    def test_same_email_in_both_domains_uses_only_the_admin_record(self, client, make_admin, make_client_user):
        admin = make_admin(password="admin-side-passphrase-1")
        make_client_user(email=admin.email, username=admin.username)
        assert login(client, admin, PASSWORD).status_code == 401
        assert login(client, admin, "admin-side-passphrase-1").status_code == 200


class TestSecretsStayOutOfLogs:
    def test_engine_hides_bound_parameters(self):
        assert engine.hide_parameters is True

    def test_failed_statement_does_not_print_values(self, db):
        with pytest.raises(Exception) as caught:
            db.add(AdminUser(email="a@example.com", username="u", password_hash="SECRET-VALUE",
                             id=uuid.uuid4(), full_name="x" * 500))
            db.commit()
        db.rollback()
        assert "SECRET-VALUE" not in str(caught.value)


class TestRecoveryCli:
    def test_mfa_recovery_requires_new_enrollment_and_is_audited(self, client, make_admin, db):
        user = make_admin(is_superuser=True)
        enroll_mfa(client, auth_headers(client, user))
        db.expire_all()
        recover_mfa(db, user.email)
        db.expire_all()
        stored = db.get(AdminUser, user.id)
        assert not stored.mfa_enabled and stored.mfa_secret_encrypted is None
        assert login(client, user).json()["status"] == "mfa_enrollment_required"
        entry = db.scalar(select(AuditLog).where(AuditLog.action == "MFA_RESET"))
        assert entry.actor_type == "system" and entry.details["via"] == "cli"

    def test_password_recovery_revokes_sessions_and_clears_lockout(self, client, make_admin, db):
        user = make_admin(is_superuser=True, locked_until=utcnow() + timedelta(hours=1))
        recover_password(db, user.email, "a-brand-new-passphrase")
        assert login(client, user, "a-brand-new-passphrase").status_code == 200

    def test_unknown_email(self, db):
        with pytest.raises(LookupError):
            recover_mfa(db, "ghost@example.com")


def test_cleanup_removes_only_expired_records(client, make_admin, db):
    user = make_admin()
    login(client, user)
    db.add(MfaChallenge(user_id=user.id, token_hash="old", expires_at=utcnow() - timedelta(minutes=1)))
    db.add(MfaChallenge(user_id=user.id, token_hash="new", expires_at=utcnow() + timedelta(minutes=1)))
    db.commit()
    counts = cleanup(db)
    assert counts["mfa_challenges"] == 1 and counts["sessions"] == 0
    db.expire_all()
    assert db.scalars(select(MfaChallenge.token_hash)).all() == ["new"]
    assert db.scalars(select(UserSession)).first() is not None
