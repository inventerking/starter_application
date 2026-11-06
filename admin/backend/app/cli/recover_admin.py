"""Break-glass account recovery for operators with server access. No API offers this.

A sole Super Admin who loses their authenticator or password would otherwise be locked out, because
only a Super Admin can reset a Super Admin. Every use is recorded in the audit log.

Usage: uv run python -m app.cli.recover_admin --email a@example.com [--mfa] [--password]
"""

import argparse
import getpass
import sys

from sqlalchemy.orm import Session

from app.core.database import SessionLocal, utcnow
from app.core.exceptions import AppError
from app.core.security import get_password_service
from app.models_registry import *  # noqa: F403
from app.modules.admins.models import AdminUser
from app.modules.admins.repository import AdminRepository
from app.modules.audit.actions import AuditAction
from app.modules.audit.service import ACTOR_SYSTEM, AuditService
from app.modules.authentication.session_service import SessionService
from app.modules.mfa.repository import MfaRepository


def _find(db: Session, email: str) -> AdminUser:
    user = AdminRepository(db).get_by_identifier(email)
    if user is None:
        raise LookupError("No Admin account has that email.")
    return user


def recover_mfa(db: Session, email: str) -> None:
    """Clears MFA and requires new enrollment at the next sign-in."""
    user = _find(db, email)
    now = utcnow()
    user.mfa_enabled = False
    user.mfa_enrollment_required = True
    user.mfa_secret_encrypted = None
    user.mfa_key_id = None
    user.mfa_confirmed_at = None
    user.mfa_last_used_step = None
    user.failed_login_count = 0
    user.locked_until = None
    repository = MfaRepository(db)
    repository.delete_recovery_codes(user.id)
    repository.invalidate_challenges(user.id, now)
    SessionService(db).revoke_all(user.id, "cli_recovery")
    AuditService(db).record(AuditAction.MFA_RESET, actor_type=ACTOR_SYSTEM, target_type="admin",
                            target_id=user.id, details={"via": "cli"})
    db.commit()


def recover_password(db: Session, email: str, new_password: str) -> None:
    user = _find(db, email)
    passwords = get_password_service()
    passwords.validate_policy(new_password, forbidden=(user.email, user.username))
    user.password_hash = passwords.hash(new_password)
    user.password_changed_at = utcnow()
    user.must_change_password = False
    user.failed_login_count = 0
    user.locked_until = None
    SessionService(db).revoke_all(user.id, "cli_recovery")
    AuditService(db).record(AuditAction.PASSWORD_RESET_COMPLETED, actor_type=ACTOR_SYSTEM,
                            target_type="admin", target_id=user.id, details={"via": "cli"})
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--mfa", action="store_true", help="Clear MFA and require re-enrollment.")
    parser.add_argument("--password", action="store_true", help="Set a new password.")
    args = parser.parse_args()
    if not (args.mfa or args.password):
        parser.error("Choose --mfa, --password, or both.")
    with SessionLocal() as db:
        try:
            if args.password:
                new_password = getpass.getpass("New password: ")
                if new_password != getpass.getpass("Confirm new password: "):
                    sys.exit("The passwords do not match.")
                recover_password(db, args.email, new_password)
            if args.mfa:
                recover_mfa(db, args.email)
        except (LookupError, AppError) as exc:
            sys.exit(str(exc))
    print("Done.")


if __name__ == "__main__":
    main()
