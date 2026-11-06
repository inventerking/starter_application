"""The Admin backend's explicit, narrow mapping of the Client schema.

This is the cross-domain contract of the control plane:

- It uses its own MetaData, which Alembic never sees, so Admin migrations cannot manage it.
- The Client backend owns these tables through its own migrations.
- Only the columns that administrators need are mapped. In particular, MFA secrets are only cleared
  by this backend, never read.
- tests/test_user_management.py checks this mapping against the real Client migrations.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, MetaData, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

CLIENT_SCHEMA = get_settings().client_database_schema


class ClientBase(DeclarativeBase):
    metadata = MetaData(schema=CLIENT_SCHEMA)


class ClientUser(ClientBase):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320))
    username: Mapped[str] = mapped_column(String(64))
    full_name: Mapped[str | None] = mapped_column(String(128))
    password_hash: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_enrollment_required: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(Text)
    mfa_key_id: Mapped[str | None] = mapped_column(String(32))
    mfa_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mfa_last_used_step: Mapped[int | None] = mapped_column(BigInteger)
    failed_login_count: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ClientRole(ClientBase):
    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ClientPermission(ClientBase):
    """Read-only here. Definitions are owned by the Client backend's permission registry."""

    __tablename__ = "permissions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    resource: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    code: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text)
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ClientUserRole(ClientBase):
    __tablename__ = "user_roles"

    user_id: Mapped[UUID] = mapped_column(ForeignKey(ClientUser.id), primary_key=True)
    role_id: Mapped[UUID] = mapped_column(ForeignKey(ClientRole.id), primary_key=True)


class ClientRolePermission(ClientBase):
    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(ForeignKey(ClientRole.id), primary_key=True)
    permission_id: Mapped[UUID] = mapped_column(ForeignKey(ClientPermission.id), primary_key=True)


class ClientUserPermission(ClientBase):
    __tablename__ = "user_permissions"

    user_id: Mapped[UUID] = mapped_column(ForeignKey(ClientUser.id), primary_key=True)
    permission_id: Mapped[UUID] = mapped_column(ForeignKey(ClientPermission.id), primary_key=True)
    effect: Mapped[str] = mapped_column(String(8))
    reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClientSession(ClientBase):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(ClientUser.id))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(64))


class ClientMfaChallenge(ClientBase):
    __tablename__ = "mfa_challenges"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(ClientUser.id))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ClientRecoveryCode(ClientBase):
    __tablename__ = "mfa_recovery_codes"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(ClientUser.id))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ClientAuditLog(ClientBase):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    action: Mapped[str] = mapped_column(String(64))
    actor_type: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[UUID | None] = mapped_column()
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[UUID | None] = mapped_column()
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
