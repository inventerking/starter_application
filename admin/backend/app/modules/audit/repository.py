"""Audit persistence: add and read. There is deliberately no update or delete."""

from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, entry: AuditLog) -> None:
        self._db.add(entry)

    def list_page(
        self,
        *,
        page: int,
        page_size: int,
        action: str | None = None,
        involving: UUID | None = None,
        target_type: str | None = None,
        target_types: tuple[str, ...] | None = None,
    ) -> tuple[list[AuditLog], int]:
        query = select(AuditLog)
        if action:
            query = query.where(AuditLog.action == action)
        if involving:
            query = query.where(
                or_(AuditLog.actor_id == involving, AuditLog.target_id == involving))
        if target_type:
            query = query.where(AuditLog.target_type == target_type)
        if target_types:
            query = query.where(AuditLog.target_type.in_(target_types))
        total = self._db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self._db.scalars(
            query.order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), total
