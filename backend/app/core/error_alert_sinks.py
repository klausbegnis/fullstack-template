"""Where error alert notifications go: a pluggable sink behind one Protocol.

`LoggingErrorAlertSink` (the default) writes each notification as one
structured log record. `WebhookErrorAlertSink` POSTs `{"text": ...}` as JSON to
`ERROR_ALERT_WEBHOOK_URL`, the body a Slack incoming webhook accepts as is;
any other receiver gets the same plain-text rendering. A sink never raises: a
failed delivery becomes one warning that names only the error type, never the
URL, which usually embeds a secret.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Literal, Protocol

import httpx
from pydantic import SecretStr

from app.core.error_alerts import ErrorAlert
from app.core.logger import get_logger

logger = get_logger(__name__)

WEBHOOK_TIMEOUT_SECONDS = 5.0
WEBHOOK_SCHEMES = ("https://", "http://")
CODE_FENCE = "```"
SAFE_FENCE = "'''"
NOT_GIVEN = "-"

Severity = Literal["error", "warning"]
SEVERITY_LEVELS: dict[Severity, int] = {
    "error": logging.ERROR,
    "warning": logging.WARNING,
}


@dataclass(frozen=True, slots=True)
class AlertNotification:
    """One message for a sink: a title, labelled fields and an optional code block."""

    severity: Severity
    title: str
    environment: str
    occurred_at: datetime
    fields: tuple[tuple[str, str], ...] = ()
    code: str | None = None

    def as_text(self) -> str:
        """Render the notification as plain text, the traceback fenced last."""
        lines = [f"[{self.severity.upper()}] {self.title}"]
        lines.extend(f"{label}: {value}" for label, value in self.fields)
        lines.append(f"{self.environment} | {self.occurred_at.isoformat()}")
        if self.code:
            fenced = self.code.replace(CODE_FENCE, SAFE_FENCE)
            lines.append(f"{CODE_FENCE}{fenced}{CODE_FENCE}")
        return "\n".join(lines)


class ErrorAlertSink(Protocol):
    """Deliver one notification; implementations log a failure and never raise."""

    async def deliver(self, notification: AlertNotification) -> None: ...


class LoggingErrorAlertSink:
    """Write each notification as one structured log record."""

    async def deliver(self, notification: AlertNotification) -> None:
        logger.log(
            SEVERITY_LEVELS[notification.severity],
            "error alert: %s",
            notification.title,
            extra={
                "alert_environment": notification.environment,
                "alert_fields": dict(notification.fields),
                "alert_traceback": notification.code,
            },
        )


class WebhookErrorAlertSink:
    """POST `{"text": ...}` to a webhook such as a Slack incoming webhook.

    Each delivery opens its own short-lived client: alerts are rare and
    throttled, and a client bound to one event loop must not outlive it.
    """

    def __init__(
        self,
        *,
        url: SecretStr,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = WEBHOOK_TIMEOUT_SECONDS,
    ) -> None:
        self._url = url
        self._transport = transport
        self._timeout = timeout

    async def deliver(self, notification: AlertNotification) -> None:
        try:
            async with httpx.AsyncClient(
                transport=self._transport, timeout=self._timeout
            ) as client:
                response = await client.post(
                    self._url.get_secret_value(),
                    json={"text": notification.as_text()},
                )
        except httpx.HTTPError as exc:
            _log_undelivered(type(exc).__name__)
            return
        if not response.is_success:
            _log_undelivered(f"http_{response.status_code}")


def build_error_alert_sink(webhook_url: SecretStr) -> ErrorAlertSink:
    """Return the webhook sink when a URL is configured, else the logging sink."""
    url = webhook_url.get_secret_value().strip()
    if not url:
        return LoggingErrorAlertSink()
    if not url.startswith(WEBHOOK_SCHEMES):
        raise ValueError("ERROR_ALERT_WEBHOOK_URL must be an http(s) URL")
    return WebhookErrorAlertSink(url=SecretStr(url))


def error_alert_notification(
    alert: ErrorAlert, *, environment: str, release: str
) -> AlertNotification:
    """Report one unhandled exception, its traceback last."""
    return AlertNotification(
        severity="error",
        title=_error_title(alert),
        environment=environment,
        occurred_at=alert.occurred_at,
        fields=(
            ("Route", alert.route_template),
            *_optional_field("User id", alert.user_id),
            *_optional_field("Request id", alert.request_id),
            ("Release", release),
            ("Failure site", alert.failure_site),
            ("Message", alert.message or NOT_GIVEN),
        ),
        code=alert.traceback or None,
    )


def repeat_summary_notification(
    alert: ErrorAlert,
    *,
    count: int,
    environment: str,
    release: str,
    occurred_at: datetime,
) -> AlertNotification:
    """Count the repeats of one error alert seen while its window was open."""
    return AlertNotification(
        severity="warning",
        title=f"{count}x {_error_title(alert)}",
        environment=environment,
        occurred_at=occurred_at,
        fields=(
            ("Repeats", str(count)),
            ("Route", alert.route_template),
            ("Failure site", alert.failure_site),
            ("Release", release),
        ),
    )


def suppressed_notification(
    *, count: int, environment: str, release: str, occurred_at: datetime
) -> AlertNotification:
    """Count the error alerts dropped by the hourly cap."""
    return AlertNotification(
        severity="warning",
        title=f"{count} error alerts suppressed",
        environment=environment,
        occurred_at=occurred_at,
        fields=(("Suppressed alerts", str(count)), ("Release", release)),
    )


def _error_title(alert: ErrorAlert) -> str:
    return f"{alert.exception_class} in {alert.method} {alert.route_template}"


def _optional_field(label: str, value: str | None) -> tuple[tuple[str, str], ...]:
    return ((label, value),) if value else ()


def _log_undelivered(reason: str) -> None:
    logger.warning("error alert not delivered", extra={"error_type": reason})
