"""Roles of the Admin domain. These records are never used for Client users."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import SCHEMA, Base
from app.core.db_types import CreatedAt, UpdatedAt, UUIDPk


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (Index("uq_roles_name", text("lower(name)"), unique=True),)

    id: Mapped[UUIDPk]
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.roles.id", ondelete="CASCADE"), primary_key=True)
    assigned_by: Mapped[UUID | None] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="SET NULL"))
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.permissions.id", ondelete="CASCADE"), primary_key=True)
