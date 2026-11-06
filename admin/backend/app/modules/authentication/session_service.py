"""Issues, rotates and revokes sessions. Callers own the transaction and commit it."""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import utcnow
from app.core.request_context import RequestContext
from app.core.security import generate_token, hash_token
from app.modules.authentication.models import RefreshToken, UserSession
from app.modules.authentication.repository import SessionRepository


@dataclass(frozen=True)
class IssuedTokens:
    session: UserSession
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_max_age: int


class SessionService:
    def __init__(self, db: Session) -> None:
        self._repository = SessionRepository(db)
        self._settings = get_settings()

    def issue(self, user_id: UUID, scope: str, context: RequestContext) -> IssuedTokens:
        now = utcnow()
        access_token = generate_token()
        session = UserSession(
            user_id=user_id,
            scope=scope,
            access_token_hash=hash_token(access_token),
            access_expires_at=now + self._access_lifetime,
            expires_at=now + timedelta(days=self._settings.refresh_session_expire_days),
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            last_seen_at=now,
        )
        self._repository.add(session)
        return self._tokens(session, access_token, self._new_refresh_token(session))

    def rotate(self, session: UserSession) -> IssuedTokens:
        """Replace both credentials. The caller has marked the presented refresh token as used."""
        now = utcnow()
        access_token = generate_token()
        session.previous_access_token_hash = session.access_token_hash
        session.previous_access_expires_at = session.access_expires_at
        session.access_token_hash = hash_token(access_token)
        session.access_expires_at = now + self._access_lifetime
        session.last_seen_at = now
        return self._tokens(session, access_token, self._new_refresh_token(session))

    def revoke(self, session: UserSession, reason: str) -> None:
        if session.revoked_at is None:
            session.revoked_at = utcnow()
            session.revoke_reason = reason

    def revoke_all(
        self, user_id: UUID, reason: str, *, except_session: UUID | None = None
    ) -> int:
        return self._repository.revoke_for_user(
            user_id, reason, utcnow(), except_session=except_session)

    @property
    def _access_lifetime(self) -> timedelta:
        return timedelta(minutes=self._settings.access_token_expire_minutes)

    def _new_refresh_token(self, session: UserSession) -> str:
        token = generate_token()
        self._repository.add_refresh_token(RefreshToken(
            session_id=session.id, token_hash=hash_token(token), expires_at=session.expires_at))
        return token

    def _tokens(self, session: UserSession, access: str, refresh: str) -> IssuedTokens:
        return IssuedTokens(
            session=session,
            access_token=access,
            refresh_token=refresh,
            expires_in=int(self._access_lifetime.total_seconds()),
            refresh_max_age=max(0, int((session.expires_at - utcnow()).total_seconds())),
        )
