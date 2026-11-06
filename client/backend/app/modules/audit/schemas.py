"""Audit log response schema."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    action: str
    actor_type: str
    actor_id: UUID | None
    target_type: str | None
    target_id: UUID | None
    ip_address: str | None
    user_agent: str | None
    details: dict[str, Any]
    created_at: datetime
