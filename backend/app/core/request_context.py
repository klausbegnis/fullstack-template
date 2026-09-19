"""Per-request context propagated through `contextvars`."""

from __future__ import annotations

from contextvars import ContextVar, Token

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Return the request ID bound to the current execution context, if any."""
    return _request_id.get()


def bind_request_id(request_id: str) -> Token[str | None]:
    """Bind a request ID to the current execution context."""
    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Restore the execution context to its state before `bind_request_id`."""
    _request_id.reset(token)
