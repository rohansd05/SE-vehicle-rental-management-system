"""Notification Service integration (e-mail, SMS, push).

Callers go through Celery tasks in apps.notifications, never inline, so a
provider outage cannot fail a booking transaction.
"""

from .factory import get_notification_service
from .interface import NotificationResult, NotificationService

__all__ = ["NotificationResult", "NotificationService", "get_notification_service"]
