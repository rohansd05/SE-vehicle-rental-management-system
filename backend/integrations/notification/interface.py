"""Notification Service interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationResult:
    success: bool
    message_id: str
    detail: str = ""


class NotificationService(ABC):
    @abstractmethod
    def send_email(self, to: str, subject: str, body: str) -> NotificationResult:
        """Send a transactional e-mail."""

    @abstractmethod
    def send_sms(self, to: str, body: str) -> NotificationResult:
        """Send an SMS to a mobile number."""

    @abstractmethod
    def send_push(self, device_token: str, title: str, body: str) -> NotificationResult:
        """Send a push notification to one device."""
