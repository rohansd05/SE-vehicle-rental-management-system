"""Booking state machine (SRS Appendix B; handoff "State machines").

Only these transitions are legal:

- Draft -> Pending Payment (Book.Hold)
- Pending Payment -> Confirmed (Book.Done), or -> Draft (hold expires or payment fails)
- Confirmed -> Confirmed (modify), -> Active, -> Cancelled or -> No-show
- Active -> Active (extend) or -> Completed

Every status change of a booking goes through transition(), which saves the
new status and writes an audit entry (SE-10).
"""

from django.utils import timezone

from apps.core.audit import record_audit

from .models import Booking

Status = Booking.Status

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    Status.DRAFT: frozenset({Status.PENDING_PAYMENT}),
    Status.PENDING_PAYMENT: frozenset({Status.CONFIRMED, Status.DRAFT}),
    Status.CONFIRMED: frozenset(
        {Status.CONFIRMED, Status.ACTIVE, Status.CANCELLED, Status.NO_SHOW}
    ),
    Status.ACTIVE: frozenset({Status.ACTIVE, Status.COMPLETED}),
    Status.COMPLETED: frozenset(),
    Status.CANCELLED: frozenset(),
    Status.NO_SHOW: frozenset(),
}


class IllegalBookingTransition(Exception):
    def __init__(self, current: str, new: str):
        self.current = current
        self.new = new
        super().__init__(f"A booking cannot move from {current} to {new}.")


def check_transition(current: str, new: str) -> None:
    if new not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise IllegalBookingTransition(current, new)


def transition(
    booking: Booking,
    new_status: str,
    *,
    actor,
    reason: str,
    request=None,
    update_fields: tuple[str, ...] = (),
) -> Booking:
    """Move `booking` to `new_status`, saving it with any other `update_fields` set by the caller.

    The caller holds the booking row lock (select_for_update) for the
    transaction, so the status checked here is the one in the database.
    """
    current = booking.status
    check_transition(current, new_status)
    booking.status = new_status
    booking.save(update_fields=["status", "updated_at", *update_fields])
    record_audit(
        actor,
        "Booking Status Changed",
        booking,
        before={"status": current},
        after={"status": new_status, "reason": reason},
        request=request,
    )
    return booking


def activate_booking(booking: Booking, by, *, request=None) -> Booking:
    """Handover.Activate: Confirmed -> Active, recording the actual handover time.

    Called by apps/rentals inside its handover transaction, which holds the
    booking row lock (Module N1).
    """
    booking.handed_over_at = timezone.now()
    return transition(
        booking,
        Status.ACTIVE,
        actor=by,
        reason="Vehicle handed over and the condition report signed (Handover.Activate).",
        request=request,
        update_fields=("handed_over_at",),
    )
