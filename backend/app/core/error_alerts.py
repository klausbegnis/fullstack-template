"""Capture an unhandled exception as a scrubbed, size-capped error alert.

An alert names the route by its template, never the raw path, carries only the
internal ids the request resolved, and renders the traceback from frame
summaries alone: file, line, function and source line, never locals, headers,
cookies, query string or body. The exception message is cut before any SQL,
bound parameters or database DETAIL line, then scrubbed of emails, phone-like
digit runs and token-like strings before it is capped.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path, PurePath
import re
import traceback
from typing import Protocol

from starlette.requests import Request
from starlette.types import Scope

APP_ROOT = Path(__file__).parents[1]
APP_PREFIX = f"{APP_ROOT}{os.sep}"
UNMATCHED_ROUTE = "<unmatched>"
UNKNOWN_FAILURE_SITE = "<unknown>"
MESSAGE_MAX_CHARACTERS = 300
TRACEBACK_MAX_FRAMES = 15
TRACEBACK_MAX_CHARACTERS = 2500
SITE_PACKAGES = "site-packages"

DATABASE_DETAIL_MARKERS: tuple[str, ...] = ("[SQL:", "[parameters:", "DETAIL:")

SCRUB_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[email]"),
    (
        re.compile(r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
        "[token]",
    ),
    (re.compile(r"[A-Za-z0-9_-]{24,}"), "[token]"),
    (re.compile(r"\+?\d(?:[\s().-]*\d){7,}"), "[phone]"),
)


@dataclass(frozen=True, slots=True)
class ErrorAlert:
    """What one unhandled exception reports, already scrubbed and capped."""

    exception_class: str
    method: str
    route_template: str
    request_id: str | None
    user_id: str | None
    failure_site: str
    message: str
    traceback: str
    occurred_at: datetime

    @property
    def fingerprint(self) -> str:
        """Identify repeats of the same failure: class, route and failure site."""
        return f"{self.exception_class}|{self.route_template}|{self.failure_site}"


class ErrorAlertReporting(Protocol):
    """What the exception handler hands a captured alert to."""

    @property
    def enabled(self) -> bool:
        """Whether this process reports unhandled exceptions at all."""
        ...

    def now(self) -> datetime:
        """Return the time an alert captured now occurred at."""
        ...

    async def report(self, alert: ErrorAlert) -> None:
        """Deliver `alert` off the response path; never raise."""
        ...


def capture_error_alert(
    request: Request, exc: BaseException, occurred_at: datetime
) -> ErrorAlert:
    """Build the alert for `exc`, raised while serving `request`."""
    frames = traceback.extract_tb(exc.__traceback__)
    return ErrorAlert(
        exception_class=type(exc).__name__,
        method=request.method,
        route_template=route_template(request.scope),
        request_id=_state_text(request, "request_id"),
        user_id=_state_text(request, "user_id"),
        failure_site=failure_site(frames),
        message=scrub_exception_message(str(exc)),
        traceback=render_traceback(frames),
        occurred_at=occurred_at,
    )


def route_template(scope: Scope) -> str:
    """Return the matched route's full path template, never the raw path."""
    fastapi_scope = scope.get("fastapi")
    if isinstance(fastapi_scope, dict):
        effective = fastapi_scope.get("effective_route_context")
        effective_path = getattr(effective, "path", None)
        if isinstance(effective_path, str) and effective_path:
            return effective_path
    path = getattr(scope.get("route"), "path", None)
    return path if isinstance(path, str) and path else UNMATCHED_ROUTE


def scrub_exception_message(text: str) -> str:
    """Drop database detail, replace personal data and secrets, then cap length."""
    text = drop_database_detail(text)
    for pattern, replacement in SCRUB_PATTERNS:
        text = pattern.sub(replacement, text)
    return text[:MESSAGE_MAX_CHARACTERS]


def drop_database_detail(text: str) -> str:
    """Keep only the text before the first SQL, parameters or DETAIL marker."""
    cut = min(
        (
            index
            for index in (text.find(marker) for marker in DATABASE_DETAIL_MARKERS)
            if index >= 0
        ),
        default=len(text),
    )
    return text[:cut].strip()


def failure_site(frames: traceback.StackSummary) -> str:
    """Name the innermost frame under `app/`, else the innermost frame."""
    for frame in reversed(frames):
        if _is_app_frame(frame.filename):
            return _frame_location(frame)
    return _frame_location(frames[-1]) if frames else UNKNOWN_FAILURE_SITE


def render_traceback(frames: traceback.StackSummary) -> str:
    """Render the last frames as location plus source line, tail-capped."""
    lines: list[str] = []
    for frame in frames[-TRACEBACK_MAX_FRAMES:]:
        lines.append(_frame_location(frame))
        if frame.line:
            lines.append(f"    {frame.line.strip()}")
    return "\n".join(lines)[-TRACEBACK_MAX_CHARACTERS:]


def _frame_location(frame: traceback.FrameSummary) -> str:
    return f"{_display_path(frame.filename)}:{frame.lineno} in {frame.name}"


def _is_app_frame(filename: str) -> bool:
    return filename.startswith(APP_PREFIX)


def _display_path(filename: str) -> str:
    if _is_app_frame(filename):
        relative = PurePath(filename[len(APP_PREFIX) :])
        return (PurePath(APP_ROOT.name) / relative).as_posix()
    parts = PurePath(filename).parts
    if SITE_PACKAGES in parts:
        return PurePath(*parts[parts.index(SITE_PACKAGES) + 1 :]).as_posix()
    return PurePath(filename).name


def _state_text(request: Request, name: str) -> str | None:
    value = getattr(request.state, name, None)
    return None if value is None else str(value)
