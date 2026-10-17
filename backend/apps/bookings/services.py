"""Bookings business logic. Views stay thin; every write is audited (SE-10).

- Ratings (D13).
- Module R2, Exp 2 UC 4 Modify / Cancel Booking and Book.Extend: Exp 3
  Booking.modify_booking(), cancel_booking() and extend_booking(), and the
  Appendix B No-show (declare_no_shows(), a Celery Beat task). Each action
  has a quote that shows the money first; the action takes the amounts the
  customer confirmed and refuses (409) if they changed meanwhile. Money moves
  only through apps/payments/services.py (R1, docs/payments-api.md); status
  changes only through states.py; notifications only through Celery.

Book Vehicle (create, hold, pay) is in lifecycle.py.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Avg, DecimalField, Q, QuerySet
from django.utils import timezone

from apps.accounts.models import Customer, Licence, User
from apps.core.audit import record_audit, snapshot
from apps.fleet.models import Branch, Vehicle
from apps.fleet.services.availability import (
    available_vehicles,
    check_period,
    is_available,
    requested_block,
)
from apps.maintenance.services import blocked_vehicle_ids
from apps.notifications.services import queue_email
from apps.payments import services as payments
from apps.payments.models import Payment, RefundRequest
from apps.pricing.models import AddOn
from apps.pricing.services import PricingError, Quote, resolve_add_ons
from apps.rentals.models import ConditionReport

from . import states
from .eligibility import licence_is_valid
from .lifecycle import (
    ONLINE,
    UNAVAILABLE,
    BookingConflictError,
    BookingError,
    InvalidBookingStateError,
    PaymentDeclinedError,
    VehicleUnavailableError,
    _refuse_delivery,
    booking_quote,
)
from .models import Booking, BookingAddOn, Rating

logger = logging.getLogger(__name__)

_AVERAGE = DecimalField(max_digits=4, decimal_places=2)
ZERO = Decimal("0.00")
CENT = Decimal("0.01")
Status = Booking.Status


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


# ═══ Module R2: Modify / Cancel / Extend booking and No-show (UC 4) ══════


class ModificationCutoffError(BookingError):
    """Exp 2 UC 4 extension 2a: less than MODIFICATION_CUTOFF before the pickup time."""

    status = 409
    code = "modification_cutoff"


# ─── Shared steps ─────────────────────────────────────────────────────────


def refund_percent(notice: timedelta) -> Decimal:
    """BR-8: the share of the rental refunded for this much notice before collection."""
    if notice >= settings.CANCELLATION_FULL_REFUND_NOTICE:
        return settings.CANCELLATION_REFUND_PERCENT_FULL
    if notice >= settings.CANCELLATION_PARTIAL_REFUND_NOTICE:
        return settings.CANCELLATION_REFUND_PERCENT_PARTIAL
    return settings.CANCELLATION_REFUND_PERCENT_LATE


def _share(amount: Decimal, percent: Decimal) -> Decimal:
    return (amount * percent / 100).quantize(CENT, ROUND_HALF_UP)


def _money(amount: Decimal) -> str:
    return f"{settings.CURRENCY} {amount:,.2f}"


def _local(value: datetime) -> str:
    return f"{timezone.localtime(value):%d %b %Y %H:%M}"


def _customer_booking(customer: Customer, booking_id: int, *, lock: bool) -> Booking:
    bookings = Booking.objects.select_related(
        "vehicle__category", "tariff", "discount_code", "pickup_branch", "customer__user"
    )
    if lock:  # the transaction holds the booking row (Book.Status: one change at a time)
        bookings = bookings.select_for_update(of=("self",))
    return bookings.get(pk=booking_id, customer=customer)


def _lock_vehicle(vehicle_id: int) -> Vehicle:
    """BR-1: changes onto one vehicle queue here, as Book.Create does (Reliability-1)."""
    return Vehicle.objects.select_for_update().select_related("category").get(pk=vehicle_id)


def _handed_over(booking: Booking) -> bool:
    """Handover.Activate stores a handover condition report (Module N1)."""
    return booking.condition_reports.filter(
        report_type=ConditionReport.ReportType.HANDOVER
    ).exists()


def _deposit_payment(booking: Booking) -> Payment | None:
    return Payment.objects.filter(
        booking=booking,
        original_payment__isnull=True,
        status=Payment.Status.SUCCEEDED,
        purpose=Payment.Purpose.SECURITY_DEPOSIT,
    ).first()


def _rental_parts(booking: Booking, amount: Decimal) -> list[tuple[Payment, Decimal]]:
    """Split a rental refund over the booking's rental payments, newest first.

    A booking paid at Book.Done and again for a modification has two; each
    refund goes back to its own instrument (Pay.Refund).
    """
    rentals = Payment.objects.filter(
        booking=booking,
        original_payment__isnull=True,
        status=Payment.Status.SUCCEEDED,
        purpose=Payment.Purpose.RENTAL,
    ).order_by("-pk")
    parts = []
    for payment in rentals:
        part = min(amount, payments.refundable_amount(payment))
        if part > 0:
            parts.append((payment, part))
            amount -= part
    return parts


def _rental_paid(booking: Booking) -> Decimal:
    """The rental amount BR-8 applies to: the current price, at most what is still refundable."""
    refundable = sum((part for _, part in _rental_parts(booking, booking.total_amount)), ZERO)
    return min(booking.total_amount, refundable)


def _refund_rental(booking, amount, reason, actor, *, key, request) -> None:
    for payment, part in _rental_parts(booking, amount):
        payments.refund_payment(
            payment, part, reason, actor, idempotency_key=f"{key}:{payment.pk}", request=request
        )


def _settle(booking: Booking, rental_refund: Decimal, actor, *, key: str, reason: str, request):
    """Book.Cancel.Release, No-show: capture what was authorised, then refund the rental
    share (BR-8) and the whole deposit through R1's services. A refund above
    REFUND_AUTO_APPROVAL_LIMIT waits in the /app/refunds queue (UC 13); a cash
    refund waits on the branch's Cash desk."""
    payments.capture_charges(booking, [], actor, idempotency_key=key, request=request)
    _refund_rental(booking, rental_refund, reason, actor, key=key, request=request)
    payments.refund_deposit(booking, booking.security_deposit, actor, request=request)


def _audit_release(booking: Booking, actor, request) -> None:
    """Book.Cancel.Release: the blocked period no longer holds the vehicle (BR-1)."""
    record_audit(
        actor,
        "Vehicle Released From Booking",
        booking.vehicle,
        after={"booking": booking.booking_reference, "booking_status": booking.status},
        request=request,
    )


def _check_licence(customer: Customer, vehicle_type: str, return_: datetime) -> None:
    """BR-2: the licence stays valid for the whole changed or extended period."""
    licence_is_valid(Licence.objects.filter(customer=customer).first(), vehicle_type, return_)


def _held_by_others(booking: Booking, vehicle: Vehicle, pickup, return_) -> bool:
    """BR-1: another booking, or a maintenance window, holds `vehicle` within
    [pickup, return_ + turnaround buffer). The booking's own block does not count."""
    others = Booking.objects.filter(
        vehicle=vehicle,
        status__in=Booking.BLOCKING_STATUSES,
        blocked_period__overlap=requested_block(pickup, return_),
    ).exclude(pk=booking.pk)
    return others.exists() or vehicle.pk in blocked_vehicle_ids(pickup, return_)


def _save_change(booking: Booking, record, actor, request, update_fields) -> None:
    """Save through the state machine; the exclusion constraint is the last word (Book.NoDouble)."""
    try:
        with transaction.atomic():
            record(booking, actor, request=request, update_fields=update_fields)
    except IntegrityError as exc:
        if "bookings_no_overlapping_vehicle_blocks" in str(exc):
            raise VehicleUnavailableError(UNAVAILABLE) from exc
        raise  # pragma: no cover - any other integrity error is a bug


def _charge_extra(booking, amount, *, key, actor, request, payment) -> payments.AuthorizationResult:
    """Book.Modify.Price / Book.Extend: the extra amount goes through Payment.authorize()."""
    if not payment.get("payment_token"):
        raise BookingError(
            "Choose how to pay the extra amount.", code="payment_required", field="payment_token"
        )
    method = payment.get("method", "card")
    return payments.authorize(
        booking,
        rental_amount=amount,
        deposit_amount=ZERO,
        payment_token=payment["payment_token"],
        idempotency_key=key,
        actor=actor,
        request=request,
        channel=payment.get("channel", "") if method == ONLINE else "",
        upi_id=payment.get("upi_id", ""),
    )


def _book_extra(booking, auth, amount, note, actor, request) -> None:
    """Pay.Ledger: the Charge entry; Pay.Invoice: a debit note on the issued invoice."""
    payments.record_booking_ledger(booking, auth, actor=actor, request=request, note=note)
    invoice = getattr(booking, "invoice", None)
    if invoice is not None:
        payments.issue_debit_note(invoice, amount, note, issued_by=actor, request=request)


def _notify(booking: Booking, template: str, *, branches=(), **extra) -> None:
    """Notify.Booking (customer) and, where UC 4 step 6 says so, the branch; sent by Celery."""
    vehicle = booking.vehicle
    context = {
        "name": booking.customer.user.name,
        "reference": booking.booking_reference,
        "vehicle": f"{vehicle.brand} {vehicle.model}",
        "registration_no": vehicle.registration_no,
        "branch": booking.pickup_branch.branch_name,
        "pickup": _local(booking.pickup_datetime),
        "return_at": _local(booking.return_datetime),
        "status": booking.status,
        **extra,
    }
    queue_email(booking.customer.user, template, context, booking=booking)
    staff = User.objects.filter(
        role=User.Role.BRANCH_STAFF, is_active=True, branch_staff__branch_id__in=branches
    )
    for user in staff:
        queue_email(user, "booking_branch_update", {**context, "name": user.name}, booking=booking)


# ─── Cancel (Book.Cancel, Book.Cancel.Release; Booking.cancel_booking()) ──


@dataclass(frozen=True)
class CancellationQuote:
    """Book.Cancel: "display the refund computed per BR-8" before the customer confirms."""

    notice_hours: int
    refund_percent: Decimal
    rental_amount: Decimal  # what the BR-8 percentage applies to
    rental_refund: Decimal
    deposit_refund: Decimal  # BR-8: always refunded in full on cancellation
    total_refund: Decimal
    awaits_approval: bool  # UC 13: a part above REFUND_AUTO_APPROVAL_LIMIT


def _check_cancellable(booking: Booking) -> None:
    unpaid_cash = booking.status == Status.PENDING_PAYMENT and booking.cash_on_collection
    if booking.status != Status.CONFIRMED and not unpaid_cash:
        raise InvalidBookingStateError(
            "Only a confirmed booking that has not been collected can be cancelled."
        )
    if _handed_over(booking):
        raise InvalidBookingStateError("The vehicle has been handed over; it can't be cancelled.")


def _cancellation_quote(booking: Booking) -> CancellationQuote:
    notice = booking.pickup_datetime - timezone.now()
    percent = refund_percent(notice)
    deposit = _deposit_payment(booking)
    if deposit is None:  # R2-P1: an unpaid cash booking; nothing was paid
        rental = rental_refund = deposit_refund = ZERO
        parts = []
    else:
        rental = _rental_paid(booking)
        rental_refund = _share(rental, percent)
        parts = [part for _, part in _rental_parts(booking, rental_refund)]
        deposit_refund = booking.security_deposit
    limit = settings.REFUND_AUTO_APPROVAL_LIMIT
    return CancellationQuote(
        notice_hours=max(int(notice.total_seconds() // 3600), 0),
        refund_percent=percent,
        rental_amount=rental,
        rental_refund=rental_refund,
        deposit_refund=deposit_refund,
        total_refund=rental_refund + deposit_refund,
        awaits_approval=any(part > limit for part in [*parts, deposit_refund]),
    )


def cancellation_quote(customer: Customer, booking_id: int) -> CancellationQuote:
    """Exp 2 UC 4 step 4: the refund due under the cancellation policy."""
    booking = _customer_booking(customer, booking_id, lock=False)
    _check_cancellable(booking)
    return _cancellation_quote(booking)


def cancel_booking(
    customer: Customer, booking_id: int, *, expected_refund: Decimal, request=None
) -> Booking:
    """Exp 3 Booking.cancel_booking(): Book.Cancel and Book.Cancel.Release in one transaction.

    The vehicle is released, the booking Cancelled, the refund initiated and
    the customer and the branch notified. `expected_refund` is the total the
    customer confirmed; if BR-8 now gives another amount (the notice crossed
    48 or 12 hours), nothing changes and 409 `refund_changed` says so.
    """
    actor = customer.user
    with transaction.atomic():
        booking = _customer_booking(customer, booking_id, lock=True)
        if booking.status == Status.CANCELLED:
            return booking  # a repeated confirmation changes nothing
        _check_cancellable(booking)
        quote = _cancellation_quote(booking)
        if quote.total_refund != expected_refund:
            raise BookingConflictError(
                f"The refund is now {_money(quote.total_refund)}. Check it and confirm again.",
                code="refund_changed",
            )
        paid = quote.deposit_refund > 0
        states.mark_cancelled(booking, actor, request=request)
        _audit_release(booking, actor, request)
        if paid:
            _settle(
                booking,
                quote.rental_refund,
                actor,
                key=f"cancel-{booking.pk}",
                reason=(
                    f"Cancelled {quote.notice_hours} hours before collection: "
                    f"{quote.refund_percent:.0f}% of the rental refunded (BR-8)."
                ),
                request=request,
            )
        refund = (
            f"We are refunding {_money(quote.total_refund)}: {_money(quote.rental_refund)} of "
            f"the rental and the deposit of {_money(quote.deposit_refund)}."
            if paid
            else "Nothing was paid, so there is nothing to refund."
        )
        _notify(booking, "booking_cancelled", branches=[booking.pickup_branch_id], refund=refund)
    return booking


# ─── Modify (Book.Modify, Book.Modify.Price; Booking.modify_booking()) ────


@dataclass(frozen=True)
class ModificationQuote:
    """Exp 2 UC 4 step 3: the new price, what it costs or refunds, and (3a) alternatives."""

    price: Quote
    vehicle: Vehicle
    vehicle_free: bool
    alternatives: list[Vehicle]  # 3a: same category, same tariff, free at the branch
    previous_total: Decimal
    new_total: Decimal
    extra_charge: Decimal  # charged immediately (Book.Modify.Price)
    refund_percent: Decimal  # BR-8 on the excess
    refund_amount: Decimal


@dataclass(frozen=True)
class Modification:
    pickup: datetime
    return_: datetime
    branch: Branch
    add_ons: list[tuple[int, int]]  # (add-on id, quantity), Book.Addons
    vehicle: Vehicle | None = None  # 3a: an alternative of the same category


def _check_modifiable(booking: Booking) -> None:
    if booking.status != Status.CONFIRMED:
        raise InvalidBookingStateError(
            "Only a confirmed booking that has not been collected can be changed."
        )
    if _handed_over(booking):
        raise InvalidBookingStateError("The vehicle has been handed over; it can't be changed.")
    if booking.pickup_datetime - timezone.now() < settings.MODIFICATION_CUTOFF:
        hours = int(settings.MODIFICATION_CUTOFF.total_seconds() // 3600)
        raise ModificationCutoffError(  # UC 4 extension 2a: "states the cut-off"
            f"A booking can be changed until {hours} hours before the pickup time "
            f"({_local(booking.pickup_datetime)}). You can still cancel it."
        )


def _chosen_add_ons(booking: Booking, requested, vehicle_type) -> list[tuple[AddOn, int]]:
    """Book.Addons: kept add-ons keep their booked rate (BR-13); new ones are checked and
    priced at today's published rate (BR-7)."""
    ids = [add_on_id for add_on_id, _ in requested]
    if len(ids) != len(set(ids)):
        raise BookingError("Choose each add-on only once.", field="add_ons")
    booked = {line.add_on_id: line for line in booking.add_ons.select_related("add_on")}
    new = [(add_on_id, quantity) for add_on_id, quantity in requested if add_on_id not in booked]
    _refuse_delivery([add_on_id for add_on_id, _ in new])
    try:
        fresh = {add_on.pk: add_on for add_on, _ in resolve_add_ons(new, vehicle_type)}
    except PricingError as exc:
        raise BookingError(str(exc), code="pricing", field=exc.field) from exc
    chosen = []
    for add_on_id, quantity in requested:
        line = booked.get(add_on_id)
        add_on = (
            AddOn(pk=add_on_id, name=line.add_on.name, daily_rate=line.daily_rate)
            if line
            else fresh[add_on_id]
        )
        chosen.append((add_on, quantity))
    return chosen


def _vehicle_free(booking: Booking, vehicle: Vehicle, change: Modification) -> bool:
    """Book.Modify "the vehicle is free for the new period" (BR-1 buffer included).

    Proposed R2-P3: a vehicle is collected at the branch it is based at, so a
    new pickup branch needs a vehicle of that branch (UC 4 3a offers one).
    """
    if vehicle.home_branch_id != change.branch.pk:
        return False
    if vehicle.pk != booking.vehicle_id:  # Vehicle.check_availability(), as search does
        return is_available(vehicle, change.pickup, change.return_)
    return not _held_by_others(booking, vehicle, change.pickup, change.return_)


def _plan(booking: Booking, vehicle: Vehicle, change: Modification):
    check_period(change.pickup, change.return_)  # BR-5
    if vehicle.category_id != booking.vehicle.category_id:
        raise BookingError(
            "Choose a vehicle of the same category, at the same tariff.", field="vehicle"
        )
    vehicle_type = vehicle.category.vehicle_type
    _check_licence(booking.customer, vehicle_type, change.return_)
    chosen = _chosen_add_ons(booking, change.add_ons, vehicle_type)
    price = booking_quote(  # Tariff.calculate_price() at the booking's own tariff (BR-13)
        booking, pickup=change.pickup, return_=change.return_, add_ons=chosen
    )
    free = _vehicle_free(booking, vehicle, change)
    alternatives = []
    if not free:  # UC 4 extension 3a
        alternatives = list(
            available_vehicles(
                branch=change.branch,
                pickup=change.pickup,
                return_=change.return_,
                category=booking.vehicle.category,
            )
            .exclude(pk__in=[booking.vehicle_id, vehicle.pk])
            .select_related("category")
            .order_by("registration_no")
        )
    difference = price.total_payable - booking.total_amount
    percent = refund_percent(booking.pickup_datetime - timezone.now())
    refund = _share(min(-difference, _rental_paid(booking)), percent) if difference < 0 else ZERO
    quote = ModificationQuote(
        price=price,
        vehicle=vehicle,
        vehicle_free=free,
        alternatives=alternatives,
        previous_total=booking.total_amount,
        new_total=price.total_payable,
        extra_charge=max(difference, ZERO),
        refund_percent=percent,
        refund_amount=refund,
    )
    return quote, chosen


def modification_quote(
    customer: Customer, booking_id: int, change: Modification
) -> ModificationQuote:
    """Exp 2 UC 4 step 3: check the vehicle is free and recalculate the price; nothing is saved."""
    booking = _customer_booking(customer, booking_id, lock=False)
    _check_modifiable(booking)
    return _plan(booking, change.vehicle or booking.vehicle, change)[0]


def _unchanged(booking: Booking, vehicle: Vehicle, change: Modification) -> bool:
    booked = dict(booking.add_ons.values_list("add_on_id", "quantity"))
    return (
        booking.pickup_datetime == change.pickup
        and booking.return_datetime == change.return_
        and booking.pickup_branch_id == change.branch.pk
        and booking.vehicle_id == vehicle.pk
        and booked == dict(change.add_ons)
    )


def _details(booking: Booking) -> dict:
    """What Book.Modify may change, for the audit entry's before and after (SE-10)."""
    return {
        "pickup_datetime": booking.pickup_datetime.isoformat(),
        "return_datetime": booking.return_datetime.isoformat(),
        "pickup_branch": booking.pickup_branch_id,
        "vehicle": booking.vehicle_id,
        "add_ons": dict(booking.add_ons.values_list("add_on_id", "quantity")),
        "total_amount": str(booking.total_amount),
    }


def _store_add_ons(booking: Booking, chosen: list[tuple[AddOn, int]]) -> None:
    booking.add_ons.exclude(add_on_id__in=[add_on.pk for add_on, _ in chosen]).delete()
    for add_on, quantity in chosen:
        BookingAddOn.objects.update_or_create(
            booking=booking,
            add_on_id=add_on.pk,
            defaults={"quantity": quantity, "daily_rate": add_on.daily_rate},
        )


def modify_booking(
    customer: Customer,
    booking_id: int,
    change: Modification,
    *,
    expected_charge: Decimal,
    expected_refund: Decimal,
    idempotency_key: str,
    payment: dict | None = None,
    request=None,
) -> Booking:
    """Exp 3 Booking.modify_booking(): Book.Modify and Book.Modify.Price.

    Only a Confirmed booking, at least MODIFICATION_CUTOFF before pickup, onto
    a vehicle free for the new period. The price is recalculated; an extra
    amount is authorised at once through the pay flow (`payment`: method,
    payment_token, channel, upi_id), an excess is refunded under BR-8. The
    same `idempotency_key` never charges or refunds twice (Pay.Idempotent).
    """
    actor = customer.user
    key = f"modify-{idempotency_key}"
    outcome: BookingError | None = None
    with transaction.atomic():
        booking = _customer_booking(customer, booking_id, lock=True)
        previous = payments.previous_authorization(booking, key)
        if (previous is not None and previous.success) or RefundRequest.objects.filter(
            original_payment__booking=booking, idempotency_key__startswith=f"{key}:"
        ).exists():
            return booking  # Pay.Idempotent: this change was already made
        _check_modifiable(booking)
        vehicle = _lock_vehicle((change.vehicle or booking.vehicle).pk)
        if _unchanged(booking, vehicle, change):
            return booking
        quote, chosen = _plan(booking, vehicle, change)
        if not quote.vehicle_free:
            raise VehicleUnavailableError(
                "This vehicle is not free for the new period. Choose one of the other vehicles "
                "offered, or other dates."
            )
        if (quote.extra_charge, quote.refund_amount) != (expected_charge, expected_refund):
            raise BookingConflictError(
                "The price of this change has changed. Check it and confirm again.",
                code="price_changed",
            )
        before = _details(booking)
        note = (
            f"Booking changed: {_local(change.pickup)} to {_local(change.return_)} "
            "(Book.Modify.Price)"
        )
        auth = None
        if quote.extra_charge > 0:
            auth = _charge_extra(
                booking,
                quote.extra_charge,
                key=key,
                actor=actor,
                request=request,
                payment=payment or {},
            )
            if not auth.success:  # the declined attempt stays recorded; nothing changes
                outcome = PaymentDeclinedError(f"Your payment was declined: {auth.message}")
        if outcome is None:
            booking.pickup_datetime, booking.return_datetime = change.pickup, change.return_
            booking.pickup_branch, booking.vehicle = change.branch, vehicle
            booking.total_amount = quote.new_total
            _save_change(
                booking,
                states.record_modification,
                actor,
                request,
                ("pickup_datetime", "return_datetime", "pickup_branch", "vehicle", "total_amount"),
            )
            _store_add_ons(booking, chosen)
            if auth is not None:
                _book_extra(booking, auth, quote.extra_charge, note, actor, request)
            elif quote.refund_amount > 0:  # Book.Modify.Price: the excess under BR-8
                _refund_rental(
                    booking,
                    quote.refund_amount,
                    f"Booking changed to a lower price: {quote.refund_percent:.0f}% of the "
                    "difference refunded (BR-8).",
                    actor,
                    key=key,
                    request=request,
                )
            record_audit(
                actor,
                "Booking Modified",
                booking,
                before=before,
                after=_details(booking),
                request=request,
            )
            money = (
                f"We have charged the extra {_money(quote.extra_charge)}."
                if quote.extra_charge
                else f"We are refunding {_money(quote.refund_amount)}."
                if quote.refund_amount
                else "The price is unchanged."
            )
            _notify(
                booking,
                "booking_modified",
                branches={before["pickup_branch"], booking.pickup_branch_id},
                money=money,
            )
    if outcome is not None:
        raise outcome
    return booking


# ─── Extend (Book.Extend; Booking.extend_booking()) ───────────────────────


@dataclass(frozen=True)
class ExtensionQuote:
    """Book.Extend: the additional charge, collected before the extension takes effect."""

    price: Quote
    return_datetime: datetime
    previous_total: Decimal
    extra_charge: Decimal


def _plan_extension(booking: Booking, return_: datetime) -> ExtensionQuote:
    if booking.status != Status.ACTIVE:
        raise InvalidBookingStateError("Only a rental in progress can be extended.")
    if return_ <= max(booking.return_datetime, timezone.now()):
        raise BookingError(
            "Choose a return time later than the current one, in the future.",
            field="return_datetime",
        )
    if return_ - booking.pickup_datetime > settings.RENTAL_PERIOD_MAXIMUM:
        raise BookingError(
            f"A rental lasts at most {settings.RENTAL_PERIOD_MAXIMUM.days} days, including "
            "extensions (BR-5).",
            field="return_datetime",
        )
    _check_licence(booking.customer, booking.vehicle.category.vehicle_type, return_)
    if _held_by_others(booking, booking.vehicle, booking.pickup_datetime, return_):
        raise VehicleUnavailableError(
            "Another booking of this vehicle starts before the new return time, so the rental "
            "can't be extended that far."
        )
    price = booking_quote(booking, return_=return_)  # BR-6 on the whole period, BR-13 tariff
    return ExtensionQuote(
        price=price,
        return_datetime=return_,
        previous_total=booking.total_amount,
        extra_charge=max(price.total_payable - booking.total_amount, ZERO),
    )


def extension_quote(customer: Customer, booking_id: int, return_: datetime) -> ExtensionQuote:
    """Book.Extend: quote the extra charge; nothing is saved."""
    return _plan_extension(_customer_booking(customer, booking_id, lock=False), return_)


def extend_booking(
    customer: Customer,
    booking_id: int,
    return_: datetime,
    *,
    expected_charge: Decimal,
    idempotency_key: str,
    payment: dict | None = None,
    request=None,
) -> Booking:
    """Exp 3 Booking.extend_booking(): Book.Extend, Active -> Active.

    Only when no booking of the vehicle conflicts and the whole rental stays
    within BR-5. The extra charge is authorised first; the later return takes
    effect only once it succeeds. The same key never charges twice.
    """
    actor = customer.user
    key = f"extend-{idempotency_key}"
    outcome: BookingError | None = None
    with transaction.atomic():
        booking = _customer_booking(customer, booking_id, lock=True)
        previous = payments.previous_authorization(booking, key)
        if (previous is not None and previous.success) or booking.return_datetime == return_:
            return booking  # Pay.Idempotent: already extended to this time
        _lock_vehicle(booking.vehicle_id)
        quote = _plan_extension(booking, return_)
        if quote.extra_charge != expected_charge:
            raise BookingConflictError(
                "The charge for this extension has changed. Check it and confirm again.",
                code="price_changed",
            )
        before = {"return_datetime": booking.return_datetime.isoformat()}
        note = f"Rental extended to {_local(return_)} (Book.Extend)"
        auth = None
        if quote.extra_charge > 0:
            auth = _charge_extra(
                booking,
                quote.extra_charge,
                key=key,
                actor=actor,
                request=request,
                payment=payment or {},
            )
            if not auth.success:
                outcome = PaymentDeclinedError(f"Your payment was declined: {auth.message}")
        if outcome is None:
            booking.return_datetime = return_
            booking.total_amount = quote.price.total_payable
            _save_change(
                booking,
                states.record_extension,
                actor,
                request,
                ("return_datetime", "total_amount"),
            )
            if auth is not None:
                _book_extra(booking, auth, quote.extra_charge, note, actor, request)
            record_audit(
                actor,
                "Booking Extended",
                booking,
                before={**before, "total_amount": str(quote.previous_total)},
                after={
                    "return_datetime": return_.isoformat(),
                    "total_amount": str(booking.total_amount),
                },
                request=request,
            )
            _notify(
                booking,
                "booking_extended",
                money=f"The additional charge is {_money(quote.extra_charge)}.",
            )
    if outcome is not None:
        raise outcome
    return booking


# ─── No-show (Appendix B; Exp 5 time event; BR-8) ─────────────────────────


def _declare_no_show(booking: Booking, request) -> None:
    paid = _deposit_payment(booking) is not None
    states.mark_no_show(booking, request=request)
    _audit_release(booking, None, request)
    refund = "Nothing was paid, so there is nothing to refund."
    if paid:
        retained = settings.NO_SHOW_RETAINED_PERCENT
        rental_refund = _share(_rental_paid(booking), 100 - retained)
        _settle(
            booking,
            rental_refund,
            None,
            key=f"no-show-{booking.pk}",
            reason=f"No-show: {retained:.0f}% of the rental retained (BR-8).",
            request=request,
        )
        refund = (
            f"We retain {retained:.0f}% of the rental and are refunding "
            f"{_money(rental_refund + booking.security_deposit)}, including the deposit."
        )
    _notify(booking, "booking_no_show", refund=refund)


def declare_no_shows(*, request=None) -> int:
    """Appendix B: a Confirmed booking not collected NO_SHOW_AFTER past its pickup time
    becomes No-show; BR-8 retains half the rental and refunds the rest and the deposit.

    An unpaid cash-at-collection booking (held until the same moment, R1-P1)
    becomes No-show too, with nothing to refund (R2-P1). A booking with a
    handover condition report is never touched (Module N1), and a row being
    handed over right now is skipped (SKIP LOCKED) and seen Active next time.
    Must run inside a transaction; each booking is settled in its own savepoint,
    so one gateway refusal does not hold up the others.
    """
    due = (
        Booking.objects.select_for_update(of=("self",), skip_locked=True)
        .select_related("vehicle", "pickup_branch", "customer__user")
        .filter(
            Q(status=Status.CONFIRMED) | Q(status=Status.PENDING_PAYMENT, cash_on_collection=True),
            pickup_datetime__lte=timezone.now() - settings.NO_SHOW_AFTER,
        )
        .exclude(condition_reports__report_type=ConditionReport.ReportType.HANDOVER)
        .order_by("pickup_datetime", "pk")
    )
    count = 0
    for booking in due:
        try:
            with transaction.atomic():
                _declare_no_show(booking, request)
        except payments.PaymentError:
            logger.exception("Booking %s: no-show not settled; retried next run.", booking.pk)
            continue
        count += 1
    return count
