"""Request metadata passed to services for auditing and rate limiting."""

from dataclasses import dataclass

from fastapi import Request


@dataclass(frozen=True)
class RequestContext:
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None


def get_request_context(request: Request) -> RequestContext:
    return RequestContext(
        ip_address=request.client.host[:45] if request.client else None,
        user_agent=(request.headers.get("user-agent") or "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
    )
