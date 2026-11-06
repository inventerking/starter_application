"""Creates the first Super Admin. This is the only way to create one; no API endpoint exists.

Usage: uv run python -m app.cli.create_superadmin [--additional]
"""

import argparse
import getpass
import sys

from pydantic import BaseModel, EmailStr, Field, ValidationError
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import SCHEMA, SessionLocal, engine
from app.core.exceptions import AppError
from app.core.security import get_password_service
from app.models_registry import *  # noqa: F403 - registers every model and foreign key target
from app.modules.admins.models import AdminUser
from app.modules.admins.repository import AdminRepository
from app.modules.audit.actions import AuditAction
from app.modules.audit.service import ACTOR_SYSTEM, AuditService


class SuperAdminAlreadyExists(Exception):
    pass


class SuperAdminIdentity(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")


def create_superadmin(
    db: Session, email: str, username: str, password: str, *, additional: bool = False
) -> AdminUser:
    identity = SuperAdminIdentity(email=email, username=username)
    repository = AdminRepository(db)
    passwords = get_password_service()
    if repository.count_active_superusers() > 0 and not additional:
        raise SuperAdminAlreadyExists
    if repository.email_taken(identity.email) or repository.username_taken(identity.username):
        raise ValueError("That email or username is already in use.")
    passwords.validate_policy(password, forbidden=(identity.email, identity.username))
    user = repository.add(AdminUser(
        email=identity.email, username=identity.username,
        password_hash=passwords.hash(password), is_superuser=True))
    AuditService(db).record(
        AuditAction.SUPER_ADMIN_CREATED, actor_type=ACTOR_SYSTEM,
        target_type="admin", target_id=user.id, details={"via": "cli"})
    db.commit()
    return user


def _preflight() -> None:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            if not inspect(connection).has_table("users", schema=SCHEMA):
                sys.exit(f"The '{SCHEMA}' schema is not migrated. Run: uv run alembic upgrade head")
    except SQLAlchemyError:
        sys.exit("Could not connect to the database. Check the DATABASE_* settings.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--additional", action="store_true",
                        help="Allow creation when a Super Admin already exists.")
    args = parser.parse_args()
    _preflight()
    with SessionLocal() as db:
        if AdminRepository(db).count_active_superusers() > 0 and not args.additional:
            sys.exit("A Super Admin already exists. Use --additional to create another.")
    email = input("Email: ").strip()
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Confirm password: "):
        sys.exit("The passwords do not match.")
    with SessionLocal() as db:
        try:
            user = create_superadmin(db, email, username, password, additional=args.additional)
        except ValidationError:
            sys.exit("The email or username is invalid.")
        except (ValueError, AppError) as exc:
            sys.exit(str(exc))
    print(f"Super Admin created: {user.email}")


if __name__ == "__main__":
    main()
