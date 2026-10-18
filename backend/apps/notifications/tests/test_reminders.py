"""Notify.Remind (SRS 3.8.3): the pickup reminder PICKUP_REMINDER_BEFORE (24 hours) before
collection, by e-mail and SMS, from the Celery Beat task scheduled by notifications/0002.
One row per channel, never twice for one booking; SI-2.2 queueing; Exp 5 "Send reminders
24 h"."""

from datetime import UTC, datetime, timedelta

import pytest
from django.conf import settings
from django_celery_beat.models import PeriodicTask
from freezegun import freeze_time

from apps.accounts.tests.factories import LicenceFactory, UserFactory
from apps.bookings.models import Booking
from apps.bookings.tests.factories import BookingFactory
from apps.notifications import tasks
from apps.notifications.models import Notification
from apps.notifications.services import queue_sms
from apps.rentals.tests.factories import ConditionReportFactory

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 20, 4, 30, tzinfo=UTC)  # 10:00 IST
S = Booking.Status


def due(**overrides) -> Booking:
    """A Confirmed booking collected 23 hours from NOW, confirmed three days earlier."""
    values = {
        "pickup_datetime": NOW + timedelta(hours=23),
        "confirmed_at": NOW - timedelta(days=3),
        "pickup_code": "482913",
    }
    return BookingFactory(**{**values, **overrides})


def remind(at=NOW) -> int:
    with freeze_time(at):
        return tasks.send_pickup_reminders.delay().get()


def reminders(booking) -> list[tuple[str, str, str]]:
    rows = Notification.objects.filter(booking=booking).order_by("pk")
    return list(rows.values_list("template", "channel", "status"))


def test_the_reminder_lead_is_24_hours():
    assert settings.PICKUP_REMINDER_BEFORE == timedelta(hours=24)


def test_a_booking_collected_within_24_hours_is_reminded_by_e_mail_and_sms(outbox):
    booking = due()
    licence = LicenceFactory(customer=booking.customer)
    assert remind() == 1
    assert reminders(booking) == [
        ("pickup_reminder", "Email", "Sent"),
        ("pickup_reminder_sms", "SMS", "Sent"),
    ]
    mail, text = outbox
    user = booking.customer.user
    assert (mail.recipient, text.recipient) == (user.email, user.mobile_no)
    # The branch, the time, the pickup code and the documents to bring.
    for message in (mail, text):
        assert booking.pickup_branch.branch_name in message.body
        assert "21 Oct 2026 09:00" in message.body  # 03:30 UTC the next day, in IST
        assert booking.pickup_code in message.body
        assert licence.licence_number in message.body
    assert booking.pickup_branch.address in mail.body
    assert all(booking.pickup_code not in str(n.context) for n in Notification.objects.all())


def test_the_reminder_is_template_version_2():
    """Version 1 stays as it was sent; new reminders use version 2 (N4)."""
    due()
    remind()
    assert set(Notification.objects.values_list("template_version", flat=True)) == {2}


def test_a_delivered_booking_is_reminded_of_its_delivery_address(outbox):
    """Book.Deliver.Location: the vehicle is delivered, so the reminder never says to collect it
    at the branch (Module N4, R4 follow-up)."""
    booking = due(delivery_address="12 Demo Lane, Andheri (W)", delivery_pincode="400053")
    assert remind() == 1
    for message in outbox:
        assert "Doorstep delivery: we bring the vehicle to 12 Demo Lane, Andheri (W), 400053" in (
            message.body
        )
        assert booking.pickup_branch.address not in message.body
        assert "collect" not in message.body.lower()
        assert booking.pickup_code in message.body


def test_a_booking_is_never_reminded_twice():
    booking = due()
    assert remind() == 1
    assert remind(NOW + timedelta(minutes=5)) == 0
    assert remind(NOW + timedelta(hours=22)) == 0
    assert len(reminders(booking)) == 2


@pytest.mark.parametrize(
    "status", [S.CANCELLED, S.NO_SHOW, S.ACTIVE, S.COMPLETED, S.PENDING_PAYMENT, S.DRAFT]
)
def test_only_confirmed_bookings_are_reminded(status):
    due(status=status)
    assert remind() == 0
    assert not Notification.objects.exists()


def test_a_booking_being_handed_over_is_not_reminded():
    booking = due()
    ConditionReportFactory(booking=booking)  # Handover report recorded, not yet Active
    assert remind() == 0


@pytest.mark.parametrize(
    ("pickup_in", "reminded"),
    [
        (timedelta(hours=24), 1),  # exactly 24 hours ahead
        (timedelta(hours=24, minutes=1), 0),  # not yet
        (timedelta(minutes=1), 1),  # still before the collection
        (-timedelta(minutes=1), 0),  # the collection time has passed
    ],
)
def test_the_window_is_the_next_24_hours(pickup_in, reminded):
    due(pickup_datetime=NOW + pickup_in, confirmed_at=NOW - timedelta(days=3))
    assert remind() == reminded


def test_a_booking_confirmed_inside_the_window_is_not_reminded():
    """Proposed R3-P3: its confirmation e-mail and SMS were just sent."""
    due(pickup_datetime=NOW + timedelta(hours=20), confirmed_at=NOW - timedelta(hours=1))
    assert remind() == 0


def test_the_reminder_task_is_scheduled_every_5_minutes():
    task = PeriodicTask.objects.get(task="apps.notifications.tasks.send_pickup_reminders")
    assert task.enabled
    assert (task.interval.every, task.interval.period) == (5, "minutes")


def test_queue_sms_writes_one_row_to_the_registered_mobile_and_sends_it(outbox):
    user = UserFactory()
    notification = queue_sms(user, "otp", {"code": "x", "minutes": 10})
    notification.refresh_from_db()
    assert (notification.channel, notification.destination) == ("SMS", user.mobile_no)
    assert notification.status == Notification.Status.SENT
    assert outbox[-1].channel == "sms" and outbox[-1].recipient == user.mobile_no
