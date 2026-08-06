"""ASGI middleware that assigns and propagates X-Request-ID."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from unity_ai_assets.core.request_context import (
    REQUEST_ID_HEADER,
    resolve_request_id,
    set_request_id,
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Validate or mint a request ID and attach it to every response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = resolve_request_id(incoming)
        set_request_id(request_id)
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
