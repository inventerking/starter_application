"""Read-only Admin audit log."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.pagination import Page, PageParams
from app.modules.audit.permissions import AUDIT_VIEW
from app.modules.audit.repository import AuditRepository
from app.modules.audit.schemas import AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=Page[AuditLogResponse],
            dependencies=[Depends(require_permission(AUDIT_VIEW))])
def list_audit_logs(
    params: PageParams = Depends(),
    action: str | None = Query(default=None, max_length=64),
    involving: UUID | None = None,
    db: Session = Depends(get_db),
) -> Page:
    items, total = AuditRepository(db).list_page(
        page=params.page, page_size=params.page_size, action=action, involving=involving)
    return Page(items=items, total=total, page=params.page, page_size=params.page_size)
