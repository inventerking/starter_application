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
