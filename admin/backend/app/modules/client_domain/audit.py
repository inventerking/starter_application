"""Records an administrative change in both audit trails, in the caller's transaction.

The Client trail stores no Admin identity: only that an administrator acted, plus a correlation ID
that matches the entry in the Admin trail. The Admin trail stores only the Client record's UUID.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.request_context import RequestContext
from app.modules.audit.actions import AuditAction
from app.modules.audit.service import AuditService
from app.modules.client_domain.models import ClientAuditLog
from app.modules.client_domain.repository import ClientAuditRepository

ACTOR_ADMINISTRATOR = "administrator"


class CrossDomainAudit:
    def __init__(self, db: Session, context: RequestContext, actor_id: UUID) -> None:
        self._admin_trail = AuditService(db)
        self._client_trail = ClientAuditRepository(db)
        self._context = context
        self._actor_id = actor_id

    def record(
        self, action: AuditAction, target_type: str, target_id: UUID,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._admin_trail.record(action, self._context, actor_id=self._actor_id,
                                 target_type=target_type, target_id=target_id, details=details)
        self._client_trail.add(ClientAuditLog(
            action=action.value,
            actor_type=ACTOR_ADMINISTRATOR,
            actor_id=None,
            target_type=target_type,
            target_id=target_id,
            ip_address=None,
            user_agent=None,
            details={**(details or {}), "correlation_id": self._context.request_id},
        ))
