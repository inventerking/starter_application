"""PostgreSQL-backed fixed-window rate limiting, safe across multiple workers."""

import hashlib
from datetime import timedelta

from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert

from app.core.database import SessionLocal, utcnow
from app.core.exceptions import RateLimited
from app.modules.authentication.models import RateLimitCounter


def enforce_rate_limit(key: str, *, limit: int, window_seconds: int = 60) -> None:
    """Count one attempt and raise RateLimited when over the limit.

    Uses its own committed transaction, so attempts still count when the request later fails.
    """
    digest = hashlib.sha256(key.encode()).hexdigest()
    now = utcnow()
    cutoff = now - timedelta(seconds=window_seconds)
    statement = insert(RateLimitCounter).values(key=digest, window_started_at=now, count=1)
    expired = RateLimitCounter.window_started_at < cutoff
    statement = statement.on_conflict_do_update(
        index_elements=[RateLimitCounter.key],
        set_={
            "count": case((expired, 1), else_=RateLimitCounter.count + 1),
            "window_started_at": case((expired, now), else_=RateLimitCounter.window_started_at),
        },
    ).returning(RateLimitCounter.count, RateLimitCounter.window_started_at)
    with SessionLocal() as session:
        count, started = session.execute(statement).one()
        session.commit()
    if count > limit:
        elapsed = (now - started).total_seconds()
        raise RateLimited(retry_after=max(1, int(window_seconds - elapsed)))
