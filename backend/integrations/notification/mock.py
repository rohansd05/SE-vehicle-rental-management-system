"""Deterministic in-memory notification service for development and tests.

Nothing is sent. Every message is appended to `outbox`, and message ids are
sequential per instance: mock_msg_000001, ...

In development (DEBUG=True) the message is also logged, so an OTP can be
read from the Celery worker console. Outside development the body is never
logged, because it may contain an OTP code (SE-7).
"""

import logging
from dataclasses import dataclass

from django.conf import settings

from .interface import NotificationResult, NotificationService

logger = logging.getLogger("vrms.notifications.mock")


@dataclass(frozen=True)
class SentNotification:
    channel: str
    recipient: str
    subject: str
    body: str
    message_id: str


class MockNotificationService(NotificationService):
    def __init__(self) -> None:
        self.outbox: list[SentNotification] = []

    def clear(self) -> None:
        self.outbox.clear()

    def _record(self, channel: str, recipient: str, subject: str, body: str) -> NotificationResult:
        message_id = f"mock_msg_{len(self.outbox) + 1:06d}"
        self.outbox.append(SentNotification(channel, recipient, subject, body, message_id))
        shown = body if settings.DEBUG else "[body not logged outside development]"
        logger.info("MOCK %s to %s | %s | %s", channel.upper(), recipient, subject, shown)
        return NotificationResult(True, message_id)

    def send_email(self, to: str, subject: str, body: str) -> NotificationResult:
        return self._record("email", to, subject, body)

    def send_sms(self, to: str, body: str) -> NotificationResult:
        return self._record("sms", to, "", body)

    def send_push(self, device_token: str, title: str, body: str) -> NotificationResult:
        return self._record("push", device_token, title, body)
