"""Sessions, refresh tokens, password reset tokens and rate limit counters."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import SCHEMA, Base
from app.core.db_types import CreatedAt, UUIDPk

SCOPE_FULL = "full"
SCOPE_MFA_ENROLLMENT = "mfa_enrollment"


class UserSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (CheckConstraint("scope IN ('full', 'mfa_enrollment')", name="scope"),)

    id: Mapped[UUIDPk]
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(String(32))
    access_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # The prior access token stays valid until it expires so other browser tabs keep working.
    previous_access_token_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    previous_access_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(64))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[CreatedAt]
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(Base):
    """One row per issued token, so that reuse of a rotated token can be detected."""

    __tablename__ = "refresh_tokens"

    id: Mapped[UUIDPk]
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.sessions.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[UUIDPk]
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]


class RateLimitCounter(Base):
    """Fixed-window counters. The key is a SHA-256 digest, so no identifier is stored in clear."""

    __tablename__ = "rate_limit_counters"
    __table_args__ = (Index("ix_rate_limit_counters_window", "window_started_at"),)

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
