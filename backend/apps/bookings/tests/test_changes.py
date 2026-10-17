"""Module R2 services: Modify / Cancel Booking (Exp 2 UC 4), Book.Extend and the No-show.

SRS 3.1 Book.Modify, Book.Modify.Price, Book.Cancel, Book.Cancel.Release,
Book.Extend, Book.Status; BR-1, BR-2, BR-5, BR-8; Exp 3
Booking.modify_booking(), cancel_booking(), extend_booking().

Prices (car tariff 150/h, 1800/day, 18% tax, D14): 1 day 2124.00, 2 days
4248.00, 3 days 6372.00, 4 days 8496.00; deposit 5000.00 (BR-3).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.conf import settings
from django.utils import timezone
from django_celery_beat.models import PeriodicTask
from freezegun import freeze_time

from apps.accounts.models import Licence
from apps.accounts.tests.factories import BranchStaffFactory
from apps.bookings import lifecycle, services, states, tasks
from apps.bookings.eligibility import NotEligibleError
from apps.bookings.models import Booking, BookingAddOn
from apps.bookings.tests.conftest import eligible_customer
from apps.core.choices import VehicleType
from apps.core.models import AuditLog
from apps.fleet.services.availability import RentalPeriodError
from apps.fleet.tests.factories import BranchFactory, CarFactory
from apps.notifications.models import Notification
from apps.payments.models import InvoiceAdjustment, LedgerEntry, Payment, RefundRequest
from apps.pricing.tests.factories import AddOnFactory
from apps.rentals.tests.factories import ConditionReportFactory

pytestmark = pytest.mark.django_db

S = Booking.Status
D = Decimal
RefundStatus = RefundRequest.Status
CARD = {"method": "card", "payment_token": "tok_visa", "channel": "", "upi_id": ""}


def confirmed(customer, vehicle, pickup, return_, key="pay-r2-0001", **kwargs):
    """A booking confirmed through Book.Done with the sandbox card."""
    booking = lifecycle.create_booking(
        customer, vehicle=vehicle, pickup=pickup, return_=return_, terms_accepted=True, **kwargs
    )
    return lifecycle.pay_booking(
        customer, booking.pk, payment_token="tok_visa", idempotency_key=key
    )


def change(booking, **overrides):
    values = {
        "pickup": booking.pickup_datetime,
        "return_": booking.return_datetime,
        "branch": booking.pickup_branch,
        "add_ons": list(booking.add_ons.values_list("add_on_id", "quantity")),
        "vehicle": None,
    }
    return services.Modification(**{**values, **overrides})


def modify(customer, booking, mod, *, charge="0.00", refund="0.00", key="modify-0001", pay=CARD):
    return services.modify_booking(
        customer,
        booking.pk,
        mod,
        expected_charge=D(charge),
        expected_refund=D(refund),
        idempotency_key=key,
        payment=pay,
    )


def refunds(booking) -> list[tuple[str, Decimal, str]]:
    rows = RefundRequest.objects.filter(original_payment__booking=booking).order_by("pk")
    return [(r.original_payment.purpose, r.amount, r.status) for r in rows]


def templates(user) -> list[str]:
    return list(
        Notification.objects.filter(recipient=user)
        .order_by("pk")
        .values_list("template", flat=True)
    )


@pytest.fixture
def staff(branch):
    return BranchStaffFactory(branch=branch).user


@pytest.fixture
def booking(customer, car, pickup, return_):
    return confirmed(customer, car, pickup, return_)


def activate(booking, at):
    with freeze_time(at):
        states.activate_booking(booking, None)
    booking.refresh_from_db()
    return booking


# ─── BR-8 ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("notice", "percent"),
    [
        (timedelta(days=5), "100"),
        (timedelta(hours=48), "100"),  # "at least 48 hours"
        (timedelta(hours=47, minutes=59), "75"),
        (timedelta(hours=12), "75"),
        (timedelta(hours=11, minutes=59), "50"),
        (timedelta(0), "50"),
    ],
)
def test_br8_refund_percent_by_notice(notice, percent):
    assert services.refund_percent(notice) == D(percent)


# ─── Cancel (Book.Cancel, Book.Cancel.Release) ────────────────────────────


def test_cancelling_48_hours_ahead_refunds_everything(customer, car, pickup, return_, staff):
    booking = confirmed(customer, car, pickup, return_)
    quote = services.cancellation_quote(customer, booking.pk)
    assert (quote.refund_percent, quote.rental_refund, quote.deposit_refund) == (
        D("100"),
        D("4248.00"),
        D("5000.00"),
    )
    assert quote.total_refund == D("9248.00") and not quote.awaits_approval

    services.cancel_booking(customer, booking.pk, expected_refund=D("9248.00"))

    booking.refresh_from_db()
    assert booking.status == S.CANCELLED
    assert refunds(booking) == [
        ("Rental", D("4248.00"), RefundStatus.ISSUED),
        ("Security Deposit", D("5000.00"), RefundStatus.ISSUED),
    ]
    # Pay.Ledger: captured, then refunded; Pay.Invoice: a credit note for the rental refund.
    types = list(LedgerEntry.objects.filter(booking=booking).values_list("entry_type", flat=True))
    assert types.count("Capture") == 2 and "Refund" in types and "Deposit Release" in types
    note = InvoiceAdjustment.objects.get(invoice=booking.invoice)
    assert (note.adjustment_type, note.amount) == ("Credit Note", D("4248.00"))
    # Book.Cancel.Release: released, audited, customer and branch told.
    assert AuditLog.objects.filter(action="Vehicle Released From Booking").exists()
    status_change = AuditLog.objects.filter(action="Booking Status Changed").latest("id")
    assert status_change.after["status"] == S.CANCELLED
    assert "booking_cancelled" in templates(customer.user)
    assert templates(staff) == ["booking_branch_update"]
    other = eligible_customer()
    assert confirmed(other, car, pickup, return_, key="pay-r2-0002").status == S.CONFIRMED


@pytest.mark.parametrize(
    ("hours_ahead", "percent", "rental_refund"),
    [(30, "75", "3186.00"), (6, "50", "2124.00")],
)
def test_later_cancellations_refund_less_but_always_the_whole_deposit(
    customer, booking, pickup, hours_ahead, percent, rental_refund
):
    with freeze_time(pickup - timedelta(hours=hours_ahead)):
        quote = services.cancellation_quote(customer, booking.pk)
        assert (quote.refund_percent, quote.rental_refund) == (D(percent), D(rental_refund))
        assert quote.notice_hours == hours_ahead
        services.cancel_booking(customer, booking.pk, expected_refund=quote.total_refund)
    assert refunds(booking) == [
        ("Rental", D(rental_refund), RefundStatus.ISSUED),
        ("Security Deposit", D("5000.00"), RefundStatus.ISSUED),
    ]


def test_a_refund_above_the_approval_limit_waits_for_an_administrator(customer, car, pickup):
    booking = confirmed(customer, car, pickup, pickup + timedelta(days=4))  # 8496.00
    quote = services.cancellation_quote(customer, booking.pk)
    assert quote.awaits_approval
    services.cancel_booking(customer, booking.pk, expected_refund=quote.total_refund)
    assert refunds(booking) == [
        ("Rental", D("8496.00"), RefundStatus.PENDING_APPROVAL),  # UC 13: /app/refunds
        ("Security Deposit", D("5000.00"), RefundStatus.ISSUED),
    ]


def test_a_changed_refund_must_be_confirmed_again(customer, booking):
    with pytest.raises(lifecycle.BookingConflictError) as refused:
        services.cancel_booking(customer, booking.pk, expected_refund=D("9000.00"))
    assert refused.value.code == "refund_changed"
    assert "9,248.00" in str(refused.value)
    booking.refresh_from_db()
    assert booking.status == S.CONFIRMED and not refunds(booking)


def test_cancelling_twice_refunds_once(customer, booking):
    services.cancel_booking(customer, booking.pk, expected_refund=D("9248.00"))
    services.cancel_booking(customer, booking.pk, expected_refund=D("9248.00"))
    assert len(refunds(booking)) == 2


def test_an_active_booking_cannot_be_cancelled(customer, booking, pickup):
    activate(booking, pickup)
    with pytest.raises(lifecycle.InvalidBookingStateError):
        services.cancellation_quote(customer, booking.pk)
    with pytest.raises(lifecycle.InvalidBookingStateError):
        services.cancel_booking(customer, booking.pk, expected_refund=D("0.00"))


def test_a_booking_being_handed_over_cannot_be_cancelled(customer, booking):
    ConditionReportFactory(booking=booking)
    with pytest.raises(lifecycle.InvalidBookingStateError, match="handed over"):
        services.cancel_booking(customer, booking.pk, expected_refund=D("9248.00"))


def test_an_unpaid_cash_booking_is_cancelled_with_nothing_to_refund(customer, car, pickup, return_):
    booking = lifecycle.create_booking(
        customer, vehicle=car, pickup=pickup, return_=return_, terms_accepted=True
    )
    lifecycle.pay_booking(customer, booking.pk, idempotency_key="cash-r2-01", method="cash")
    quote = services.cancellation_quote(customer, booking.pk)
    assert quote.total_refund == D("0.00")
    services.cancel_booking(customer, booking.pk, expected_refund=D("0.00"))
    booking.refresh_from_db()
    assert booking.status == S.CANCELLED  # R2-P1
    assert not Payment.objects.filter(booking=booking).exists()
    other = eligible_customer()
    assert confirmed(other, car, pickup, return_, key="pay-r2-0003").status == S.CONFIRMED


def test_a_held_card_booking_is_not_cancelled_it_simply_expires(customer, car, pickup, return_):
    booking = lifecycle.create_booking(
        customer, vehicle=car, pickup=pickup, return_=return_, terms_accepted=True
    )
    with pytest.raises(lifecycle.InvalidBookingStateError):
        services.cancel_booking(customer, booking.pk, expected_refund=D("0.00"))


def test_a_confirmed_cash_booking_refund_waits_at_the_cash_desk(
    customer, car, pickup, return_, staff
):
    booking = lifecycle.create_booking(
        customer, vehicle=car, pickup=pickup, return_=return_, terms_accepted=True
    )
    lifecycle.pay_booking(customer, booking.pk, idempotency_key="cash-r2-02", method="cash")
    lifecycle.record_cash_payment(
        staff, booking.pk, amount_received=D("9248.00"), idempotency_key="cash-r2-03"
    )
    services.cancel_booking(customer, booking.pk, expected_refund=D("9248.00"))
    assert {status for _, _, status in refunds(booking)} == {RefundStatus.APPROVED}


# ─── Modify (Book.Modify, Book.Modify.Price) ──────────────────────────────


def test_a_longer_period_is_charged_at_once(customer, booking, staff, return_):
    mod = change(booking, return_=return_ + timedelta(days=1))
    quote = services.modification_quote(customer, booking.pk, mod)
    assert quote.vehicle_free and quote.alternatives == []
    assert (quote.previous_total, quote.new_total, quote.extra_charge, quote.refund_amount) == (
        D("4248.00"),
        D("6372.00"),
        D("2124.00"),
        D("0.00"),
    )

    modify(customer, booking, mod, charge="2124.00")

    booking.refresh_from_db()
    assert booking.status == S.CONFIRMED
    assert booking.return_datetime == return_ + timedelta(days=1)
    assert booking.total_amount == D("6372.00")
    extra = Payment.objects.get(booking=booking, idempotency_key="modify-modify-0001:Rental")
    assert (extra.amount, extra.transaction_type, extra.status) == (
        D("2124.00"),
        "Authorize",
        "Succeeded",
    )
    assert not Payment.objects.filter(idempotency_key="modify-modify-0001:Security Deposit")
    charge = LedgerEntry.objects.filter(booking=booking, entry_type="Charge").latest("id")
    assert charge.amount == D("2124.00") and "Book.Modify.Price" in charge.note
    debit = InvoiceAdjustment.objects.get(invoice=booking.invoice)
    assert debit.adjustment_type == "Debit Note"
    assert debit.adjustment_number.startswith(f"DN-{timezone.localdate().year}-")
    modified = AuditLog.objects.get(action="Booking Modified")
    assert modified.before["total_amount"] == "4248.00"
    assert modified.after["total_amount"] == "6372.00"
    assert "booking_modified" in templates(customer.user)
    assert templates(staff) == ["booking_branch_update"]


def test_a_shorter_period_refunds_the_excess_under_br8(customer, booking, pickup):
    mod = change(booking, return_=pickup + timedelta(days=1))
    with freeze_time(pickup - timedelta(hours=30)):  # 75% band
        quote = services.modification_quote(customer, booking.pk, mod)
        assert (quote.extra_charge, quote.refund_percent, quote.refund_amount) == (
            D("0.00"),
            D("75"),
            D("1593.00"),
        )
        modify(customer, booking, mod, refund="1593.00")
    booking.refresh_from_db()
    assert booking.total_amount == D("2124.00")
    assert refunds(booking) == [("Rental", D("1593.00"), RefundStatus.ISSUED)]
    assert InvoiceAdjustment.objects.get(invoice=booking.invoice).adjustment_type == "Credit Note"


def test_no_change_inside_the_12_hour_cut_off(customer, booking, pickup, return_):
    mod = change(booking, return_=return_ + timedelta(days=1))
    with freeze_time(pickup - timedelta(hours=11, minutes=59)):
        with pytest.raises(services.ModificationCutoffError) as refused:
            services.modification_quote(customer, booking.pk, mod)
        assert "12 hours" in str(refused.value)  # UC 4 2a: states the cut-off
        with pytest.raises(services.ModificationCutoffError):
            modify(customer, booking, mod, charge="2124.00")


def test_a_busy_vehicle_offers_one_of_the_same_category(customer, booking, car, branch, return_):
    same = CarFactory(home_branch=branch, category=car.category, available_from=date(2026, 1, 1))
    CarFactory(home_branch=branch, available_from=date(2026, 1, 1))  # another category
    later = return_ + timedelta(days=3)
    confirmed(eligible_customer(), car, later, later + timedelta(days=2), key="pay-r2-0004")
    mod = change(booking, pickup=later, return_=later + timedelta(days=2))

    quote = services.modification_quote(customer, booking.pk, mod)
    assert not quote.vehicle_free
    assert [vehicle.pk for vehicle in quote.alternatives] == [same.pk]  # UC 4 3a
    with pytest.raises(lifecycle.VehicleUnavailableError):
        modify(customer, booking, mod)

    take = change(booking, pickup=later, return_=later + timedelta(days=2), vehicle=same)
    assert services.modification_quote(customer, booking.pk, take).vehicle_free
    modify(customer, booking, take)
    booking.refresh_from_db()
    assert booking.vehicle_id == same.pk and booking.total_amount == D("4248.00")  # same tariff


def test_the_turnaround_buffer_still_applies(customer, booking, car, return_):
    """BR-1: a new return within 60 minutes of the next booking's pickup is not free."""
    nxt = return_ + timedelta(days=2)
    confirmed(eligible_customer(), car, nxt, nxt + timedelta(days=1), key="pay-r2-0005")
    close = change(booking, return_=nxt - timedelta(minutes=59))
    assert not services.modification_quote(customer, booking.pk, close).vehicle_free
    clear = change(booking, return_=nxt - timedelta(hours=1))
    assert services.modification_quote(customer, booking.pk, clear).vehicle_free


def test_a_new_branch_needs_a_vehicle_based_there(customer, booking, car):
    bandra = BranchFactory(branch_name="Bandra")
    there = CarFactory(home_branch=bandra, category=car.category, available_from=date(2026, 1, 1))
    quote = services.modification_quote(customer, booking.pk, change(booking, branch=bandra))
    assert not quote.vehicle_free  # R2-P3
    assert [vehicle.pk for vehicle in quote.alternatives] == [there.pk]
    modify(customer, booking, change(booking, branch=bandra, vehicle=there), key="modify-0002")
    booking.refresh_from_db()
    assert (booking.pickup_branch, booking.vehicle_id) == (bandra, there.pk)


def test_add_ons_keep_their_booked_rate_and_new_ones_take_todays(customer, car, pickup, return_):
    seat = AddOnFactory(name="Child seat", daily_rate=D("100.00"), vehicle_type=VehicleType.CAR)
    gps = AddOnFactory(name="GPS", daily_rate=D("50.00"), vehicle_type=VehicleType.CAR)
    booking = confirmed(customer, car, pickup, return_, add_ons=[(seat.pk, 1)])  # 4484.00
    seat.daily_rate = D("150.00")
    seat.save()
    mod = change(booking, add_ons=[(seat.pk, 1), (gps.pk, 1)])
    quote = services.modification_quote(customer, booking.pk, mod)
    # (3600 + 2 x 100 + 2 x 50) x 1.18 = 4602.00
    assert (quote.new_total, quote.extra_charge) == (D("4602.00"), D("118.00"))
    modify(customer, booking, mod, charge="118.00")
    rates = dict(BookingAddOn.objects.filter(booking=booking).values_list("add_on", "daily_rate"))
    assert rates == {seat.pk: D("100.00"), gps.pk: D("50.00")}

    modify(customer, booking, change(booking, add_ons=[]), refund="354.00", key="modify-0003")
    assert not BookingAddOn.objects.filter(booking=booking).exists()


def test_a_changed_price_must_be_confirmed_again(customer, booking, return_):
    mod = change(booking, return_=return_ + timedelta(days=1))
    with pytest.raises(lifecycle.BookingConflictError) as refused:
        modify(customer, booking, mod, charge="2000.00")
    assert refused.value.code == "price_changed"
    assert not Payment.objects.filter(idempotency_key__startswith="modify-").exists()


def test_a_declined_extra_charge_changes_nothing(customer, booking, return_):
    mod = change(booking, return_=return_ + timedelta(days=1))
    declined = {**CARD, "payment_token": "tok_decline"}
    with pytest.raises(lifecycle.PaymentDeclinedError):
        modify(customer, booking, mod, charge="2124.00", pay=declined)
    booking.refresh_from_db()
    assert booking.return_datetime == return_ and booking.total_amount == D("4248.00")
    assert Payment.objects.get(idempotency_key="modify-modify-0001:Rental").status == "Failed"


def test_an_extra_charge_needs_a_payment_method(customer, booking, return_):
    mod = change(booking, return_=return_ + timedelta(days=1))
    with pytest.raises(lifecycle.BookingError) as refused:
        modify(customer, booking, mod, charge="2124.00", pay={})
    assert (refused.value.code, refused.value.field) == ("payment_required", "payment_token")


def test_the_same_key_never_charges_twice(customer, booking, return_):
    mod = change(booking, return_=return_ + timedelta(days=1))
    modify(customer, booking, mod, charge="2124.00")
    modify(customer, booking, mod, charge="2124.00")
    assert Payment.objects.filter(idempotency_key__startswith="modify-").count() == 1
    assert AuditLog.objects.filter(action="Booking Modified").count() == 1


def test_an_unchanged_request_changes_nothing(customer, booking):
    modify(customer, booking, change(booking))
    assert not AuditLog.objects.filter(action="Booking Modified").exists()


def test_only_a_confirmed_booking_can_be_changed(customer, booking, pickup, return_):
    activate(booking, pickup)
    with pytest.raises(lifecycle.InvalidBookingStateError):
        services.modification_quote(customer, booking.pk, change(booking))


def test_a_booking_being_handed_over_cannot_be_changed(customer, booking, return_):
    ConditionReportFactory(booking=booking)
    with pytest.raises(lifecycle.InvalidBookingStateError, match="handed over"):
        modify(customer, booking, change(booking, return_=return_ + timedelta(days=1)))


def test_br5_and_br2_still_apply_to_the_new_period(customer, booking, pickup):
    too_long = change(booking, return_=pickup + timedelta(days=30, hours=1))
    with pytest.raises(RentalPeriodError):
        services.modification_quote(customer, booking.pk, too_long)
    Licence.objects.filter(customer=customer).update(expiry_date=timezone.localdate(pickup))
    later = change(booking, return_=pickup + timedelta(days=3))
    with pytest.raises(NotEligibleError) as refused:
        services.modification_quote(customer, booking.pk, later)
    assert refused.value.code == "licence_expires_before_return"


def test_an_alternative_must_be_of_the_same_category(customer, booking, branch):
    other = CarFactory(home_branch=branch, available_from=date(2026, 1, 1))
    with pytest.raises(lifecycle.BookingError) as refused:
        services.modification_quote(customer, booking.pk, change(booking, vehicle=other))
    assert refused.value.field == "vehicle"


def test_doorstep_delivery_cannot_be_added(customer, booking):
    delivery = AddOnFactory(name="Doorstep delivery", vehicle_type="")
    with pytest.raises(lifecycle.BookingError) as refused:
        services.modification_quote(
            customer, booking.pk, change(booking, add_ons=[(delivery.pk, 1)])
        )
    assert refused.value.code == "delivery_unavailable"


def test_raising_then_cancelling_refunds_both_payments(customer, booking, return_):
    """The debit note lets the credit notes cover the extra charge (Pay.Invoice)."""
    modify(
        customer, booking, change(booking, return_=return_ + timedelta(days=1)), charge="2124.00"
    )
    services.cancel_booking(customer, booking.pk, expected_refund=D("11372.00"))
    assert sorted(amount for _, amount, _ in refunds(booking)) == [
        D("2124.00"),
        D("4248.00"),
        D("5000.00"),
    ]
    notes = InvoiceAdjustment.objects.filter(invoice=booking.invoice)
    assert sorted(notes.values_list("adjustment_type", "amount")) == [
        ("Credit Note", D("2124.00")),
        ("Credit Note", D("4248.00")),
        ("Debit Note", D("2124.00")),
    ]


# ─── Extend (Book.Extend) ─────────────────────────────────────────────────


def test_an_active_rental_is_extended_once_the_extra_is_paid(customer, booking, pickup, return_):
    activate(booking, pickup)
    later = return_ + timedelta(days=1)
    with freeze_time(pickup + timedelta(hours=1)):
        quote = services.extension_quote(customer, booking.pk, later)
        assert (quote.previous_total, quote.extra_charge) == (D("4248.00"), D("2124.00"))
        services.extend_booking(
            customer,
            booking.pk,
            later,
            expected_charge=D("2124.00"),
            idempotency_key="extend-0001",
            payment=CARD,
        )
    booking.refresh_from_db()
    assert booking.status == S.ACTIVE
    assert (booking.return_datetime, booking.total_amount) == (later, D("6372.00"))
    assert Payment.objects.get(idempotency_key="extend-extend-0001:Rental").amount == D("2124.00")
    assert InvoiceAdjustment.objects.get(invoice=booking.invoice).adjustment_type == "Debit Note"
    assert AuditLog.objects.filter(action="Booking Extended").exists()
    assert "booking_extended" in templates(customer.user)


def test_no_extension_into_another_booking_or_its_buffer(customer, booking, car, pickup, return_):
    nxt = return_ + timedelta(hours=2)
    confirmed(eligible_customer(), car, nxt, nxt + timedelta(days=1), key="pay-r2-0006")
    activate(booking, pickup)
    with freeze_time(pickup + timedelta(hours=1)):
        services.extension_quote(customer, booking.pk, return_ + timedelta(hours=1))  # touches
        with pytest.raises(lifecycle.VehicleUnavailableError):
            services.extension_quote(customer, booking.pk, return_ + timedelta(hours=1, minutes=1))


def test_the_whole_rental_stays_within_30_days(customer, booking, pickup):
    activate(booking, pickup)
    limit = pickup + settings.RENTAL_PERIOD_MAXIMUM
    with freeze_time(pickup + timedelta(hours=1)):
        services.extension_quote(customer, booking.pk, limit)
        with pytest.raises(lifecycle.BookingError, match="BR-5") as refused:
            services.extension_quote(customer, booking.pk, limit + timedelta(minutes=1))
    assert refused.value.field == "return_datetime"


def test_only_an_active_rental_is_extended(customer, booking, return_):
    with pytest.raises(lifecycle.InvalidBookingStateError):
        services.extension_quote(customer, booking.pk, return_ + timedelta(days=1))


def test_the_new_return_must_be_later(customer, booking, pickup, return_):
    activate(booking, pickup)
    with freeze_time(pickup + timedelta(hours=1)):
        with pytest.raises(lifecycle.BookingError):
            services.extension_quote(customer, booking.pk, return_)


def test_a_declined_extension_changes_nothing(customer, booking, pickup, return_):
    activate(booking, pickup)
    with freeze_time(pickup + timedelta(hours=1)):
        with pytest.raises(lifecycle.PaymentDeclinedError):
            services.extend_booking(
                customer,
                booking.pk,
                return_ + timedelta(days=1),
                expected_charge=D("2124.00"),
                idempotency_key="extend-0002",
                payment={**CARD, "payment_token": "tok_decline"},
            )
        with pytest.raises(lifecycle.BookingConflictError):
            services.extend_booking(
                customer,
                booking.pk,
                return_ + timedelta(days=1),
                expected_charge=D("1.00"),
                idempotency_key="extend-0003",
                payment=CARD,
            )
    booking.refresh_from_db()
    assert booking.return_datetime == return_


def test_extending_twice_with_one_key_charges_once(customer, booking, pickup, return_):
    activate(booking, pickup)
    with freeze_time(pickup + timedelta(hours=1)):
        for _ in range(2):
            services.extend_booking(
                customer,
                booking.pk,
                return_ + timedelta(days=1),
                expected_charge=D("2124.00"),
                idempotency_key="extend-0004",
                payment=CARD,
            )
    assert Payment.objects.filter(idempotency_key__startswith="extend-").count() == 1


# ─── No-show (Appendix B; BR-8) ───────────────────────────────────────────


def test_an_uncollected_booking_is_a_no_show_two_hours_after_pickup(customer, booking, pickup):
    with freeze_time(pickup + settings.NO_SHOW_AFTER - timedelta(minutes=1)):
        assert services.declare_no_shows() == 0
    with freeze_time(pickup + settings.NO_SHOW_AFTER):
        assert tasks.declare_no_shows() == 1
    booking.refresh_from_db()
    assert booking.status == S.NO_SHOW
    assert refunds(booking) == [  # BR-8: 50% of the rental retained, the deposit refunded
        ("Rental", D("2124.00"), RefundStatus.ISSUED),
        ("Security Deposit", D("5000.00"), RefundStatus.ISSUED),
    ]
    entry = AuditLog.objects.filter(action="Booking Status Changed").latest("id")
    assert entry.actor is None and entry.after["status"] == S.NO_SHOW
    assert "booking_no_show" in templates(customer.user)


def test_a_handed_over_booking_is_never_a_no_show(booking, pickup):
    ConditionReportFactory(booking=booking)
    with freeze_time(pickup + timedelta(hours=3)):
        assert services.declare_no_shows() == 0
    booking.refresh_from_db()
    assert booking.status == S.CONFIRMED


def test_an_unpaid_cash_booking_becomes_a_no_show_and_frees_the_vehicle(
    customer, car, pickup, return_
):
    booking = lifecycle.create_booking(
        customer, vehicle=car, pickup=pickup, return_=return_, terms_accepted=True
    )
    lifecycle.pay_booking(customer, booking.pk, idempotency_key="cash-r2-04", method="cash")
    with freeze_time(pickup + timedelta(hours=2, minutes=1)):
        assert lifecycle.release_expired_holds() == 0  # left to the no-show task (R2-P1)
        assert services.declare_no_shows() == 1
        later = pickup + timedelta(hours=3)
        other = confirmed(eligible_customer(), car, later, return_, key="pay-r2-0007")
    booking.refresh_from_db()
    assert booking.status == S.NO_SHOW
    assert not Payment.objects.filter(booking=booking).exists()
    assert other.status == S.CONFIRMED


def test_other_statuses_are_left_alone(customer, car, pickup, return_, booking):
    activate(booking, pickup)
    with freeze_time(pickup + timedelta(hours=3)):
        assert services.declare_no_shows() == 0
    booking.refresh_from_db()
    assert booking.status == S.ACTIVE


def test_a_gateway_refusal_leaves_the_booking_for_the_next_run(booking, pickup, monkeypatch):
    from apps.payments import services as payments

    def refuse(*args, **kwargs):
        raise payments.PaymentError("Gateway down.", code="capture_failed", status=402)

    monkeypatch.setattr(payments, "capture_charges", refuse)
    with freeze_time(pickup + timedelta(hours=3)):
        assert services.declare_no_shows() == 0
    booking.refresh_from_db()
    assert booking.status == S.CONFIRMED


def test_the_no_show_task_is_scheduled_every_minute():
    task = PeriodicTask.objects.get(task="apps.bookings.tasks.declare_no_shows")
    assert task.enabled and (task.interval.every, task.interval.period) == (1, "minutes")
