"""Pagination contract shared by list endpoints."""

from fastapi import Query
from pydantic import BaseModel


class PageParams:
    def __init__(
        self, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)
    ) -> None:
        self.page = page
        self.page_size = page_size


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


def like_pattern(term: str) -> str:
    """Escape LIKE wildcards in user input. Use with escape='\\\\'."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
