"""Audit recording. Entries join the caller's transaction, so they commit with the change."""

import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.request_context import RequestContext
from app.modules.audit.actions import AuditAction
from app.modules.audit.models import AuditLog
from app.modules.audit.repository import AuditRepository

ACTOR_ADMIN = "admin"
ACTOR_SYSTEM = "system"
ACTOR_ANONYMOUS = "anonymous"

_FORBIDDEN_KEY = re.compile(r"(?i)password|secret|token|recovery|hash|key|cookie|otp|code")


def _sanitize(details: dict[str, Any]) -> dict[str, Any]:
    """Drop any field whose name suggests sensitive content, as a last line of defence."""
    return {key: value for key, value in details.items() if not _FORBIDDEN_KEY.search(key)}


class AuditService:
    def __init__(self, db: Session) -> None:
        self._repository = AuditRepository(db)

    def record(
        self,
        action: AuditAction,
        context: RequestContext | None = None,
        *,
        actor_type: str = ACTOR_ADMIN,
        actor_id: UUID | None = None,
        target_type: str | None = None,
        target_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        context = context or RequestContext()
        payload = _sanitize(details or {})
        if context.request_id:
            payload["request_id"] = context.request_id
        self._repository.add(
            AuditLog(
                action=action.value,
                actor_type=actor_type,
                actor_id=actor_id,
                target_type=target_type,
                target_id=target_id,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                details=payload,
            )
        )
