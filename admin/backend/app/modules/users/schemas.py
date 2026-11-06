"""User Management schemas. Hashes and MFA secrets are never part of any response."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ClientUserCreateRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    full_name: str | None = Field(default=None, max_length=128)
    role_ids: list[UUID] | None = Field(
        default=None, max_length=100, description="Omit to assign the default Client roles.")


class ClientUserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    username: str | None = Field(default=None, min_length=3, max_length=64,
                                 pattern=r"^[A-Za-z0-9_.-]+$")
    full_name: str | None = Field(default=None, max_length=128)


class ClientUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    username: str
    full_name: str | None
    is_active: bool
    mfa_enabled: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime


class ClientUserCreatedResponse(ClientUserResponse):
    temporary_password: str = Field(description="Shown once. The user must change it at login.")


class TemporaryPasswordResponse(BaseModel):
    temporary_password: str


class ClientMfaStatusResponse(BaseModel):
    enabled: bool
    enrollment_required: bool
    confirmed_at: datetime | None
    recovery_codes_remaining: int


class ClientPermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    resource: str
    action: str
    code: str
    description: str


class ClientOverrideRequest(BaseModel):
    effect: Literal["ALLOW", "DENY"]
    reason: str | None = Field(default=None, max_length=255)


class ClientOverrideResponse(BaseModel):
    permission: ClientPermissionResponse
    effect: str
    reason: str | None
    created_at: datetime


class ClientRoleSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    is_system: bool
    is_default: bool
    created_at: datetime


class ClientRoleAssignmentRequest(BaseModel):
    role_id: UUID


class ClientActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    action: str
    actor_type: str
    ip_address: str | None
    details: dict[str, Any]
    created_at: datetime
