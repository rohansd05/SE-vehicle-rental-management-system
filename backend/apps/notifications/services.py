"""Queue notifications (Notify.*, SI-2.2).

Messages are never sent inline: a Notification row is written in the
caller's transaction and a Celery task is enqueued only after that
transaction commits, so a provider outage can never fail or roll back the
business operation (SI-2.2, Robustness-2).
"""

from django.db import transaction

from .models import Notification


def _enqueue_after_commit(task, *args) -> None:
    transaction.on_commit(lambda: task.delay(*args))


def queue_email(recipient, template: str, context: dict, *, booking=None, version: int = 1):
    """Queue an e-mail to `recipient` (a User). `context` must hold no secrets."""
    from .tasks import deliver_notification

    notification = Notification.objects.create(
        recipient=recipient,
        channel=Notification.Channel.EMAIL,
        destination=recipient.email,
        template=template,
        template_version=version,
        context=context,
        booking=booking,
    )
    _enqueue_after_commit(deliver_notification, notification.pk)
    return notification


def queue_otp_sms(otp) -> Notification:
    """Queue the SMS for a OneTimePassword (SE-7).

    The code does not exist yet: the task generates it, stores only its hash
    and sends it, so the plain code is never in the database, in the
    Notification row or in a queued Celery message.
    """
    from .tasks import send_otp

    notification = Notification.objects.create(
        recipient=otp.user,
        channel=Notification.Channel.SMS,
        destination=otp.destination,
        template="otp",
        context={"purpose": otp.purpose, "otp_id": otp.pk},
    )
    _enqueue_after_commit(send_otp, otp.pk, notification.pk)
    return notification
