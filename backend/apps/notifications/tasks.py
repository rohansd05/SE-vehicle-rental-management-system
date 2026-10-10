"""Celery tasks that deliver notifications (SI-2.2).

Workers on Windows need ``--pool=solo``. Task arguments are ids only, so no
message content (and no OTP code) is ever written to the broker.
"""

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from integrations.notification import get_notification_service

from .models import Notification
from .templates import render


class DeliveryError(Exception):
    """The provider refused the message; the task is retried with back-off."""


def _send(notification: Notification, subject: str, body: str) -> None:
    service = get_notification_service()
    notification.attempt_count += 1
    if notification.channel == Notification.Channel.EMAIL:
        result = service.send_email(notification.destination, subject, body)
    elif notification.channel == Notification.Channel.SMS:
        result = service.send_sms(notification.destination, body)
    else:
        result = service.send_push(notification.destination, subject, body)
    if result.success:
        notification.status = Notification.Status.SENT
        notification.provider_message_id = result.message_id
        notification.sent_at = timezone.now()
        notification.error = ""
    else:
        notification.status = Notification.Status.FAILED
        notification.error = (result.detail or "Delivery failed.")[:255]
    notification.save(
        update_fields=[
            "attempt_count",
            "status",
            "provider_message_id",
            "sent_at",
            "error",
            "updated_at",
        ]
    )
    if not result.success:
        raise DeliveryError(notification.error)


@shared_task(autoretry_for=(DeliveryError,), retry_backoff=True, max_retries=5)
def deliver_notification(notification_id: int) -> None:
    notification = Notification.objects.get(pk=notification_id)
    subject, body = render(
        notification.template, notification.template_version, notification.context
    )
    _send(notification, subject, body)


@shared_task(autoretry_for=(DeliveryError,), retry_backoff=True, max_retries=5)
def send_otp(otp_id: int, notification_id: int) -> None:
    """Generate the OTP code, keep only its hash, and send it by SMS (SE-7)."""
    from apps.accounts.services import assign_otp_code

    code = assign_otp_code(otp_id)
    notification = Notification.objects.get(pk=notification_id)
    minutes = int(settings.OTP_LIFETIME.total_seconds() // 60)
    subject, body = render("otp", notification.template_version, {"code": code, "minutes": minutes})
    _send(notification, subject, body)
