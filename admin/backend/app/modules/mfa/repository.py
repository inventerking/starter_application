"""Persistence for MFA challenges and recovery codes."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.modules.admins.models import AdminUser
from app.modules.mfa.models import MfaChallenge, MfaRecoveryCode


class MfaRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create_challenge(
        self, user_id: UUID, token_hash: str, expires_at: datetime, ip_address: str | None
    ) -> None:
        self._db.add(MfaChallenge(user_id=user_id, token_hash=token_hash, expires_at=expires_at,
                                  ip_address=ip_address))

    def get_challenge_for_update(self, token_hash: str) -> MfaChallenge | None:
        return self._db.scalar(
            select(MfaChallenge).where(MfaChallenge.token_hash == token_hash).with_for_update())

    def invalidate_challenges(self, user_id: UUID, now: datetime) -> None:
        self._db.execute(
            update(MfaChallenge)
            .where(MfaChallenge.user_id == user_id, MfaChallenge.consumed_at.is_(None))
            .values(consumed_at=now))

    def claim_totp_step(self, user_id: UUID, step: int) -> bool:
        """Atomically accept a time-step only if it is newer than the last one used."""
        result = self._db.execute(
            update(AdminUser)
            .where(AdminUser.id == user_id,
                   (AdminUser.mfa_last_used_step.is_(None))
                   | (AdminUser.mfa_last_used_step < step))
            .values(mfa_last_used_step=step)
            .execution_options(synchronize_session="fetch"))
        return result.rowcount == 1

    def replace_recovery_codes(self, user_id: UUID, code_hashes: list[str]) -> None:
        self.delete_recovery_codes(user_id)
        self._db.add_all(MfaRecoveryCode(user_id=user_id, code_hash=value) for value in code_hashes)

    def delete_recovery_codes(self, user_id: UUID) -> None:
        self._db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id))

    def unused_recovery_codes(self, user_id: UUID) -> list[MfaRecoveryCode]:
        return list(self._db.scalars(
            select(MfaRecoveryCode)
            .where(MfaRecoveryCode.user_id == user_id, MfaRecoveryCode.used_at.is_(None))
            .with_for_update()).all())

    def count_unused_recovery_codes(self, user_id: UUID) -> int:
        return len(self._db.scalars(
            select(MfaRecoveryCode.id)
            .where(MfaRecoveryCode.user_id == user_id, MfaRecoveryCode.used_at.is_(None))).all())
