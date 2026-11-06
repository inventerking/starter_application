"""Re-encrypts stored MFA secrets under the current key.

Rotation procedure:
1. Move the old key into MFA_ENCRYPTION_PREVIOUS_KEYS as ``old_id:old_key``.
2. Set a new MFA_ENCRYPTION_KEY and MFA_ENCRYPTION_KEY_ID, then restart.
3. Run: uv run python -m app.cli.rotate_mfa_key
4. Remove the old key from MFA_ENCRYPTION_PREVIOUS_KEYS.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import get_mfa_cipher
from app.core.database import SessionLocal
from app.models_registry import *  # noqa: F403
from app.modules.admins.models import AdminUser
from app.modules.mfa.service import secret_owner


def rotate(db: Session) -> int:
    cipher = get_mfa_cipher()
    users = db.scalars(
        select(AdminUser)
        .where(AdminUser.mfa_secret_encrypted.is_not(None),
               AdminUser.mfa_key_id != cipher.key_id)
        .with_for_update()).all()
    for user in users:
        owner = secret_owner(user.id)
        user.mfa_secret_encrypted = cipher.encrypt(
            cipher.decrypt(user.mfa_secret_encrypted, owner), owner)
        user.mfa_key_id = cipher.key_id
    db.commit()
    return len(users)


if __name__ == "__main__":
    with SessionLocal() as session:
        print(f"Re-encrypted {rotate(session)} secret(s).")
