"""Book.NoDouble, Book.Concurrent, Reliability-1 and BR-1, at the database level.

Every test saves straight through the ORM, with no service-layer check, so
only the PostgreSQL exclusion constraint can reject the second booking.
"""

from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction

from apps.bookings.models import Booking
from apps.bookings.tests.factories import BookingFactory

pytestmark = pytest.mark.django_db

Status = Booking.Status


def _second_booking(first: Booking, *, start, hours: int = 6, status=Status.CONFIRMED):
    return BookingFactory(
        vehicle=first.vehicle,
        tariff=first.tariff,
        pickup_datetime=start,
        return_datetime=start + timedelta(hours=hours),
        status=status,
    )


def test_overlapping_confirmed_booking_is_rejected():
    first = BookingFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        _second_booking(first, start=first.pickup_datetime + timedelta(hours=2))


def test_booking_inside_the_turnaround_buffer_is_rejected():
    """BR-1: starting 30 minutes after the previous return is inside the 60-minute buffer."""
    first = BookingFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        _second_booking(first, start=first.return_datetime + timedelta(minutes=30))


def test_booking_after_the_turnaround_buffer_is_accepted():
    """BR-1: starting exactly 60 minutes after the previous return is allowed."""
    first = BookingFactory()
    second = _second_booking(first, start=first.return_datetime + timedelta(minutes=60))
    assert second.pk is not None


def test_booking_ending_before_the_other_starts_is_accepted():
    first = BookingFactory()
    earlier = _second_booking(
        first, start=first.pickup_datetime - timedelta(hours=8), hours=7
    )  # ends 1 h before; its own buffer ends exactly at first.pickup_datetime
    assert earlier.pk is not None


@pytest.mark.parametrize(
    "status", [Status.DRAFT, Status.CANCELLED, Status.COMPLETED, Status.NO_SHOW]
)
def test_non_blocking_statuses_do_not_block(status):
    first = BookingFactory(status=status)
    second = _second_booking(first, start=first.pickup_datetime)
    assert second.pk is not None


@pytest.mark.parametrize("status", [Status.PENDING_PAYMENT, Status.CONFIRMED, Status.ACTIVE])
def test_blocking_statuses_block(status):
    """Pending Payment blocks: the 15-minute hold keeps the vehicle (Book.Hold)."""
    first = BookingFactory(status=status)
    with pytest.raises(IntegrityError), transaction.atomic():
        _second_booking(first, start=first.pickup_datetime, status=Status.PENDING_PAYMENT)


def test_a_draft_cannot_be_promoted_into_an_overlap():
    first = BookingFactory()
    draft = _second_booking(first, start=first.pickup_datetime, status=Status.DRAFT)
    draft.status = Status.PENDING_PAYMENT
    with pytest.raises(IntegrityError), transaction.atomic():
        draft.save()


def test_cancelling_releases_the_vehicle():
    """Book.Cancel.Release: a cancelled booking stops blocking at once."""
    first = BookingFactory()
    first.status = Status.CANCELLED
    first.save(update_fields=["status"])
    assert _second_booking(first, start=first.pickup_datetime).pk is not None


def test_extending_into_another_booking_is_rejected():
    """Book.Extend: the extended period must not conflict with a later booking."""
    first = BookingFactory()
    later = _second_booking(first, start=first.return_datetime + timedelta(hours=3))
    first.return_datetime = later.pickup_datetime
    with pytest.raises(IntegrityError), transaction.atomic():
        first.save(update_fields=["return_datetime"])


def test_different_vehicles_never_conflict():
    first = BookingFactory()
    other = BookingFactory(
        pickup_datetime=first.pickup_datetime, return_datetime=first.return_datetime
    )
    assert other.vehicle_id != first.vehicle_id


def test_blocked_period_is_pickup_to_return_plus_buffer():
    booking = BookingFactory()
    booking.refresh_from_db()
    assert booking.blocked_period.lower == booking.pickup_datetime
    assert booking.blocked_period.upper == booking.return_datetime + timedelta(minutes=60)
    assert booking.blocked_period.bounds == "[)"


def test_return_must_be_after_pickup():
    with pytest.raises(IntegrityError), transaction.atomic():
        BookingFactory(return_datetime=BookingFactory.pickup_datetime.function())
