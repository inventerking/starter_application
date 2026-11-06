"""Tests run against throwaway schemas inside starter_app; no other database is created."""

import base64
import os
import uuid

_run_id = uuid.uuid4().hex[:10]
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_SCHEMA"] = f"test_client_{_run_id}"
os.environ["MFA_ENCRYPTION_KEY"] = base64.urlsafe_b64encode(os.urandom(32)).decode()
os.environ["MFA_ENCRYPTION_KEY_ID"] = "k1"
os.environ["COOKIE_SECURE"] = "false"
os.environ["CORS_ORIGINS"] = "http://localhost:5174"
os.environ["ARGON2_TIME_COST"] = "1"
os.environ["ARGON2_MEMORY_COST_KIB"] = "64"
os.environ["ARGON2_PARALLELISM"] = "1"
os.environ["LOG_LEVEL"] = "WARNING"

import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]


def run_alembic(cwd: Path, schema: str, *args: str) -> None:
    """Run a backend's own Alembic environment in its own uv environment."""
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["DATABASE_SCHEMA"] = schema
    subprocess.run(["uv", "run", "-q", "alembic", *args], cwd=cwd, env=env, check=True,
                   capture_output=True)


@pytest.fixture(scope="session", autouse=True)
def _test_schemas():
    from sqlalchemy import text

    from app.core.database import SCHEMA, engine
    try:
        run_alembic(BACKEND_DIR, SCHEMA, "upgrade", "head")
        yield
    finally:
        engine.dispose()
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'))
        engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables():
    """Every test starts from empty domain tables."""
    yield
    from sqlalchemy import text

    from app.core.database import SCHEMA, engine

    with engine.begin() as connection:
        names = connection.execute(
            text("SELECT tablename FROM pg_tables "
                 "WHERE schemaname = :s AND tablename <> 'alembic_version'"),
            {"s": SCHEMA},
        ).scalars().all()
        if names:
            joined = ", ".join(f'"{SCHEMA}"."{name}"' for name in names)
            connection.execute(text(f"TRUNCATE {joined} CASCADE"))


ORIGIN_HEADERS = {"Origin": "http://localhost:5174", "X-Requested-With": "starter-app"}
PASSWORD = "correct-horse-battery-staple"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app, headers=ORIGIN_HEADERS) as test_client:
        yield test_client


@pytest.fixture
def db():
    from app.core.database import SessionLocal

    with SessionLocal() as session:
        yield session


@pytest.fixture
def make_user(db):
    from app.core.security import get_password_service
    from app.modules.users.models import User

    counter = iter(range(1, 10_000))

    def _make(**overrides) -> User:
        number = next(counter)
        values = {
            "email": f"user{number}@example.com",
            "username": f"user{number}",
            "password_hash": get_password_service().hash(overrides.pop("password", PASSWORD)),
        }
        user = User(**(values | overrides))
        db.add(user)
        db.commit()
        return user

    return _make


@pytest.fixture
def permissions(db):
    """Synchronize the registry and return a {code: Permission} map."""
    from app.modules.permissions.repository import PermissionRepository
    from app.modules.permissions.service import PermissionService

    PermissionService(db).sync_registry()
    db.commit()
    return {row.code: row for row in PermissionRepository(db).list_all()}


def login(client, user, password=PASSWORD) -> dict:
    return client.post("/api/v1/auth/login",
                       json={"identifier": user.email, "password": password})


def auth_headers(client, user, password=PASSWORD) -> dict:
    return {"Authorization": f"Bearer {login(client, user, password).json()['access_token']}"}


def totp_code(secret: str, offset_steps: int = 0) -> str:
    import time

    import pyotp

    return pyotp.TOTP(secret).at(int(time.time()) + offset_steps * 30)


def enroll_mfa(client, headers, password=PASSWORD) -> tuple[str, list[str]]:
    """Run setup and confirmation. Returns the secret and the recovery codes."""
    secret = client.post("/api/v1/auth/mfa/setup", headers=headers,
                         json={"password": password}).json()["secret"]
    body = client.post("/api/v1/auth/mfa/confirm", headers=headers,
                       json={"code": totp_code(secret)}).json()
    return secret, body["recovery_codes"]
