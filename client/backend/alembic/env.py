"""Migration environment. It manages this domain's schema only and ignores all other schemas."""

from sqlalchemy import create_engine, text

from alembic import context
from app import models_registry  # noqa: F401
from app.core.config import get_settings
from app.core.database import SCHEMA, Base

target_metadata = Base.metadata


def _include_name(name, type_, parent_names):
    # Autogenerate must never see, and therefore never drop, another domain's tables.
    if type_ == "schema":
        return name == SCHEMA
    return True


def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url)
    with engine.connect() as connection:
        connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=_include_name,
            version_table="alembic_version",
            version_table_schema=SCHEMA,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported.")
run_migrations_online()
