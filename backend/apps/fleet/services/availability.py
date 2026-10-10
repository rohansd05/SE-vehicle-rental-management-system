"""Vehicle availability (Search.Available, BR-1, BR-5; Exp 3 Vehicle.check_availability()).

A vehicle is available for a requested period only if (Search.Available):

- its status allows a handover, which the Appendix B state machine in
  fleet/services/status.py permits only from Available; so Under Maintenance,
  Unsafe, On Rent and Retired vehicles never appear (Fleet.Retire);
- no booking that holds the vehicle overlaps the period plus the 60-minute
  turnaround buffer (BR-1). "Holds" means Pending Payment, Confirmed or
  Active: Search.Available names Confirmed and Active, and Book.Hold adds the
  15-minute payment hold, which "shall not be offered to any other
  customer". The overlap test is the one the booking exclusion constraint
  applies, so search never offers what the database would refuse;
- no Scheduled or In Progress maintenance window overlaps the period;
- the pickup is on or after its availability date (Fleet.Add, 3.7.2).

Requested periods follow BR-5 (4 hours to 30 days).

Owner: Rohan (CLAUDE.md ownership; was WBS 1.4.2).
"""

from datetime import datetime

from django.conf import settings
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.db.models import QuerySet
from django.utils import timezone

from apps.fleet.models import Branch, Vehicle, VehicleCategory
from apps.fleet.services.status import ALLOWED_TRANSITIONS


class RentalPeriodError(ValueError):
    """The requested period breaks BR-5 or is not a usable period.

    `field` names the request field the message belongs to.
    """

    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(message)


def bookable_statuses() -> frozenset[str]:
    """Search.Available: the statuses from which the state machine allows a handover.

    Read from the status service's transition table rather than restated, so
    the two never disagree. Today this is {Available}.
    """
    return frozenset(
        status
        for status, targets in ALLOWED_TRANSITIONS.items()
        if Vehicle.Status.ON_RENT in targets
    )


def check_period(pickup: datetime, return_: datetime, *, now: datetime | None = None) -> None:
    """Raise RentalPeriodError unless [pickup, return_) is a period that can be booked.

    BR-5 / Book.Period.Limits: at least RENTAL_PERIOD_MINIMUM and at most
    RENTAL_PERIOD_MAXIMUM. The pickup must also be in the future (Proposed S1:
    the SRS does not say so, but no booking can start in the past).
    """
    now = now or timezone.now()
    if pickup <= now:
        raise RentalPeriodError("pickup_datetime", "Choose a pickup time in the future.")
    if return_ <= pickup:
        raise RentalPeriodError("return_datetime", "The return must be after the pickup.")
    length = return_ - pickup
    if length < settings.RENTAL_PERIOD_MINIMUM:
        hours = int(settings.RENTAL_PERIOD_MINIMUM.total_seconds() // 3600)
        raise RentalPeriodError(
            "return_datetime", f"A rental lasts at least {hours} hours (BR-5)."
        )
    if length > settings.RENTAL_PERIOD_MAXIMUM:
        raise RentalPeriodError(
            "return_datetime",
            f"A rental lasts at most {settings.RENTAL_PERIOD_MAXIMUM.days} days (BR-5).",
        )


def requested_block(pickup: datetime, return_: datetime) -> DateTimeTZRange:
    """[pickup, return + turnaround buffer): what a booking for this period would block (BR-1).

    The same range Booking.compute_blocked_period() stores, so the overlap
    test below matches the exclusion constraint exactly.
    """
    return DateTimeTZRange(pickup, return_ + settings.BOOKING_TURNAROUND_BUFFER, "[)")


def _unavailable_ids(pickup: datetime, return_: datetime):
    """Ids of vehicles held by a booking or a maintenance window during the period."""
    from apps.bookings.models import Booking
    from apps.maintenance.services import blocked_vehicle_ids

    booked = Booking.objects.filter(
        status__in=Booking.BLOCKING_STATUSES,
        blocked_period__overlap=requested_block(pickup, return_),
    ).values("vehicle_id")
    return booked, blocked_vehicle_ids(pickup, return_)


def available_vehicles(
    *,
    branch: Branch,
    pickup: datetime,
    return_: datetime,
    category: VehicleCategory | None = None,
) -> QuerySet[Vehicle]:
    """Search.Available: vehicles at `branch` that can be booked for the whole period.

    Raises RentalPeriodError for a period BR-5 does not allow.
    """
    check_period(pickup, return_)
    booked, in_workshop = _unavailable_ids(pickup, return_)
    vehicles = (
        Vehicle.objects.filter(
            home_branch=branch,
            status__in=bookable_statuses(),
            available_from__lte=timezone.localdate(pickup),
        )
        .exclude(pk__in=booked)
        .exclude(pk__in=in_workshop)
    )
    if category is not None:
        vehicles = vehicles.filter(category=category)
    return vehicles


def is_available(vehicle: Vehicle, pickup: datetime, return_: datetime) -> bool:
    """Exp 3 Vehicle.check_availability(): the same rules for one vehicle.

    The period itself is not checked here; call check_period first. A True
    answer is advice only: the exclusion constraint decides at confirmation
    (Book.NoDouble).
    """
    if vehicle.status not in bookable_statuses():
        return False
    if timezone.localdate(pickup) < vehicle.available_from:
        return False
    booked, in_workshop = _unavailable_ids(pickup, return_)
    return vehicle.pk not in in_workshop and not booked.filter(vehicle_id=vehicle.pk).exists()
