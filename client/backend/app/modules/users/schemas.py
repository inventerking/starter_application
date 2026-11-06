"""Profile schemas. Password hashes and MFA secrets are never part of any response."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    username: str
    full_name: str | None
    created_at: datetime
    last_login_at: datetime | None


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=128)


class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    action: str
    actor_type: str
    ip_address: str | None
    details: dict[str, Any]
    created_at: datetime
