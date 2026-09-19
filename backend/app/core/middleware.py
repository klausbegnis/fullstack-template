"""ASGI middleware for request correlation and access logging."""

from __future__ import annotations

import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logger import get_logger
from app.core.request_context import bind_request_id, get_request_id, reset_request_id

REQUEST_ID_HEADER = "X-Request-ID"

_access_logger = get_logger("app.access")


class RequestIDMiddleware:
    """Bind an inbound or generated request ID for the request's lifetime.

    The ID is taken from the inbound `X-Request-ID` header when present, or
    generated as a UUID4 otherwise. It is exposed to the rest of the request
    through `app.core.request_context`, stored on `request.state.request_id`,
    and echoed back on the response header.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request_id = Headers(scope=scope).get(REQUEST_ID_HEADER.lower())
        if not request_id:
            request_id = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        token = bind_request_id(request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault(REQUEST_ID_HEADER, request_id)
            await send(message)

        try:
            await self._app(scope, receive, send_with_request_id)
        finally:
            reset_request_id(token)


class AccessLogMiddleware:
    """Emit one structured access-log line per completed HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        status_code = 0
        started_at = time.perf_counter()

        async def send_and_capture_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        await self._app(scope, receive, send_and_capture_status)

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        _access_logger.info(
            "request completed",
            extra={
                "request_id": get_request_id(),
                "http_method": scope.get("method", ""),
                "http_path": scope.get("path", ""),
                "http_status_code": status_code,
                "duration_ms": duration_ms,
            },
        )
