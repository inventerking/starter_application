"""Grants or revokes Super Admin status. Deliberately not available through any API.

Usage: uv run python -m app.cli.set_superadmin --email a@example.com (--grant | --revoke)
"""

import argparse
import sys

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models_registry import *  # noqa: F403
from app.modules.admins.repository import AdminRepository
from app.modules.audit.actions import AuditAction
from app.modules.audit.service import ACTOR_SYSTEM, AuditService
from app.modules.authentication.session_service import SessionService


class LastSuperAdmin(Exception):
    pass


def set_superadmin(db: Session, email: str, *, grant: bool) -> None:
    repository = AdminRepository(db)
    user = repository.get_by_identifier(email)
    if user is None:
        raise LookupError("No Admin account has that email.")
    if not grant and repository.count_active_superusers(excluding=user.id) == 0:
        raise LastSuperAdmin("The last active Super Admin cannot be demoted.")
    user.is_superuser = grant
    SessionService(db).revoke_all(user.id, "superuser_status_changed")
    action = AuditAction.SUPER_ADMIN_GRANTED if grant else AuditAction.SUPER_ADMIN_REVOKED
    AuditService(db).record(action, actor_type=ACTOR_SYSTEM, target_type="admin",
                            target_id=user.id, details={"via": "cli"})
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--grant", action="store_true")
    group.add_argument("--revoke", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        try:
            set_superadmin(db, args.email, grant=args.grant)
        except (LookupError, LastSuperAdmin) as exc:
            sys.exit(str(exc))
    print("Done.")


if __name__ == "__main__":
    main()
