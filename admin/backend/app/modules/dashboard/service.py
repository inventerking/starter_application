"""Builds a dashboard containing only what the caller's permissions allow."""

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.admins.models import AdminUser
from app.modules.admins.permissions import ADMINS_VIEW
from app.modules.admins.repository import AdminRepository
from app.modules.audit.permissions import AUDIT_VIEW
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditLogResponse
from app.modules.client_domain.repository import ClientUserRepository
from app.modules.dashboard.schemas import DashboardResponse
from app.modules.permissions.service import PermissionService
from app.modules.users.permissions import USERS_VIEW

_RECENT_ACTIVITY_SIZE = 10


class DashboardService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def summary(self, user: AdminUser) -> DashboardResponse:
        codes = PermissionService(self._db).effective_codes(user)
        admin_count = user_count = recent = None
        if ADMINS_VIEW.code in codes:
            _, admin_count = AdminRepository(self._db).list_page(
                page=1, page_size=1, search=None)
        if USERS_VIEW.code in codes:
            _, user_count = ClientUserRepository(self._db).list_page(
                page=1, page_size=1, search=None)
        if AUDIT_VIEW.code in codes:
            rows, _ = AuditRepository(self._db).list_page(page=1, page_size=_RECENT_ACTIVITY_SIZE)
            recent = [AuditLogResponse.model_validate(row) for row in rows]
        return DashboardResponse(
            environment=get_settings().environment, version="0.1.0", admin_count=admin_count,
            user_count=user_count, recent_activity=recent)
