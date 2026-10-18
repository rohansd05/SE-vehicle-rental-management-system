"""Booking state machine (SRS Appendix B; handoff "State machines").

Only these transitions are legal:

- Draft -> Pending Payment (Book.Hold)
- Pending Payment -> Confirmed (Book.Done), or -> Draft (hold expires or payment fails)
- Pending Payment -> Cancelled or -> No-show: only an unpaid cash-at-collection booking
  (proposed R2-P1; not in Appendix B, see docs/traceability-booking-changes.md)
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
    Status.PENDING_PAYMENT: frozenset(
        {Status.CONFIRMED, Status.DRAFT, Status.CANCELLED, Status.NO_SHOW}  # R2-P1: cash only
    ),
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


def complete_booking(booking: Booking, by, *, request=None) -> Booking:
    """Return.Complete: Active -> Completed, recording the return time and the distance.

    Called by apps/rentals inside its return transaction, which holds the
    booking row lock and has set returned_at and distance_travelled (Module N2).
    """
    return transition(
        booking,
        Status.COMPLETED,
        actor=by,
        reason="Vehicle returned and the settlement recorded (Return.Complete).",
        request=request,
        update_fields=("returned_at", "distance_travelled"),
    )


# ─── Module R2: modify, extend, cancel, no-show (UC 4; Appendix B) ────────
# Called by bookings/services.py inside its transaction, which holds the
# booking row lock. Each guards the one source status it accepts, because
# ALLOWED_TRANSITIONS alone would also let Pending Payment -> Confirmed or
# Confirmed -> Active through.


def _require(booking: Booking, *sources: str, new: str) -> None:
    if booking.status not in sources:
        raise IllegalBookingTransition(booking.status, new)


def record_modification(booking: Booking, by, *, request=None, update_fields=()) -> Booking:
    """Book.Modify: Confirmed -> Confirmed with the new period, branch, vehicle or add-ons."""
    _require(booking, Status.CONFIRMED, new=Status.CONFIRMED)
    return transition(
        booking,
        Status.CONFIRMED,
        actor=by,
        reason="The customer modified the booking and the price was recalculated (Book.Modify).",
        request=request,
        update_fields=update_fields,
    )


def record_extension(booking: Booking, by, *, request=None, update_fields=()) -> Booking:
    """Book.Extend: Active -> Active with the later return, once the extra charge is paid."""
    _require(booking, Status.ACTIVE, new=Status.ACTIVE)
    return transition(
        booking,
        Status.ACTIVE,
        actor=by,
        reason="The customer extended the rental and paid the additional charge (Book.Extend).",
        request=request,
        update_fields=update_fields,
    )


def mark_cancelled(booking: Booking, by, *, reason: str = "", request=None) -> Booking:
    """Book.Cancel.Release: Confirmed (or an unpaid cash booking, R2-P1) -> Cancelled.

    `reason` replaces the customer's default, e.g. for an Administrator's cancellation.
    """
    if not booking.cash_on_collection:
        _require(booking, Status.CONFIRMED, new=Status.CANCELLED)
    return transition(
        booking,
        Status.CANCELLED,
        actor=by,
        reason=reason or "The customer cancelled before collection; refund per BR-8 (Book.Cancel).",
        request=request,
    )


def mark_no_show(booking: Booking, *, request=None) -> Booking:
    """Appendix B: not collected NO_SHOW_AFTER past the pickup time -> No-show (BR-8)."""
    if not booking.cash_on_collection:
        _require(booking, Status.CONFIRMED, new=Status.NO_SHOW)
    return transition(
        booking,
        Status.NO_SHOW,
        actor=None,
        reason="Not collected two hours after the pickup time (Appendix B No-show).",
        request=request,
    )
