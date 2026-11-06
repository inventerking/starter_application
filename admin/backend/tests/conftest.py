"""Tests run against throwaway schemas inside starter_app; no other database is created."""

import base64
import os
import uuid

_run_id = uuid.uuid4().hex[:10]
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_SCHEMA"] = f"test_admin_{_run_id}"
os.environ["CLIENT_DATABASE_SCHEMA"] = f"test_client_{_run_id}"
os.environ["MFA_ENCRYPTION_KEY"] = base64.urlsafe_b64encode(os.urandom(32)).decode()
os.environ["MFA_ENCRYPTION_KEY_ID"] = "k1"
os.environ["COOKIE_SECURE"] = "false"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"
os.environ["ARGON2_TIME_COST"] = "1"
os.environ["ARGON2_MEMORY_COST_KIB"] = "64"
os.environ["ARGON2_PARALLELISM"] = "1"
os.environ["LOG_LEVEL"] = "WARNING"

import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
CLIENT_BACKEND_DIR = BACKEND_DIR.parents[1] / "client" / "backend"


def run_alembic(cwd: Path, schema: str, *args: str) -> None:
    """Run a backend's own Alembic environment in its own uv environment."""
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["DATABASE_SCHEMA"] = schema
    subprocess.run(["uv", "run", "-q", "alembic", *args], cwd=cwd, env=env, check=True,
                   capture_output=True)


@pytest.fixture(scope="session", autouse=True)
def _test_schemas():
    from sqlalchemy import text

    from app.core.config import get_settings
    from app.core.database import SCHEMA, engine

    client_schema = get_settings().client_database_schema
    try:
        run_alembic(BACKEND_DIR, SCHEMA, "upgrade", "head")
        run_alembic(CLIENT_BACKEND_DIR, client_schema, "upgrade", "head")
        yield
    finally:
        engine.dispose()
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'))
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{client_schema}" CASCADE'))
        engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables():
    """Every test starts from empty domain tables."""
    yield
    from sqlalchemy import text

    from app.core.config import get_settings
    from app.core.database import SCHEMA, engine

    for schema, keep in ((SCHEMA, "alembic_version"),
                         (get_settings().client_database_schema, "alembic_version")):
        with engine.begin() as connection:
            names = connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = :s AND tablename <> :k"),
                {"s": schema, "k": keep},
            ).scalars().all()
            if names:
                joined = ", ".join(f'"{schema}"."{name}"' for name in names)
                connection.execute(text(f"TRUNCATE {joined} CASCADE"))
