"""Self-service profile operations. Account administration lives in the Admin control plane."""

from sqlalchemy.orm import Session

from app.core.request_context import RequestContext
from app.modules.audit.actions import AuditAction
from app.modules.audit.models import AuditLog
from app.modules.audit.repository import AuditRepository
from app.modules.audit.service import AuditService
from app.modules.users.models import User

TARGET = "user"


class ProfileService:
    def __init__(self, db: Session, context: RequestContext) -> None:
        self._db = db
        self._context = context

    def update(self, user: User, changes: dict) -> User:
        if "full_name" in changes:
            user.full_name = changes["full_name"]
        AuditService(self._db).record(
            AuditAction.USER_UPDATED, self._context, actor_id=user.id, target_type=TARGET,
            target_id=user.id, details={"changed": sorted(changes)})
        self._db.commit()
        return user

    def activity(self, user: User, page: int, page_size: int) -> tuple[list[AuditLog], int]:
        return AuditRepository(self._db).list_page(
            page=page, page_size=page_size, involving=user.id)
