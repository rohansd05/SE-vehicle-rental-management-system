"""Vehicle status service: the only way a vehicle's status changes.

Implements the vehicle state machine of SRS Appendix B, Figure 4 (Fleet.Status):

- Available -> On Rent (handover) or Under Maintenance (job scheduled or started)
- On Rent -> Available (return) or Under Maintenance (flagged during the return)
- Under Maintenance -> Available (job completed and the vehicle released)
- any status -> Unsafe (Maint.Unsafe)
- Unsafe -> Available only when an Administrator clears the flag
  (BR-16, SA-3, SE-6; Administrator only per Exp 4 sequence 3, Proposed M1)
- any status -> Retired, by an Administrator, when no future booking exists
  (Fleet.Retire)

Retired is terminal (Proposed M2). Asking for the status a vehicle already has
is a no-op and writes no audit entry (Proposed M5). Every change is audited
(SE-10) with the actor, so BR-16's "the identity of that user is recorded".

Exp 3 `Vehicle.update_status()` delegates here.

Owner: Nidhi (WBS 1.4.4).
"""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.core.audit import record_audit
from apps.fleet.models import Vehicle

Status = Vehicle.Status

# Appendix B, Figure 4. A status maps to the statuses it may move to.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    Status.AVAILABLE: frozenset(
        {Status.ON_RENT, Status.UNDER_MAINTENANCE, Status.UNSAFE, Status.RETIRED}
    ),
    Status.ON_RENT: frozenset(
        {Status.AVAILABLE, Status.UNDER_MAINTENANCE, Status.UNSAFE, Status.RETIRED}
    ),
    Status.UNDER_MAINTENANCE: frozenset({Status.AVAILABLE, Status.UNSAFE, Status.RETIRED}),
    Status.UNSAFE: frozenset({Status.AVAILABLE, Status.RETIRED}),
    Status.RETIRED: frozenset(),
}


class VehicleStatusError(Exception):
    """The status change is refused; the message says why."""


class IllegalTransitionError(VehicleStatusError):
    """The state machine has no transition from the current status to the new one."""

    def __init__(self, current: str, new: str):
        self.current = current
        self.new = new
        super().__init__(f"A vehicle cannot move from {current} to {new}.")


class ActorNotPermittedError(VehicleStatusError):
    """The transition exists, but this actor may not make it (BR-16, Fleet.Retire)."""


class FutureBookingsExistError(VehicleStatusError):
    """Fleet.Retire: the vehicle still has a booking that is not over."""


def _is_administrator(actor) -> bool:
    # Branch Managers are not Administrators here (Proposed M3).
    return bool(
        actor is not None
        and getattr(actor, "is_authenticated", False)
        and actor.is_active
        and actor.role == User.Role.ADMINISTRATOR
    )


def _has_future_booking(vehicle: Vehicle) -> bool:
    """Fleet.Retire: an Active booking, or a held or Confirmed one not yet over (Proposed M4)."""
    from apps.bookings.models import Booking

    BookingStatus = Booking.Status
    return vehicle.bookings.filter(
        Q(status=BookingStatus.ACTIVE)
        | Q(
            status__in=(BookingStatus.PENDING_PAYMENT, BookingStatus.CONFIRMED),
            return_datetime__gt=timezone.now(),
        )
    ).exists()


def check_transition(vehicle: Vehicle, current: str, new: str, actor) -> None:
    """Raise a VehicleStatusError if `actor` may not move `vehicle` from `current` to `new`."""
    if new not in ALLOWED_TRANSITIONS.get(current, ()):
        raise IllegalTransitionError(current, new)
    if current == Status.UNSAFE and new == Status.AVAILABLE and not _is_administrator(actor):
        # BR-16, SA-3, SE-6, Maint.Unsafe.
        raise ActorNotPermittedError("Only an Administrator can clear an Unsafe flag (BR-16).")
    if new == Status.RETIRED:
        if not _is_administrator(actor):
            raise ActorNotPermittedError("Only an Administrator can retire a vehicle.")
        if _has_future_booking(vehicle):
            raise FutureBookingsExistError(
                "This vehicle has bookings that are not over; cancel or reassign them first."
            )


def update_status(
    vehicle: Vehicle, new_status: str, *, actor, reason: str, request=None
) -> Vehicle:
    """Move `vehicle` to `new_status` (Fleet.Status, Appendix B Figure 4).

    The vehicle row is locked for the rest of the caller's transaction, and the
    transition is checked against the status in the database, not the one on
    the instance passed in. `actor` is the User making the change, or None for
    a system action. Returns the vehicle with its new status; the instance
    passed in is updated too.
    """
    if new_status not in Status.values:
        raise IllegalTransitionError(vehicle.status, new_status)
    with transaction.atomic():
        locked = Vehicle.objects.select_for_update().get(pk=vehicle.pk)
        current = locked.status
        if current != new_status:
            check_transition(locked, current, new_status, actor)
            locked.status = new_status
            locked.save(update_fields=["status", "updated_at"])
            record_audit(
                actor,
                "Vehicle Status Changed",
                locked,
                before={"status": current},
                after={"status": new_status, "reason": reason},
                request=request,
            )
    vehicle.status = locked.status
    return locked
