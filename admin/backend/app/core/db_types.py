"""Reusable column helpers shared by this domain's models."""

from datetime import datetime
from typing import Annotated
from uuid import UUID, uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.orm import mapped_column

UUIDPk = Annotated[UUID, mapped_column(primary_key=True, default=uuid4)]
Timestamp = Annotated[datetime, mapped_column(DateTime(timezone=True))]
CreatedAt = Annotated[
    datetime, mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
]
UpdatedAt = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    ),
]
