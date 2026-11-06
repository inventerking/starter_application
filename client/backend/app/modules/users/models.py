"""client.users: ordinary application users. Administrative accounts live in admin.users."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.db_types import CreatedAt, UpdatedAt, UUIDPk


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("uq_users_email_active", text("lower(email)"), unique=True,
              postgresql_where=text("deleted_at IS NULL")),
        Index("uq_users_username_active", text("lower(username)"), unique=True,
              postgresql_where=text("deleted_at IS NULL")),
    )

    id: Mapped[UUIDPk]
    email: Mapped[str] = mapped_column(String(320))
    username: Mapped[str] = mapped_column(String(64))
    full_name: Mapped[str | None] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"))
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    # Set by an MFA reset: forces re-enrollment even when MFA is not globally mandatory.
    mfa_enrollment_required: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"))
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(Text)
    mfa_key_id: Mapped[str | None] = mapped_column(String(32))
    mfa_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mfa_last_used_step: Mapped[int | None] = mapped_column(BigInteger)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
