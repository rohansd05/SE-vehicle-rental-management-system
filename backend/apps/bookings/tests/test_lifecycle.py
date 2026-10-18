"""Exp 4 sequence diagram 1, step by step: create_booking() and pay_booking().

Main flow: is_valid -> check_availability -> calculate_price -> hold ->
authorize -> block (update_status) -> generate_invoice -> Confirmed.
Alternative flows: licence invalid, vehicle not free, payment declined, and
the hold expiring (Book.Hold.Expire).
"""

import re
from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import override_settings
from django.utils import timezone
from freezegun import freeze_time

from apps.accounts.models import Licence
from apps.bookings import lifecycle
from apps.bookings.eligibility import NotEligibleError
from apps.bookings.models import Booking, BookingAddOn
from apps.bookings.tasks import release_expired_holds
from apps.bookings.tests.conftest import eligible_customer
from apps.bookings.tests.factories import BookingFactory
from apps.core.choices import VehicleType
from apps.core.models import AuditLog
from apps.fleet.models import Vehicle
from apps.fleet.services.availability import RentalPeriodError
from apps.payments.models import CardPayment, Invoice, InvoiceLine, LedgerEntry, Payment
from apps.pricing.models import DiscountCode
from apps.pricing.tests.factories import AddOnFactory, DiscountCodeFactory

pytestmark = pytest.mark.django_db

S = Booking.Status


def create(customer, vehicle, pickup, return_, **kwargs):
    kwargs.setdefault("terms_accepted", True)
    return lifecycle.create_booking(
        customer, vehicle=vehicle, pickup=pickup, return_=return_, **kwargs
    )


def pay(customer, booking, token="tok_visa", key="pay-key-0001"):
    return lifecycle.pay_booking(customer, booking.pk, payment_token=token, idempotency_key=key)


def actions(entity_type: str | None = None) -> list[str]:
    entries = AuditLog.objects.order_by("id")
    if entity_type:
        entries = entries.filter(entity_type=entity_type)
    return list(entries.values_list("action", flat=True))


# ─── create_booking: the hold (Book.Create, Book.Hold) ────────────────────


def test_a_booking_is_held_for_15_minutes_with_its_price(customer, car, pickup, return_):
    seat = AddOnFactory(
        name="Child seat", daily_rate=Decimal("100.00"), vehicle_type=VehicleType.CAR
    )
    before = timezone.now()
    booking = create(customer, car, pickup, return_, add_ons=[(seat.pk, 1)])

    booking.refresh_from_db()
    assert booking.status == S.PENDING_PAYMENT
    assert (
        before + timedelta(minutes=15)
        <= booking.hold_expires_at
        <= timezone.now() + timedelta(minutes=15)
    )
    assert booking.pickup_branch == car.home_branch
    assert booking.booking_reference == "" and booking.pickup_code == ""
    # BK7 snapshot: 2 days x 1800 + child seat 2 x 100 = 3800, + 18% tax.
    assert booking.total_amount == Decimal("4484.00")
    assert booking.security_deposit == Decimal("5000.00")
    assert booking.tariff.vehicle_category == car.category
    line = BookingAddOn.objects.get(booking=booking)
    assert (line.add_on, line.quantity, line.daily_rate) == (seat, 1, Decimal("100.00"))
    assert booking.terms_accepted_at is not None
    assert booking.safety_notice_acknowledged_at is None  # a car needs no SA-1 notice
    assert actions("bookings.Booking") == ["Create", "Booking Status Changed"]


def test_the_hold_blocks_the_vehicle_for_everyone_else(customer, car, pickup, return_):
    create(customer, car, pickup, return_)
    with pytest.raises(lifecycle.VehicleUnavailableError):
        create(eligible_customer(), car, pickup + timedelta(hours=3), return_)


def test_a_discount_code_is_priced_but_not_used_up(customer, car, pickup, return_):
    code = DiscountCodeFactory(code="WELCOME10")
    booking = create(customer, car, pickup, return_, discount_code="welcome10")
    assert booking.discount_code == code
    assert booking.discount_amount == Decimal("360.00")
    code.refresh_from_db()
    assert code.times_used == 0


def test_the_rental_terms_must_be_accepted(customer, car, pickup, return_):
    with pytest.raises(lifecycle.BookingError) as error:
        create(customer, car, pickup, return_, terms_accepted=False)
    assert (error.value.code, error.value.field) == ("terms_required", "terms_accepted")
    assert not Booking.objects.exists()


def test_a_two_wheeler_needs_the_safety_notice(customer, scooter, pickup, return_):
    with pytest.raises(lifecycle.BookingError) as error:
        create(customer, scooter, pickup, return_)
    assert error.value.code == "safety_notice_required"
    booking = create(customer, scooter, pickup, return_, safety_notice_acknowledged=True)
    assert booking.safety_notice_acknowledged_at is not None  # SA-1: stored with the booking


def test_doorstep_delivery_needs_an_address(customer, car, pickup, return_):
    """Book.Deliver.Location (Module R4): no longer refused outright; the address is asked."""
    delivery = AddOnFactory(name="Doorstep delivery")
    with pytest.raises(lifecycle.BookingError) as error:
        create(customer, car, pickup, return_, add_ons=[(delivery.pk, 1)])
    assert error.value.field == "delivery_address"


def test_a_bad_period_is_refused(customer, car, pickup):
    with pytest.raises(RentalPeriodError):
        create(customer, car, pickup, pickup + timedelta(hours=2))


def test_a_bad_discount_code_is_refused_on_its_field(customer, car, pickup, return_):
    with pytest.raises(lifecycle.BookingError) as error:
        create(customer, car, pickup, return_, discount_code="NOPE")
    assert (error.value.code, error.value.field) == ("pricing", "discount_code")
    assert not Booking.objects.exists()


# ─── alt: licence invalid -> booking refused ──────────────────────────────


def test_an_unverified_licence_refuses_the_booking(customer, car, pickup, return_):
    Licence.objects.filter(customer=customer).update(status=Licence.Status.PENDING_VERIFICATION)
    with pytest.raises(NotEligibleError) as error:
        create(customer, car, pickup, return_)
    assert error.value.code == "licence_not_verified"
    assert not Booking.objects.exists()


# ─── alt: vehicle not free ────────────────────────────────────────────────


def test_a_confirmed_booking_in_the_period_refuses_the_booking(customer, car, pickup, return_):
    BookingFactory(vehicle=car, pickup_datetime=pickup - timedelta(hours=5), return_datetime=pickup)
    with pytest.raises(lifecycle.VehicleUnavailableError, match="just been taken"):
        create(customer, car, pickup, return_)  # inside the 60-minute buffer (BR-1)


def test_a_vehicle_that_cannot_be_handed_over_is_refused(customer, car, pickup, return_):
    Vehicle.objects.filter(pk=car.pk).update(status=Vehicle.Status.UNSAFE)
    with pytest.raises(lifecycle.VehicleUnavailableError):
        create(customer, car, pickup, return_)


def test_the_constraint_is_the_last_word(customer, car, pickup, return_, monkeypatch):
    """Even if the availability check were wrong, the constraint refuses (Book.NoDouble)."""
    BookingFactory(vehicle=car, pickup_datetime=pickup, return_datetime=return_)
    monkeypatch.setattr(lifecycle, "is_available", lambda *args: True)
    with pytest.raises(lifecycle.VehicleUnavailableError):
        create(customer, car, pickup, return_)


def test_an_expired_hold_of_someone_else_is_released_first(customer, car, pickup, return_):
    other = create(eligible_customer(), car, pickup, return_)
    with freeze_time(timezone.now() + timedelta(minutes=16)):
        mine = create(customer, car, pickup, return_)
    other.refresh_from_db()
    assert other.status == S.DRAFT and other.hold_expires_at is None
    assert mine.status == S.PENDING_PAYMENT


# ─── pay_booking: the main flow (Book.Done) ───────────────────────────────


def test_payment_confirms_the_booking_in_one_transaction(customer, car, pickup, return_):
    booking = pay(customer, create(customer, car, pickup, return_))
    booking.refresh_from_db()

    # Book.Done.Store
    assert booking.status == S.CONFIRMED
    today = timezone.localdate().strftime("%Y%m%d")
    assert booking.booking_reference == f"VRMS-{today}-0001"
    assert re.fullmatch(r"[0-9]{6}", booking.pickup_code)
    assert booking.confirmed_at is not None and booking.hold_expires_at is None

    # Payment.authorize(): one authorisation, two rows (Pay.Deposit keeps the deposit apart).
    rental, deposit = (
        CardPayment.objects.get(booking=booking, purpose=purpose)
        for purpose in (Payment.Purpose.RENTAL, Payment.Purpose.SECURITY_DEPOSIT)
    )
    assert (rental.amount, deposit.amount) == (Decimal("4248.00"), Decimal("5000.00"))
    assert rental.status == deposit.status == Payment.Status.SUCCEEDED
    assert rental.transaction_type == Payment.TransactionType.AUTHORIZE
    assert rental.gateway_reference == deposit.gateway_reference != ""
    assert rental.transaction_id != deposit.transaction_id

    # Vehicle.update_status() = Book.Done.Block: no status change (team decision).
    car.refresh_from_db()
    assert car.status == Vehicle.Status.AVAILABLE
    block = AuditLog.objects.get(action="Vehicle Blocked For Booking")
    assert block.entity_id == str(car.pk) and block.after["booking"] == booking.booking_reference

    # Invoice.generate_invoice()
    invoice = Invoice.objects.get(booking=booking)
    assert invoice.invoice_number == f"INV-{timezone.localdate().year}-000001"
    assert (invoice.tax_amount, invoice.total_amount) == (Decimal("648.00"), Decimal("4248.00"))
    rental_line = InvoiceLine.objects.get(invoice=invoice)
    assert (rental_line.description, rental_line.amount) == ("Rental, 2 days", Decimal("3600.00"))

    # Pay.Ledger
    assert list(
        LedgerEntry.objects.filter(booking=booking).values_list("entry_type", "amount", "payment")
    ) == [
        ("Charge", Decimal("4248.00"), rental.pk),
        ("Deposit Hold", Decimal("5000.00"), deposit.pk),
    ]

    # SE-10: an audit entry for each step, in the order of the sequence diagram.
    assert actions() == [
        "Create",
        "Booking Status Changed",  # Draft -> Pending Payment (hold)
        "Payment Authorized",
        "Payment Authorized",
        "Booking Status Changed",  # Pending Payment -> Confirmed
        "Vehicle Blocked For Booking",
        "Invoice Issued",
        "Ledger Entries Recorded",
    ]
    assert AuditLog.objects.verify_chain()


def test_references_and_invoice_numbers_are_sequential(customer, branch, car, pickup, return_):
    first = pay(customer, create(customer, car, pickup, return_))
    second_car = type(car).objects.get(pk=car.pk)
    later = pickup + timedelta(days=5)
    second = pay(
        customer, create(customer, second_car, later, later + timedelta(days=1)), key="pay-key-0002"
    )
    assert first.booking_reference.endswith("-0001") and second.booking_reference.endswith("-0002")
    assert second.invoice.invoice_number.endswith("-000002")


def test_the_discount_is_used_up_and_invoiced(customer, car, pickup, return_):
    code = DiscountCodeFactory(code="FLAT500", discount_type="Fixed", value=Decimal("500.00"))
    booking = pay(customer, create(customer, car, pickup, return_, discount_code="FLAT500"))
    code.refresh_from_db()
    assert code.times_used == 1
    line = InvoiceLine.objects.get(
        invoice__booking=booking, line_type=InvoiceLine.LineType.DISCOUNT
    )
    assert line.amount == Decimal("-500.00")
    assert booking.invoice.total_amount == Decimal("3658.00")  # (3600 - 500) x 1.18


def test_add_ons_are_invoiced_per_line(customer, car, pickup, return_):
    seat = AddOnFactory(name="Child seat", daily_rate=Decimal("100.00"))
    booking = pay(customer, create(customer, car, pickup, return_, add_ons=[(seat.pk, 2)]))
    line = InvoiceLine.objects.get(invoice__booking=booking, line_type=InvoiceLine.LineType.ADD_ON)
    assert (line.description, line.quantity, line.amount) == (
        "Child seat x2, 2 days",
        Decimal("4.00"),
        Decimal("400.00"),
    )


def test_a_fully_discounted_rental_authorises_only_the_deposit(customer, car, pickup, return_):
    DiscountCodeFactory(code="FREE", discount_type="Fixed", value=Decimal("99999.00"))
    booking = pay(customer, create(customer, car, pickup, return_, discount_code="FREE"))
    assert list(booking.payments.values_list("purpose", flat=True)) == ["Security Deposit"]
    assert list(
        LedgerEntry.objects.filter(booking=booking).values_list("entry_type", flat=True)
    ) == ["Deposit Hold"]
    assert booking.invoice.total_amount == Decimal("0.00")


# ─── alt: payment declined -> hold retained (BK2) ─────────────────────────


def test_a_declined_payment_keeps_the_hold_and_can_be_retried(customer, car, pickup, return_):
    booking = create(customer, car, pickup, return_)
    with pytest.raises(lifecycle.PaymentDeclinedError, match="declined"):
        pay(customer, booking, token="tok_decline", key="pay-declined-1")
    booking.refresh_from_db()
    assert booking.status == S.PENDING_PAYMENT
    assert set(booking.payments.values_list("status", flat=True)) == {"Failed"}
    assert not Invoice.objects.filter(booking=booking).exists()
    assert not LedgerEntry.objects.filter(booking=booking).exists()
    assert actions().count("Payment Declined") == 2

    pay(customer, booking, key="pay-retry-2")
    booking.refresh_from_db()
    assert booking.status == S.CONFIRMED


def test_repeating_a_declined_key_does_not_call_the_gateway_again(customer, car, pickup, return_):
    booking = create(customer, car, pickup, return_)
    for _ in range(2):
        with pytest.raises(lifecycle.PaymentDeclinedError):
            pay(customer, booking, token="tok_decline", key="same-key-01")
    assert booking.payments.count() == 2


# ─── Pay.Idempotent ───────────────────────────────────────────────────────


def test_the_same_key_never_charges_twice(customer, car, pickup, return_):
    booking = create(customer, car, pickup, return_)
    pay(customer, booking, key="pay-once-01")
    again = pay(customer, booking, key="pay-once-01")
    assert again.status == S.CONFIRMED
    assert booking.payments.count() == 2
    assert Invoice.objects.filter(booking=booking).count() == 1


def test_a_new_key_on_a_confirmed_booking_is_refused(customer, car, pickup, return_):
    booking = create(customer, car, pickup, return_)
    pay(customer, booking, key="pay-once-01")
    with pytest.raises(lifecycle.InvalidBookingStateError, match="already confirmed"):
        pay(customer, booking, key="pay-twice-02")


@pytest.mark.parametrize("status", [S.ACTIVE, S.COMPLETED, S.CANCELLED])
def test_only_a_held_booking_can_be_paid(customer, car, status):
    booking = BookingFactory(customer=customer, vehicle=car, status=status)
    with pytest.raises(lifecycle.InvalidBookingStateError):
        pay(customer, booking)


def test_another_customers_booking_cannot_be_paid(customer, car, pickup, return_):
    booking = create(customer, car, pickup, return_)
    with pytest.raises(Booking.DoesNotExist):
        pay(eligible_customer(), booking)


# ─── Book.Hold.Expire ─────────────────────────────────────────────────────


def test_paying_after_the_hold_expired_is_refused_and_releases_it(customer, car, pickup, return_):
    booking = create(customer, car, pickup, return_)
    with freeze_time(timezone.now() + timedelta(minutes=15, seconds=1)):
        with pytest.raises(lifecycle.HoldExpiredError):
            pay(customer, booking)
    booking.refresh_from_db()
    assert booking.status == S.DRAFT
    assert not booking.payments.exists()
    with pytest.raises(lifecycle.HoldExpiredError):  # a Draft says the same
        pay(customer, booking)


def test_the_sweep_releases_only_expired_holds(customer, car, scooter, pickup, return_):
    expired = create(customer, car, pickup, return_)
    with freeze_time(timezone.now() + timedelta(minutes=10)):
        fresh = create(customer, scooter, pickup, return_, safety_notice_acknowledged=True)
    with freeze_time(timezone.now() + timedelta(minutes=16)):
        assert release_expired_holds() == 1  # the Celery task
    expired.refresh_from_db()
    fresh.refresh_from_db()
    assert (expired.status, fresh.status) == (S.DRAFT, S.PENDING_PAYMENT)


def test_an_expired_booking_can_be_held_again_with_its_details(customer, car, pickup, return_):
    seat = AddOnFactory(name="Child seat", daily_rate=Decimal("100.00"))
    booking = create(customer, car, pickup, return_, add_ons=[(seat.pk, 1)])
    with freeze_time(timezone.now() + timedelta(minutes=20)):
        lifecycle.release_expired_holds()
        held = lifecycle.hold_again(customer, booking.pk)
        assert held.status == S.PENDING_PAYMENT
        assert held.hold_expires_at > timezone.now()
        assert list(held.add_ons.values_list("add_on", "quantity")) == [(seat.pk, 1)]
        assert held.total_amount == Decimal("4484.00")
        pay(customer, held)


def test_holding_again_refuses_a_booking_that_is_not_draft(customer, car, pickup, return_):
    booking = create(customer, car, pickup, return_)
    with pytest.raises(lifecycle.InvalidBookingStateError):
        lifecycle.hold_again(customer, booking.pk)


def test_holding_again_refuses_when_the_vehicle_was_taken(customer, car, pickup, return_):
    booking = create(customer, car, pickup, return_)
    with freeze_time(timezone.now() + timedelta(minutes=20)):
        other = eligible_customer()
        pay(other, create(other, car, pickup, return_))
        with pytest.raises(lifecycle.VehicleUnavailableError):
            lifecycle.hold_again(customer, booking.pk)


def test_holding_again_rechecks_eligibility(customer, car, pickup, return_):
    booking = create(customer, car, pickup, return_)
    with freeze_time(timezone.now() + timedelta(minutes=20)):
        lifecycle.release_expired_holds()
        customer.is_blacklisted = True
        customer.save()
        with pytest.raises(NotEligibleError):
            lifecycle.hold_again(customer, booking.pk)


# ─── The price and the discount are rechecked at payment (BK7, BK8) ───────


def test_a_price_change_during_the_hold_is_refused(customer, car, pickup, return_):
    booking = create(customer, car, pickup, return_)
    with override_settings(TAX_RATE_PERCENT=Decimal("12.00")):
        with pytest.raises(lifecycle.BookingConflictError) as error:
            pay(customer, booking)
    assert error.value.code == "price_changed" and error.value.status == 409
    booking.refresh_from_db()
    assert booking.status == S.DRAFT
    assert not booking.payments.exists()


@pytest.mark.parametrize(
    "change",
    [{"is_active": False}, {"usage_limit": 1, "times_used": 1}],
    ids=["deactivated", "used-up"],
)
def test_a_discount_that_became_unusable_is_refused(customer, car, pickup, return_, change):
    code = DiscountCodeFactory(code="ONCE")
    booking = create(customer, car, pickup, return_, discount_code="ONCE")
    DiscountCode.objects.filter(pk=code.pk).update(**change)
    with pytest.raises(lifecycle.BookingConflictError) as error:
        pay(customer, booking)
    assert error.value.code == "discount_unavailable"
    booking.refresh_from_db()
    assert booking.status == S.DRAFT


def test_a_booking_keeps_its_price_after_a_code_is_edited(customer, car, pickup, return_):
    """BR-13 spirit: the snapshot amount is used, not the code's new value."""
    code = DiscountCodeFactory(code="SAVE10")
    booking = create(customer, car, pickup, return_, discount_code="SAVE10")
    DiscountCode.objects.filter(pk=code.pk).update(value=Decimal("50.00"))
    booking = pay(customer, booking)
    assert booking.invoice.total_amount == booking.total_amount


# ─── Book.Done.Failure: all or nothing ────────────────────────────────────


def test_a_failure_after_authorisation_rolls_everything_back(
    customer, car, pickup, return_, monkeypatch
):
    booking = create(customer, car, pickup, return_)

    def broken(*args, **kwargs):
        raise RuntimeError("invoice store down")

    monkeypatch.setattr(lifecycle.payments, "issue_invoice", broken)
    with pytest.raises(RuntimeError):
        pay(customer, booking)
    booking.refresh_from_db()
    assert booking.status == S.PENDING_PAYMENT and booking.booking_reference == ""
    assert not Payment.objects.exists()
    assert not LedgerEntry.objects.exists()
