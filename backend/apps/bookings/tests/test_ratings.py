"""Ratings (D13): constraints and the rating service."""

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.accounts.tests.factories import CustomerFactory
from apps.bookings.models import Booking, Rating
from apps.bookings.services import (
    RatingError,
    average_vehicle_rating,
    submit_rating,
    with_average_rating,
)
from apps.bookings.tests.factories import BookingFactory, RatingFactory
from apps.core.models import AuditLog
from apps.fleet.models import Vehicle

pytestmark = pytest.mark.django_db


def test_factory_creates_a_valid_rating():
    rating = RatingFactory()
    rating.full_clean()
    assert str(rating)


@pytest.mark.parametrize("field", ["vehicle_rating", "service_rating"])
@pytest.mark.parametrize("value", [0, 6])
def test_scores_must_be_one_to_five(field, value):
    with pytest.raises(IntegrityError), transaction.atomic():
        RatingFactory(**{field: value})


def test_one_rating_per_booking():
    rating = RatingFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        RatingFactory(booking=rating.booking)


class TestSubmitRating:
    def test_completed_own_booking_can_be_rated(self):
        booking = BookingFactory(status=Booking.Status.COMPLETED)
        rating = submit_rating(
            booking.customer, booking.pk, vehicle_rating=4, service_rating=5, comment="Good"
        )
        assert rating.booking == booking
        assert AuditLog.objects.filter(action="Create", entity_type="bookings.Rating").exists()

    @pytest.mark.parametrize(
        "status",
        [s for s in Booking.Status.values if s != Booking.Status.COMPLETED],
    )
    def test_only_completed_bookings(self, status):
        booking = BookingFactory(status=status)
        with pytest.raises(RatingError, match="completed"):
            submit_rating(booking.customer, booking.pk, vehicle_rating=4, service_rating=4)

    def test_only_own_bookings(self):
        booking = BookingFactory(status=Booking.Status.COMPLETED)
        with pytest.raises(RatingError, match="own"):
            submit_rating(CustomerFactory(), booking.pk, vehicle_rating=4, service_rating=4)

    def test_only_once(self):
        booking = BookingFactory(status=Booking.Status.COMPLETED)
        submit_rating(booking.customer, booking.pk, vehicle_rating=4, service_rating=4)
        with pytest.raises(RatingError, match="already"):
            submit_rating(booking.customer, booking.pk, vehicle_rating=5, service_rating=5)
        assert Rating.objects.count() == 1


def test_average_is_computed_not_stored():
    first = RatingFactory(vehicle_rating=5)
    # Completed bookings do not block the vehicle, so the same times are fine.
    booking = BookingFactory(
        vehicle=first.booking.vehicle,
        tariff=first.booking.tariff,
        status=Booking.Status.COMPLETED,
    )
    RatingFactory(booking=booking, vehicle_rating=4)
    vehicle = first.booking.vehicle
    assert average_vehicle_rating(vehicle) == Decimal("4.50")
    annotated = with_average_rating(Vehicle.objects.filter(pk=vehicle.pk)).get()
    assert Decimal(annotated.average_rating).quantize(Decimal("0.01")) == Decimal("4.50")
    assert "average_rating" not in {f.name for f in Vehicle._meta.concrete_fields}


def test_average_is_none_without_ratings():
    assert average_vehicle_rating(BookingFactory().vehicle) is None
