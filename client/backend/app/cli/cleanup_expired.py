"""Deletes expired authentication records. Schedule it daily.

Usage: uv run python -m app.cli.cleanup_expired
"""

from datetime import timedelta

from sqlalchemy import delete, or_
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, utcnow
from app.models_registry import *  # noqa: F403
from app.modules.authentication.models import (
    PasswordResetToken,
    RateLimitCounter,
    RefreshToken,
    UserSession,
)
from app.modules.mfa.models import MfaChallenge

# Revoked and expired sessions stay this long, so reuse detection and investigation still work.
_RETENTION = timedelta(days=30)
_RATE_LIMIT_RETENTION = timedelta(days=1)


def cleanup(db: Session) -> dict[str, int]:
    now = utcnow()
    horizon = now - _RETENTION
    statements = {
        "mfa_challenges": delete(MfaChallenge).where(MfaChallenge.expires_at < now),
        "password_reset_tokens": delete(PasswordResetToken).where(
            PasswordResetToken.expires_at < now),
        "refresh_tokens": delete(RefreshToken).where(RefreshToken.expires_at < horizon),
        "sessions": delete(UserSession).where(
            or_(UserSession.expires_at < horizon, UserSession.revoked_at < horizon)),
        "rate_limit_counters": delete(RateLimitCounter).where(
            RateLimitCounter.window_started_at < now - _RATE_LIMIT_RETENTION),
    }
    counts = {name: db.execute(statement).rowcount for name, statement in statements.items()}
    db.commit()
    return counts


if __name__ == "__main__":
    with SessionLocal() as session:
        print(cleanup(session))
