"""Permission definitions and direct per-user overrides (the ACL part of the model)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import SCHEMA, Base
from app.core.db_types import CreatedAt, UpdatedAt, UUIDPk


class Permission(Base):
    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("resource", "action"),)

    id: Mapped[UUIDPk]
    resource: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    code: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str] = mapped_column(Text)
    # Set when a definition leaves the registry. Deprecated permissions are never effective.
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


class UserPermission(Base):
    __tablename__ = "user_permissions"
    __table_args__ = (CheckConstraint("effect IN ('ALLOW', 'DENY')", name="effect"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.permissions.id", ondelete="CASCADE"), primary_key=True)
    effect: Mapped[str] = mapped_column(String(8))
    reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[CreatedAt]
