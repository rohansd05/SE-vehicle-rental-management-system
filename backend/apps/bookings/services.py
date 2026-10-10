"""Bookings business logic. Views stay thin; every write is audited (SE-10).

Phase 1B holds the rating service (D13). The booking lifecycle follows in
Phase 3.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Avg, DecimalField, QuerySet

from apps.core.audit import record_audit, snapshot

from .models import Booking, Rating

_AVERAGE = DecimalField(max_digits=4, decimal_places=2)


class RatingError(Exception):
    """The rating is not allowed; the message says why."""


@transaction.atomic
def submit_rating(
    customer,
    booking_id: int,
    *,
    vehicle_rating: int,
    service_rating: int,
    comment: str = "",
    request=None,
) -> Rating:
    """D13: a customer rates their own Completed booking, once."""
    booking = Booking.objects.select_for_update().get(pk=booking_id)
    if booking.customer_id != customer.pk:
        raise RatingError("You can rate only your own bookings.")
    if booking.status != Booking.Status.COMPLETED:
        raise RatingError("Only a completed booking can be rated.")
    if Rating.objects.filter(booking=booking).exists():
        raise RatingError("This booking has already been rated.")
    rating = Rating.objects.create(
        booking=booking,
        vehicle_rating=vehicle_rating,
        service_rating=service_rating,
        comment=comment,
    )
    record_audit(customer.user, "Create", rating, after=snapshot(rating), request=request)
    return rating


def average_vehicle_rating(vehicle) -> Decimal | None:
    """Search.Detail: the vehicle's average rating, computed and never stored (D13)."""
    value = Rating.objects.filter(booking__vehicle=vehicle).aggregate(
        average=Avg("vehicle_rating", output_field=_AVERAGE)
    )["average"]
    return None if value is None else Decimal(value).quantize(Decimal("0.01"), ROUND_HALF_UP)


def with_average_rating(vehicles: QuerySet) -> QuerySet:
    """Annotate `average_rating` for Search.Filter (minimum rating) and sorting."""
    return vehicles.annotate(
        average_rating=Avg("bookings__rating__vehicle_rating", output_field=_AVERAGE)
    )
