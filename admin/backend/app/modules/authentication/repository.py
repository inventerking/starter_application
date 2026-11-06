"""Persistence for sessions, refresh tokens and password reset tokens."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.modules.authentication.models import PasswordResetToken, RefreshToken, UserSession


class SessionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, session: UserSession) -> None:
        self._db.add(session)
        self._db.flush()

    def add_refresh_token(self, token: RefreshToken) -> None:
        self._db.add(token)

    def get(self, session_id: UUID) -> UserSession | None:
        return self._db.get(UserSession, session_id)

    def get_for_update(self, session_id: UUID) -> UserSession | None:
        return self._db.scalar(
            select(UserSession).where(UserSession.id == session_id).with_for_update())

    def get_by_access_hash(self, token_hash: str) -> UserSession | None:
        return self._db.scalar(
            select(UserSession).where(
                or_(UserSession.access_token_hash == token_hash,
                    UserSession.previous_access_token_hash == token_hash)))

    def get_refresh_token(self, token_hash: str) -> RefreshToken | None:
        return self._db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update())

    def list_active(self, user_id: UUID, now: datetime) -> list[UserSession]:
        return list(self._db.scalars(
            select(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None),
                   UserSession.expires_at > now)
            .order_by(UserSession.created_at.desc())).all())

    def revoke_for_user(
        self, user_id: UUID, reason: str, now: datetime, *, except_session: UUID | None = None
    ) -> int:
        statement = (
            update(UserSession)
            .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
            .values(revoked_at=now, revoke_reason=reason))
        if except_session:
            statement = statement.where(UserSession.id != except_session)
        return self._db.execute(statement.execution_options(synchronize_session="fetch")).rowcount


class PasswordResetRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, token: PasswordResetToken) -> None:
        self._db.add(token)

    def get_for_update(self, token_hash: str) -> PasswordResetToken | None:
        return self._db.scalar(
            select(PasswordResetToken)
            .where(PasswordResetToken.token_hash == token_hash).with_for_update())

    def invalidate_for_user(self, user_id: UUID, now: datetime) -> None:
        self._db.execute(
            update(PasswordResetToken)
            .where(PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None))
            .values(used_at=now))
