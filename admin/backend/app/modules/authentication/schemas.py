"""Request and response schemas. Tokens other than the access token never appear in JSON."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.core.security import PASSWORD_MAX_LENGTH

Password = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=320, description="Email or username")
    password: str = Password


class AuthResponse(BaseModel):
    status: Literal["authenticated", "mfa_required", "mfa_enrollment_required"]
    access_token: str | None = None
    token_type: str = "bearer"  # noqa: S105
    expires_in: int | None = None
    challenge_token: str | None = None
    challenge_expires_in: int | None = None


class CurrentUserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    full_name: str | None
    is_superuser: bool
    mfa_enabled: bool
    must_change_password: bool
    mfa_enrollment_required: bool
    session_scope: str
    permissions: list[str]


class PasswordChangeRequest(BaseModel):
    current_password: str = Password
    new_password: str = Password


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=1, max_length=256)
    new_password: str = Password


class SessionResponse(BaseModel):
    id: UUID
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
    last_seen_at: datetime | None
    expires_at: datetime
    current: bool
