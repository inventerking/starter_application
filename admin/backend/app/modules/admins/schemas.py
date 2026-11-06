"""Admin Management schemas. Password hashes and MFA secrets are never part of any response."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Username = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")


class AdminCreateRequest(BaseModel):
    email: EmailStr
    username: str = Username
    full_name: str | None = Field(default=None, max_length=128)


class AdminUpdateRequest(BaseModel):
    email: EmailStr | None = None
    username: str | None = Field(default=None, min_length=3, max_length=64,
                                 pattern=r"^[A-Za-z0-9_.-]+$")
    full_name: str | None = Field(default=None, max_length=128)


class AdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    username: str
    full_name: str | None
    is_active: bool
    is_superuser: bool
    mfa_enabled: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime


class AdminCreatedResponse(AdminResponse):
    temporary_password: str = Field(description="Shown once. The account must change it at login.")


class TemporaryPasswordResponse(BaseModel):
    temporary_password: str


class MfaStatusResponse(BaseModel):
    enabled: bool
    enrollment_required: bool
    confirmed_at: datetime | None
    recovery_codes_remaining: int
