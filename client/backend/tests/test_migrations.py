"""Schema isolation: each Alembic environment manages its own schema and nothing else."""

import uuid

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError

from app import models_registry  # noqa: F401
from app.core.database import SCHEMA, Base, engine
from tests.conftest import BACKEND_DIR, run_alembic

EXPECTED_TABLES = {
    "users", "roles", "permissions", "user_roles", "role_permissions", "user_permissions",
    "sessions", "refresh_tokens", "mfa_challenges", "mfa_recovery_codes",
    "password_reset_tokens", "rate_limit_counters", "audit_logs", "alembic_version",
}
# A sentinel schema stands in for the other domain, which this project knows nothing about.
OTHER_SCHEMA = "test_other_domain"


def _tables(schema):
    with engine.connect() as connection:
        return set(inspect(connection).get_table_names(schema=schema))


def test_migrations_create_exactly_the_expected_tables():
    assert _tables(SCHEMA) == EXPECTED_TABLES


def test_models_match_migrations():
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={
            "include_schemas": True,
            "version_table_schema": SCHEMA,
            "include_name": lambda name, type_, _: name == SCHEMA if type_ == "schema" else True,
        })
        assert compare_metadata(context, Base.metadata) == []


def test_metadata_only_contains_this_domain():
    assert {table.schema for table in Base.metadata.tables.values()} == {SCHEMA}


def test_foreign_keys_stay_inside_the_schema():
    with engine.connect() as connection:
        inspector = inspect(connection)
        for table in inspector.get_table_names(schema=SCHEMA):
            for fk in inspector.get_foreign_keys(table, schema=SCHEMA):
                assert fk["referred_schema"] in (None, SCHEMA)


def test_migrating_this_domain_does_not_touch_the_other_schema():
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{OTHER_SCHEMA}"'))
        connection.execute(text(f'CREATE TABLE IF NOT EXISTS "{OTHER_SCHEMA}".users (id int)'))
    before = _tables(OTHER_SCHEMA)
    scratch = f"test_scratch_{uuid.uuid4().hex[:8]}"
    try:
        run_alembic(BACKEND_DIR, scratch, "upgrade", "head")
        assert _tables(scratch) == EXPECTED_TABLES
        assert _tables(OTHER_SCHEMA) == before
        run_alembic(BACKEND_DIR, scratch, "downgrade", "base")
        assert _tables(scratch) == {"alembic_version"}
        assert _tables(OTHER_SCHEMA) == before
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{scratch}" CASCADE'))
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{OTHER_SCHEMA}" CASCADE'))


def test_audit_logs_are_append_only():
    log_id = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(f"""INSERT INTO "{SCHEMA}".audit_logs (id, action, actor_type, details)
                     VALUES (:id, 'TEST', 'system', '{{}}')"""),
            {"id": log_id},
        )
    for statement in (
        f"""UPDATE "{SCHEMA}".audit_logs SET action = 'X' WHERE id = :id""",
        f"""DELETE FROM "{SCHEMA}".audit_logs WHERE id = :id""",
    ):
        with pytest.raises(DBAPIError, match="append-only"), engine.begin() as connection:
            connection.execute(text(statement), {"id": log_id})
