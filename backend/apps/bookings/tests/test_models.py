"""Booking fields and constraints (Book.Done.Store, Book.Addons, BR-13)."""

from decimal import Decimal

import pytest
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import ProtectedError

from apps.bookings.models import Booking
from apps.bookings.tests.factories import BookingAddOnFactory, BookingFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "factory_class", [BookingFactory, BookingAddOnFactory], ids=lambda f: f.__name__
)
def test_factory_creates_a_valid_row(factory_class):
    instance = factory_class()
    instance.full_clean()
    assert instance.pk is not None
    assert str(instance)


def test_booking_status_values_match_the_handoff():
    assert Booking.Status.values == [
        "Draft",
        "Pending Payment",
        "Confirmed",
        "Active",
        "Completed",
        "Cancelled",
        "No-show",
    ]


@pytest.mark.parametrize("reference", ["VRMS-2026101-0001", "VRMS-20261010-001", "ABC"])
def test_reference_must_match_the_format(reference):
    with pytest.raises(IntegrityError), transaction.atomic():
        BookingFactory(booking_reference=reference)


def test_reference_is_unique_but_drafts_have_none():
    BookingFactory(status=Booking.Status.DRAFT, booking_reference="", pickup_code="")
    BookingFactory(status=Booking.Status.DRAFT, booking_reference="", pickup_code="")
    booking = BookingFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        BookingFactory(booking_reference=booking.booking_reference)


@pytest.mark.parametrize("code", ["12345", "1234567", "12a456"])
def test_pickup_code_is_six_digits(code):
    # Too long fails the column length (DataError); wrong digits fail the check.
    with pytest.raises(DatabaseError), transaction.atomic():
        BookingFactory(pickup_code=code)


def test_pickup_code_keeps_leading_zeros():
    booking = BookingFactory(pickup_code="000042")
    booking.refresh_from_db()
    assert booking.pickup_code == "000042"


def test_add_on_rate_is_a_snapshot():
    """BR-13: changing the published add-on rate leaves the booking unchanged."""
    line = BookingAddOnFactory(add_on__daily_rate=Decimal("150.00"))
    line.add_on.daily_rate = Decimal("999.00")
    line.add_on.save()
    line.refresh_from_db()
    assert line.daily_rate == Decimal("150.00")


def test_an_add_on_appears_once_per_booking():
    line = BookingAddOnFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        BookingAddOnFactory(booking=line.booking, add_on=line.add_on)


def test_vehicle_and_customer_of_a_booking_cannot_be_deleted():
    booking = BookingFactory()
    with pytest.raises(ProtectedError):
        booking.vehicle.delete()
    with pytest.raises(ProtectedError):
        booking.customer.delete()
