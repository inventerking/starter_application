import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app


def _settings(**overrides):
    base = {
        "database_password": "x",
        "mfa_encryption_key": "A" * 43,
        "_env_file": None,
    }
    return Settings(**(base | overrides))


def test_liveness_and_security_headers():
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"


def test_readiness_reaches_database():
    assert TestClient(app).get("/api/v1/health/ready").json() == {"status": "ready"}


def test_unknown_route_uses_safe_error_shape():
    body = TestClient(app).get("/api/v1/nope").json()
    assert body["error"]["code"] == "not_found"


def test_unhandled_exception_is_not_exposed():
    from fastapi import FastAPI

    from app.core.exceptions import register_exception_handlers

    probe = FastAPI()
    register_exception_handlers(probe)

    @probe.get("/boom")
    def boom():
        raise RuntimeError("password=hunter2 leaked")

    response = TestClient(probe, raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500
    assert "hunter2" not in response.text


@pytest.mark.parametrize("bad_key", ["REPLACE_WITH_SECURE_KEY", "short", ""])
def test_invalid_mfa_key_fails_startup(bad_key):
    with pytest.raises(ValidationError):
        _settings(mfa_encryption_key=bad_key)


def test_mfa_title_rejects_colon():
    with pytest.raises(ValidationError):
        _settings(mfa_title="Bad:Title")


def test_production_requires_secure_cookies():
    with pytest.raises(ValidationError):
        _settings(environment="production", cookie_secure=False)


def test_docs_disabled_in_production():
    assert _settings(environment="production", cookie_secure=True).docs_enabled is False


def test_database_url_supports_environment_host():
    assert _settings(database_host="postgres").database_url.host == "postgres"


def test_password_is_hidden_in_settings_repr():
    assert "hunter2" not in repr(_settings(database_password="hunter2"))
