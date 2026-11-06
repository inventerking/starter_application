"""Sweeps over every route and the boundary with the Admin domain."""

import ast
import uuid
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from app.cli.cleanup_expired import cleanup
from app.core.database import engine, utcnow
from app.main import app
from app.modules.mfa.models import MfaChallenge
from tests.conftest import auth_headers, login

APP_DIR = Path(__file__).resolve().parents[1] / "app"
PUBLIC = {
    ("get", "/api/v1/health"),
    ("get", "/api/v1/health/ready"),
    ("post", "/api/v1/auth/login"),
    ("post", "/api/v1/auth/register"),
    ("post", "/api/v1/auth/refresh"),
    ("post", "/api/v1/auth/logout"),
    ("post", "/api/v1/auth/mfa/verify-login"),
    ("post", "/api/v1/auth/password/reset/request"),
    ("post", "/api/v1/auth/password/reset/confirm"),
}
PERMISSION_GUARDED = {("get", "/api/v1/users/me"), ("patch", "/api/v1/users/me"),
                      ("get", "/api/v1/users/me/activity")}


def _call(client, method, path, **kwargs):
    return client.request(method.upper(), path.replace("{session_id}", str(uuid.uuid4())), **kwargs)


def _routes():
    for path, methods in app.openapi()["paths"].items():
        for method in methods:
            yield method, path


def test_every_non_public_route_rejects_anonymous_requests(client):
    checked = 0
    for method, path in _routes():
        if (method, path) in PUBLIC:
            continue
        assert _call(client, method, path, json={}).status_code == 401, f"{method} {path}"
        checked += 1
    assert checked >= 15


def test_permission_guarded_routes_reject_a_user_without_permissions(client, make_user, permissions):
    headers = auth_headers(client, make_user())
    for method, path in PERMISSION_GUARDED:
        assert _call(client, method, path, headers=headers, json={}).status_code == 403, path


def test_responses_never_expose_sensitive_field_names():
    forbidden = {"password_hash", "mfa_secret_encrypted", "code_hash", "token_hash", "mfa_key_id"}
    for name, schema in app.openapi()["components"]["schemas"].items():
        assert not forbidden & set(schema.get("properties", {})), name


def test_no_management_api_exists_here():
    """Administering users belongs to the Admin control plane, not this application."""
    paths = set(app.openapi()["paths"])
    assert not any("admin" in path for path in paths)
    assert not any(path.startswith("/api/v1/users/{") for path in paths)
    assert "/api/v1/roles" not in paths


def test_client_backend_imports_nothing_from_the_admin_backend():
    for path in APP_DIR.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(("admin.", "app.modules.admins")), path


def test_engine_hides_bound_parameters():
    assert engine.hide_parameters is True


def test_cleanup_removes_only_expired_records(client, make_user, db):
    user = make_user()
    login(client, user)
    db.add(MfaChallenge(user_id=user.id, token_hash="old", expires_at=utcnow() - timedelta(minutes=1)))
    db.add(MfaChallenge(user_id=user.id, token_hash="new", expires_at=utcnow() + timedelta(minutes=1)))
    db.commit()
    assert cleanup(db)["mfa_challenges"] == 1
    db.expire_all()
    assert db.scalars(select(MfaChallenge.token_hash)).all() == ["new"]
