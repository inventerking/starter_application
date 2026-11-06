"""Dashboard schemas. A section the caller may not see is null, never a leaked count."""

from pydantic import BaseModel

from app.modules.audit.schemas import AuditLogResponse


class DashboardResponse(BaseModel):
    environment: str
    version: str
    admin_count: int | None
    user_count: int | None
    recent_activity: list[AuditLogResponse] | None
