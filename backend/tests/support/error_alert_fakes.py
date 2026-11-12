"""An in-memory error alert sink that keeps every notification it was handed."""

from __future__ import annotations

from app.core.error_alert_sinks import AlertNotification


class RecordingErrorAlertSink:
    """Record delivered notifications in order."""

    def __init__(self) -> None:
        self.delivered: list[AlertNotification] = []

    async def deliver(self, notification: AlertNotification) -> None:
        self.delivered.append(notification)
