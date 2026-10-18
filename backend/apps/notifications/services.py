"""Queue notifications (Notify.*, SI-2.2).

Messages are never sent inline: a Notification row is written in the
caller's transaction and a Celery task is enqueued only after that
transaction commits, so a provider outage can never fail or roll back the
business operation (SI-2.2, Robustness-2).
"""

from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Notification


def _enqueue_after_commit(task, *args) -> None:
    transaction.on_commit(lambda: task.delay(*args))


def _queue(recipient, channel: str, destination: str, template, context, booking, version):
    from .tasks import deliver_notification

    notification = Notification.objects.create(
        recipient=recipient,
        channel=channel,
        destination=destination,
        template=template,
        template_version=version,
        context=context,
        booking=booking,
    )
    _enqueue_after_commit(deliver_notification, notification.pk)
    return notification


def queue_email(recipient, template: str, context: dict, *, booking=None, version: int = 1):
    """Queue an e-mail to `recipient` (a User). `context` must hold no secrets."""
    return _queue(
        recipient, Notification.Channel.EMAIL, recipient.email, template, context, booking, version
    )


def queue_sms(recipient, template: str, context: dict, *, booking=None, version: int = 1):
    """Queue an SMS to `recipient`'s registered mobile (SI-2.2). `context` must hold no secrets."""
    return _queue(
        recipient,
        Notification.Channel.SMS,
        recipient.mobile_no,
        template,
        context,
        booking,
        version,
    )


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


PICKUP_REMINDER = "pickup_reminder"


def send_pickup_reminders(now: datetime | None = None) -> int:
    """Notify.Remind: e-mail and SMS each Confirmed booking PICKUP_REMINDER_BEFORE its
    collection, with the branch, the time, the pickup code and the documents to bring.

    Only Confirmed bookings with no handover report qualify, so Cancelled, No-show and
    handed-over ones are skipped. A booking is reminded once (a reminder Notification
    exists), and one confirmed inside the window is not (its confirmation just told
    it all; proposed R3-P3). Rows being changed elsewhere are skipped (SKIP LOCKED)
    and seen on the next run. Must run inside a transaction.
    """
    from apps.bookings.models import Booking
    from apps.bookings.services import notification_context
    from apps.rentals.models import ConditionReport

    now = now or timezone.now()
    lead = settings.PICKUP_REMINDER_BEFORE
    due = (
        Booking.objects.select_for_update(of=("self",), skip_locked=True)
        .select_related("vehicle", "pickup_branch", "customer__user", "customer__licence")
        .filter(
            status=Booking.Status.CONFIRMED,
            pickup_datetime__gt=now,
            pickup_datetime__lte=now + lead,
            confirmed_at__lte=F("pickup_datetime") - lead,
        )
        .exclude(condition_reports__report_type=ConditionReport.ReportType.HANDOVER)
        .exclude(notifications__template=PICKUP_REMINDER)
        .order_by("pickup_datetime", "pk")
    )
    count = 0
    for booking in due:
        user = booking.customer.user
        context = notification_context(booking)
        queue_email(user, PICKUP_REMINDER, context, booking=booking)
        queue_sms(user, f"{PICKUP_REMINDER}_sms", context, booking=booking)
        count += 1
    return count
