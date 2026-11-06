"""Synchronizes the Client permission registry and seeds a default role on first run.

Usage: uv run python -m app.cli.sync_permissions
"""

from app.core.database import SessionLocal
from app.models_registry import *  # noqa: F403
from app.modules.permissions.service import PermissionService


def main() -> None:
    with SessionLocal() as db:
        service = PermissionService(db)
        result = service.sync_registry()
        service.ensure_default_role()
        db.commit()
    print(f"Added {result.added}, updated {result.updated}, deprecated {result.deprecated}.")


if __name__ == "__main__":
    main()
