"""Book Vehicle (SRS 3.1; Exp 4 sequence diagram 1): the booking lifecycle service.

Sequence 1 maps onto two requests, because the customer pays after seeing
the quote (BK1):

create_booking()   Customer -> Booking.create_booking()
                   -> Licence.is_valid()            (eligibility.check_eligibility)
                      alt: licence invalid -> booking refused
                   -> Vehicle.check_availability()   (fleet availability service)
                      alt: vehicle not free -> refused (409)
                   -> Tariff.calculate_price()       (pricing.services; snapshot stored, BK7)
                   -> Pending Payment with a 15-minute hold (Book.Hold)
pay_booking()      -> Payment.authorize()            (payments.services.authorize; Pay.Method)
                      alt: declined -> hold retained (BK2)
                   -> Vehicle.update_status()        (Book.Done.Block; see below)
                   -> Invoice.generate_invoice()     (payments.services.issue_invoice)
                   -> status Confirmed, booking reference and pickup code (Book.Done.Store)
record_cash_payment()  BR-9: the customer chose cash at collection; a named staff
                   member records it, then the same Book.Done steps confirm it.

Vehicle.update_status() at confirmation (team decision, 11 Oct 2026): the
Appendix B state machine changes a vehicle's status only at handover, so
confirmation changes no status. The message is Book.Done.Block: the booking's
blocked period (exclusion constraint, BR-1) takes the vehicle out of every
other booking, and an audit entry records the block.

Book.Done is one database transaction. A failure after the gateway has
authorised rolls everything back; the sandbox gateway has no void, so the
uncaptured authorisation simply lapses (team decision: one authorisation).

Proposed (BK1-BK11) items are listed in the Stage 3 summary and marked here.
Owner: Rohan (WBS 1.4.3).
"""

from __future__ import annotations

import secrets
from datetime import datetime

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.models import Customer
from apps.core.audit import record_audit, snapshot
from apps.core.choices import VehicleType
from apps.fleet.models import Vehicle
from apps.fleet.services.availability import check_period, is_available
from apps.payments import services as payments
from apps.pricing.models import AddOn, DiscountCode
from apps.pricing.services import PricingError, Quote, calculate_price, quote

from .eligibility import check_eligibility
from .models import Booking, BookingAddOn
from .numbering import next_in_sequence
from .states import transition

Status = Booking.Status

# BK11: doorstep delivery needs the address check of Book.Deliver.Location,
# which is not built yet; until then the add-on cannot be booked online.
DOORSTEP_DELIVERY = "doorstep delivery"


class BookingError(Exception):
    """A refusal the client can act on: `code` is stable, `status` is the HTTP status."""

    status = 400
    code = "invalid"

    def __init__(self, message: str, *, code: str | None = None, field: str | None = None):
        super().__init__(message)
        if code:
            self.code = code
        self.field = field


class VehicleUnavailableError(BookingError):
    status = 409
    code = "vehicle_unavailable"


class HoldExpiredError(BookingError):
    status = 409
    code = "hold_expired"


class BookingConflictError(BookingError):
    """The booking changed under the customer (price, discount): hold it again."""

    status = 409
    code = "conflict"


class InvalidBookingStateError(BookingError):
    status = 409
    code = "invalid_state"


class PaymentDeclinedError(BookingError):
    status = 402
    code = "payment_declined"


UNAVAILABLE = "Sorry, this vehicle has just been taken for these dates. Please choose another."


# ─── Shared steps ─────────────────────────────────────────────────────────


def booking_snapshot(booking: Booking) -> dict:
    """snapshot() for the audit log; the range field is stored as text (JSON has no ranges)."""
    data = snapshot(booking)
    period = data.pop("blocked_period", None)
    if period is not None:
        data["blocked_period"] = f"[{period.lower.isoformat()}, {period.upper.isoformat()})"
    return data


def _hold_until() -> datetime:
    return timezone.now() + settings.PAYMENT_HOLD_DURATION  # Book.Hold: 15 minutes


def release_expired_holds(*, vehicle: Vehicle | None = None, request=None) -> int:
    """Book.Hold.Expire: expired Pending Payment holds return to Draft, details kept (BK3)."""
    expired = Booking.objects.select_for_update().filter(
        status=Status.PENDING_PAYMENT, hold_expires_at__lte=timezone.now()
    )
    if vehicle is not None:
        expired = expired.filter(vehicle=vehicle)
    count = 0
    for booking in expired:
        booking.hold_expires_at = None
        transition(
            booking,
            Status.DRAFT,
            actor=None,
            reason="The payment hold expired (Book.Hold.Expire).",
            request=request,
            update_fields=("hold_expires_at",),
        )
        count += 1
    return count


def _check_terms(vehicle_type: str, terms_accepted: bool, safety_acknowledged: bool) -> None:
    if not terms_accepted:  # Book.Quote.Terms (BK5)
        raise BookingError(
            "Accept the rental terms to continue.", code="terms_required", field="terms_accepted"
        )
    if vehicle_type == VehicleType.TWO_WHEELER and not safety_acknowledged:  # SA-1 (BK5)
        raise BookingError(
            "Read and acknowledge the safety notice: one helmet per rider is included.",
            code="safety_notice_required",
            field="safety_notice_acknowledged",
        )


def _refuse_delivery(add_on_ids: list[int]) -> None:
    names = AddOn.objects.filter(pk__in=add_on_ids).values_list("name", flat=True)
    if any(name.strip().lower() == DOORSTEP_DELIVERY for name in names):
        raise BookingError(
            "Doorstep delivery can't be booked online yet. Collect the vehicle at the branch.",
            code="delivery_unavailable",
            field="add_ons",
        )


def _price(vehicle, pickup, return_, add_ons, discount_code) -> Quote:
    try:
        return quote(vehicle, pickup, return_, add_ons=add_ons, discount_code=discount_code)
    except PricingError as exc:
        raise BookingError(str(exc), code="pricing", field=exc.field) from exc


def _store_price(booking: Booking, priced: Quote) -> None:
    """BK7: the price snapshot (BR-13: a later tariff change never alters it)."""
    booking.tariff_id = priced.tariff_id
    booking.total_amount = priced.total_payable
    booking.security_deposit = priced.security_deposit
    booking.discount_amount = priced.discount_amount
    booking.discount_code = (
        DiscountCode.objects.get(code__iexact=priced.discount_code)
        if priced.discount_code
        else None
    )


def _store_add_ons(booking: Booking, priced: Quote) -> None:
    booking.add_ons.all().delete()  # only while not yet confirmed (hold again)
    BookingAddOn.objects.bulk_create(
        BookingAddOn(
            booking=booking,
            add_on_id=line.add_on_id,
            quantity=line.quantity,
            daily_rate=line.daily_rate,
        )
        for line in priced.add_ons
    )


def _place_hold(booking: Booking, *, actor, request) -> None:
    """Draft -> Pending Payment. The exclusion constraint is the last word (Book.NoDouble)."""
    booking.hold_expires_at = _hold_until()
    try:
        with transaction.atomic():
            transition(
                booking,
                Status.PENDING_PAYMENT,
                actor=actor,
                reason="Vehicle held while the customer pays (Book.Hold).",
                request=request,
                update_fields=("hold_expires_at",),
            )
    except IntegrityError as exc:
        if "bookings_no_overlapping_vehicle_blocks" in str(exc):
            raise VehicleUnavailableError(UNAVAILABLE) from exc
        raise  # pragma: no cover - any other integrity error is a bug


def booking_quote(booking: Booking) -> Quote:
    """The booking's price recomputed from its snapshot: tariff, add-on rates, discount."""
    add_ons = [
        (AddOn(pk=line.add_on_id, name=line.add_on.name, daily_rate=line.daily_rate), line.quantity)
        for line in booking.add_ons.select_related("add_on").order_by("pk")
    ]
    discount = None
    if booking.discount_code_id:
        # The snapshot amount, so a later edit of the code cannot change this booking.
        discount = DiscountCode(
            code=booking.discount_code.code,
            discount_type=DiscountCode.DiscountType.FIXED,
            value=booking.discount_amount,
        )
    return calculate_price(
        tariff=booking.tariff,
        vehicle_type=booking.vehicle.category.vehicle_type,
        pickup=booking.pickup_datetime,
        return_=booking.return_datetime,
        add_ons=add_ons,
        discount=discount,
    )


# ─── create_booking (Book.Create, Book.Hold) ──────────────────────────────


def create_booking(
    customer: Customer,
    *,
    vehicle: Vehicle,
    pickup: datetime,
    return_: datetime,
    add_ons: list[tuple[int, int]] | None = None,
    discount_code: str = "",
    terms_accepted: bool,
    safety_notice_acknowledged: bool = False,
    request=None,
) -> Booking:
    """Exp 3 Booking.create_booking(): check, price and hold the vehicle for 15 minutes."""
    add_ons = add_ons or []
    actor = customer.user
    vehicle_type = vehicle.category.vehicle_type
    check_period(pickup, return_)  # BR-5 (raises RentalPeriodError)
    _check_terms(vehicle_type, terms_accepted, safety_notice_acknowledged)
    check_eligibility(customer, vehicle_type, pickup, return_)  # Licence.is_valid()
    _refuse_delivery([add_on_id for add_on_id, _ in add_ons])

    with transaction.atomic():
        # One booking at a time per vehicle; the exclusion constraint backs this up.
        locked = Vehicle.objects.select_for_update().select_related("category").get(pk=vehicle.pk)
        release_expired_holds(vehicle=locked, request=request)
        if not is_available(locked, pickup, return_):  # Vehicle.check_availability()
            raise VehicleUnavailableError(UNAVAILABLE)
        priced = _price(locked, pickup, return_, add_ons, discount_code)  # Tariff.calculate_price()
        now = timezone.now()
        booking = Booking(
            customer=customer,
            vehicle=locked,
            pickup_branch_id=locked.home_branch_id,
            pickup_datetime=pickup,
            return_datetime=return_,
            status=Status.DRAFT,
            terms_accepted_at=now,
            safety_notice_acknowledged_at=now if vehicle_type == VehicleType.TWO_WHEELER else None,
        )
        _store_price(booking, priced)
        booking.save()
        _store_add_ons(booking, priced)
        record_audit(actor, "Create", booking, after=booking_snapshot(booking), request=request)
        _place_hold(booking, actor=actor, request=request)
    return booking


def hold_again(customer: Customer, booking_id: int, *, request=None) -> Booking:
    """Book.Hold.Expire: "retain the entered details so that the customer can try again".

    A Draft booking is checked, re-priced at today's tariff and held again.
    """
    with transaction.atomic():
        booking = (
            Booking.objects.select_for_update(of=("self",))
            .select_related("vehicle__category", "discount_code")
            .get(pk=booking_id, customer=customer)
        )
        if booking.status != Status.DRAFT:
            raise InvalidBookingStateError(
                "Only a booking whose hold has expired can be held again."
            )
        vehicle_type = booking.vehicle.category.vehicle_type
        check_period(booking.pickup_datetime, booking.return_datetime)
        check_eligibility(customer, vehicle_type, booking.pickup_datetime, booking.return_datetime)
        locked = (
            Vehicle.objects.select_for_update()
            .select_related("category")
            .get(pk=booking.vehicle_id)
        )
        release_expired_holds(vehicle=locked, request=request)
        if not is_available(locked, booking.pickup_datetime, booking.return_datetime):
            raise VehicleUnavailableError(UNAVAILABLE)
        add_ons = list(booking.add_ons.values_list("add_on_id", "quantity"))
        code = booking.discount_code.code if booking.discount_code_id else ""
        priced = _price(locked, booking.pickup_datetime, booking.return_datetime, add_ons, code)
        _store_price(booking, priced)
        booking.save(
            update_fields=[
                "tariff",
                "total_amount",
                "security_deposit",
                "discount_amount",
                "discount_code",
                "updated_at",
            ]
        )
        _store_add_ons(booking, priced)
        _place_hold(booking, actor=customer.user, request=request)
    return booking


# ─── pay_booking (Pay.Method, Pay.Authorize, Book.Done) ───────────────────

CARD, ONLINE, CASH = "card", "online", "cash"  # Pay.Method; D6: on-line is UPI, net banking, wallet


def _discount_still_usable(booking: Booking) -> bool:
    """BK8: the code is used up at confirmation, so check it again under a row lock."""
    if not booking.discount_code_id:
        return True
    code = DiscountCode.objects.select_for_update().get(pk=booking.discount_code_id)
    now = timezone.now()
    within_limit = code.usage_limit is None or code.times_used < code.usage_limit
    return code.is_active and code.valid_from <= now < code.valid_to and within_limit


def _confirm(booking: Booking, priced: Quote, auth, *, actor, request) -> None:
    """Book.Done, inside the caller's transaction: store, block, invoice, ledger."""
    booking.booking_reference = next_in_sequence(  # BK6: confirmation date in IST
        Booking, "booking_reference", f"VRMS-{timezone.localdate():%Y%m%d}-", 4
    )
    booking.pickup_code = (
        f"{secrets.randbelow(10**settings.PICKUP_CODE_LENGTH):0{settings.PICKUP_CODE_LENGTH}d}"
    )
    booking.confirmed_at = timezone.now()
    booking.hold_expires_at = None
    booking.cash_on_collection = auth.deposit.method == "Cash"
    if booking.discount_code_id:
        DiscountCode.objects.filter(pk=booking.discount_code_id).update(
            times_used=F("times_used") + 1
        )
    paid = "Cash received" if booking.cash_on_collection else "Payment authorised"
    transition(
        booking,
        Status.CONFIRMED,
        actor=actor,
        reason=f"{paid}, transaction {auth.transaction_id} (Book.Done).",
        request=request,
        update_fields=(
            "booking_reference",
            "pickup_code",
            "confirmed_at",
            "hold_expires_at",
            "cash_on_collection",
        ),
    )
    # Vehicle.update_status() in sequence 1 = Book.Done.Block (no status change; see module doc).
    record_audit(
        actor,
        "Vehicle Blocked For Booking",
        booking.vehicle,
        after={
            "booking": booking.booking_reference,
            "blocked_from": booking.blocked_period.lower.isoformat(),
            "blocked_until": booking.blocked_period.upper.isoformat(),
            "status": booking.vehicle.status,
        },
        request=request,
    )
    payments.issue_invoice(booking, priced, actor=actor, request=request)
    payments.record_booking_ledger(booking, auth, actor=actor, request=request)


def _back_to_draft(booking: Booking, *, actor, reason: str, request) -> None:
    booking.hold_expires_at = None
    transition(
        booking,
        Status.DRAFT,
        actor=actor,
        reason=reason,
        request=request,
        update_fields=("hold_expires_at",),
    )


def _payable(booking: Booking, *, actor, request) -> tuple[Quote | None, BookingError | None]:
    """The checks before Book.Done: the hold, the discount (BK8) and the price (BK7).

    Returns the price to collect, or the refusal to raise once the caller's
    transaction has committed the booking's return to Draft.
    """
    if booking.hold_expires_at is None or booking.hold_expires_at <= timezone.now():
        release_expired_holds(vehicle=booking.vehicle, request=request)
        return None, HoldExpiredError(
            "The 15-minute hold on this vehicle has expired. Hold it again to pay."
        )
    if not _discount_still_usable(booking):
        _back_to_draft(
            booking, actor=actor, reason="The discount code is no longer usable.", request=request
        )
        return None, BookingConflictError(
            "Your discount code can no longer be used. Hold the vehicle again for a new price.",
            code="discount_unavailable",
        )
    priced = booking_quote(booking)
    if priced.total_payable != booking.total_amount:  # BK7 recheck
        _back_to_draft(
            booking,
            actor=actor,
            reason="The price changed while the vehicle was held.",
            request=request,
        )
        return None, BookingConflictError(
            "The price has changed. Hold the vehicle again to see the new price.",
            code="price_changed",
        )
    return priced, None


def _choose_cash(booking: Booking, *, actor, request) -> None:
    """Pay.Method, BR-9: cash at collection.

    The booking stays Pending Payment, held for the collection until
    NO_SHOW_AFTER past the pickup time (proposed R1-P1), and is confirmed only
    when a named staff member records the cash (record_cash_payment).
    """
    if booking.delivery_address:
        raise BookingError(
            "Cash is accepted only for a booking collected at the branch (BR-9).",
            code="cash_not_available",
            field="method",
        )
    if booking.cash_on_collection:
        return  # Pay.Idempotent: choosing cash again changes nothing
    booking.cash_on_collection = True
    booking.hold_expires_at = booking.pickup_datetime + settings.NO_SHOW_AFTER
    booking.save(update_fields=["cash_on_collection", "hold_expires_at", "updated_at"])
    record_audit(
        actor,
        "Cash On Collection Chosen",
        booking,
        after={"hold_expires_at": booking.hold_expires_at.isoformat()},
        request=request,
    )


def pay_booking(
    customer: Customer,
    booking_id: int,
    *,
    payment_token: str = "",
    idempotency_key: str,
    method: str = CARD,
    channel: str = "",
    upi_id: str = "",
    request=None,
) -> Booking:
    """Pay.Method, Pay.Authorize and Book.Done. Repeating the same idempotency key never
    charges twice. With `method` cash the booking waits for the cash at collection."""
    actor = customer.user
    outcome: BookingError | None = None
    with transaction.atomic():
        booking = (
            Booking.objects.select_for_update(of=("self",))
            .select_related("vehicle__category", "tariff", "discount_code")
            .get(pk=booking_id, customer=customer)
        )
        if booking.status == Status.CONFIRMED:
            previous = payments.previous_authorization(booking, idempotency_key)
            if previous is not None and previous.success:
                return booking  # Pay.Idempotent: a refreshed page or double submission
            raise InvalidBookingStateError("This booking is already confirmed and paid.")
        if booking.status == Status.DRAFT:
            raise HoldExpiredError(
                "The 15-minute hold on this vehicle has expired. Hold it again to pay."
            )
        if booking.status != Status.PENDING_PAYMENT:
            raise InvalidBookingStateError("This booking is not waiting for payment.")

        priced, outcome = _payable(booking, actor=actor, request=request)
        if priced is not None and method == CASH:
            _choose_cash(booking, actor=actor, request=request)
        elif priced is not None:
            auth = payments.authorize(  # Payment.authorize()
                booking,
                rental_amount=priced.total_payable,
                deposit_amount=priced.security_deposit,
                payment_token=payment_token,
                idempotency_key=idempotency_key,
                actor=actor,
                request=request,
                channel=channel if method == ONLINE else "",
                upi_id=upi_id,
            )
            if auth.success:
                _confirm(booking, priced, auth, actor=actor, request=request)
            else:  # BK2: declined -> hold retained; the failed attempt stays recorded
                outcome = PaymentDeclinedError(
                    f"Your payment was declined: {auth.message} The vehicle stays held "
                    "until the hold expires; you can try another card."
                )
    if outcome is not None:
        raise outcome
    return booking


def record_cash_payment(
    staff_user, booking_id: int, *, amount_received, idempotency_key: str, request=None
) -> Booking:
    """BR-9, Book.Confirm.Pay: a named branch staff member records the cash at collection.

    The booking is then confirmed by the same Book.Done transaction as a card
    payment (_confirm). Only the pickup branch's staff can find the booking.
    """
    staff = staff_user.branch_staff
    outcome: BookingError | None = None
    with transaction.atomic():
        booking = (
            Booking.objects.select_for_update(of=("self",))
            .select_related("vehicle__category", "tariff", "discount_code")
            .get(pk=booking_id, pickup_branch_id=staff.branch_id)
        )
        if booking.status == Status.CONFIRMED:
            previous = payments.previous_authorization(booking, idempotency_key)
            if previous is not None and previous.success:
                return booking  # Pay.Idempotent: the same submission twice
            raise InvalidBookingStateError("This booking is already confirmed and paid.")
        if booking.status != Status.PENDING_PAYMENT or not booking.cash_on_collection:
            raise InvalidBookingStateError("This booking is not waiting for a cash payment.")
        priced, outcome = _payable(booking, actor=staff_user, request=request)
        if priced is not None:
            expected = priced.total_payable + priced.security_deposit
            if amount_received != expected:
                raise BookingError(
                    f"Collect exactly {settings.CURRENCY} {expected}: the rental "
                    f"{priced.total_payable} and the deposit {priced.security_deposit}.",
                    code="wrong_amount",
                    field="amount_received",
                )
            auth = payments.record_cash(
                booking,
                staff=staff,
                rental_amount=priced.total_payable,
                deposit_amount=priced.security_deposit,
                idempotency_key=idempotency_key,
                request=request,
            )
            _confirm(booking, priced, auth, actor=staff_user, request=request)
    if outcome is not None:
        raise outcome
    return booking
