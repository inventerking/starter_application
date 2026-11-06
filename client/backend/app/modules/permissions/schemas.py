"""Permission schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    resource: str
    action: str
    code: str
    description: str


class PermissionOverrideRequest(BaseModel):
    effect: Literal["ALLOW", "DENY"]
    reason: str | None = Field(default=None, max_length=255)


class PermissionOverrideResponse(BaseModel):
    permission: PermissionResponse
    effect: str
    reason: str | None
    created_at: datetime
