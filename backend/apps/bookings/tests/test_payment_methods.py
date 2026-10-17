"""Pay.Method: on-line channels (D6) and cash at collection (BR-9, Book.Confirm.Pay)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from freezegun import freeze_time

from apps.accounts.tests.factories import BranchStaffFactory
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings import lifecycle, services
from apps.bookings.models import Booking
from apps.bookings.tests.conftest import PASSWORD
from apps.core.models import AuditLog
from apps.payments.models import CashPayment, Invoice, LedgerEntry, OnlinePayment, Payment
from apps.rentals.services import handover_refusals

pytestmark = pytest.mark.django_db

S = Booking.Status


def held(customer, vehicle, pickup, return_):
    return lifecycle.create_booking(
        customer, vehicle=vehicle, pickup=pickup, return_=return_, terms_accepted=True
    )


def choose_cash(customer, booking, key="choose-cash-1"):
    return lifecycle.pay_booking(customer, booking.pk, idempotency_key=key, method="cash")


@pytest.fixture
def staff(branch):
    return BranchStaffFactory(branch=branch).user


def record(staff_user, booking, amount=None, key="cash-key-0001"):
    return lifecycle.record_cash_payment(
        staff_user,
        booking.pk,
        amount_received=amount if amount is not None else Decimal("9248.00"),
        idempotency_key=key,
    )


# ─── On-line transfer and wallet (D6) ─────────────────────────────────────


@pytest.mark.parametrize("channel", ["UPI", "Net Banking", "Wallet"])
def test_an_online_payment_confirms_the_booking(customer, car, pickup, return_, channel):
    booking = held(customer, car, pickup, return_)
    lifecycle.pay_booking(
        customer,
        booking.pk,
        payment_token="tok_online",
        idempotency_key="pay-online-1",
        method="online",
        channel=channel,
        upi_id="asha@okbank",
    )
    booking.refresh_from_db()
    assert booking.status == S.CONFIRMED
    rows = OnlinePayment.objects.filter(booking=booking)
    assert {row.channel for row in rows} == {channel}
    assert {row.upi_id for row in rows} == {"asha@okbank" if channel == "UPI" else ""}
    assert set(LedgerEntry.objects.filter(booking=booking).values_list("method", flat=True)) == {
        "Online"
    }


# ─── Cash at collection (BR-9) ────────────────────────────────────────────


def test_choosing_cash_keeps_the_booking_unconfirmed_and_held_for_the_collection(
    customer, car, pickup, return_
):
    booking = held(customer, car, pickup, return_)
    choose_cash(customer, booking)
    booking.refresh_from_db()
    assert booking.status == S.PENDING_PAYMENT
    assert booking.cash_on_collection
    assert booking.hold_expires_at == pickup + timedelta(hours=2)  # NO_SHOW_AFTER (R1-P1)
    assert not booking.payments.exists()
    assert not Invoice.objects.filter(booking=booking).exists()
    assert AuditLog.objects.filter(action="Cash On Collection Chosen").count() == 1
    choose_cash(customer, booking, key="choose-cash-2")  # again: nothing changes
    assert AuditLog.objects.filter(action="Cash On Collection Chosen").count() == 1


def test_cash_is_only_for_collection_at_the_branch(customer, car, pickup, return_):
    booking = held(customer, car, pickup, return_)
    Booking.objects.filter(pk=booking.pk).update(delivery_address="12 Hill Road")
    with pytest.raises(lifecycle.BookingError) as refused:
        choose_cash(customer, booking)
    assert refused.value.code == "cash_not_available"


def test_staff_record_the_cash_and_the_same_book_done_confirms_it(
    customer, car, pickup, return_, staff
):
    booking = held(customer, car, pickup, return_)
    choose_cash(customer, booking)
    record(staff, booking)  # 4248.00 rental + 5000.00 deposit
    booking.refresh_from_db()

    assert booking.status == S.CONFIRMED
    assert booking.booking_reference and len(booking.pickup_code) == 6
    rows = CashPayment.objects.filter(booking=booking)
    assert {(row.purpose, row.amount) for row in rows} == {
        ("Rental", Decimal("4248.00")),
        ("Security Deposit", Decimal("5000.00")),
    }
    assert {row.received_by.user for row in rows} == {staff}  # BR-9: a named staff member
    assert {row.transaction_type for row in rows} == {"Capture"}
    assert Invoice.objects.get(booking=booking).total_amount == Decimal("4248.00")
    assert sorted(
        LedgerEntry.objects.filter(booking=booking).values_list("entry_type", flat=True)
    ) == [
        "Capture",
        "Capture",
        "Charge",
        "Deposit Hold",
    ]
    confirmed = AuditLog.objects.filter(action="Booking Status Changed").latest("id")
    assert confirmed.actor == staff
    assert confirmed.after["reason"].startswith("Cash received")
    # N1's paid check sees the cash deposit (other handover conditions are N1's).
    assert "payment_due" not in [refusal.code for refusal in handover_refusals(booking)]


def test_the_cash_must_be_exactly_the_rental_and_the_deposit(customer, car, pickup, return_, staff):
    booking = held(customer, car, pickup, return_)
    choose_cash(customer, booking)
    with pytest.raises(lifecycle.BookingError) as refused:
        record(staff, booking, amount=Decimal("4248.00"))
    assert (refused.value.code, refused.value.field) == ("wrong_amount", "amount_received")
    assert not Payment.objects.filter(booking=booking).exists()


def test_recording_the_same_cash_twice_never_records_it_twice(
    customer, car, pickup, return_, staff
):
    booking = held(customer, car, pickup, return_)
    choose_cash(customer, booking)
    record(staff, booking)
    record(staff, booking)
    assert CashPayment.objects.filter(booking=booking).count() == 2  # rental + deposit, once
    with pytest.raises(lifecycle.InvalidBookingStateError):
        record(staff, booking, key="cash-key-0002")


def test_only_a_cash_booking_waiting_for_its_cash_can_be_recorded(
    customer, car, pickup, return_, staff
):
    booking = held(customer, car, pickup, return_)
    with pytest.raises(lifecycle.InvalidBookingStateError):
        record(staff, booking)


def test_staff_of_another_branch_cannot_find_the_booking(customer, car, pickup, return_):
    booking = held(customer, car, pickup, return_)
    choose_cash(customer, booking)
    with pytest.raises(Booking.DoesNotExist):
        record(BranchStaffFactory().user, booking)


def test_an_uncollected_cash_booking_is_released_after_the_no_show_window(
    customer, car, pickup, return_, staff
):
    booking = held(customer, car, pickup, return_)
    choose_cash(customer, booking)
    with freeze_time(pickup + timedelta(hours=2, minutes=1)):
        # R2-P1: the no-show task, not the hold sweep, releases it, as No-show.
        assert lifecycle.release_expired_holds() == 0
        with pytest.raises(lifecycle.HoldExpiredError):
            lifecycle.pay_booking(customer, booking.pk, idempotency_key="late", method="cash")
        assert services.declare_no_shows() == 1
    booking.refresh_from_db()
    assert booking.status == S.NO_SHOW


def test_a_cash_booking_can_still_be_paid_by_card(customer, car, pickup, return_):
    booking = held(customer, car, pickup, return_)
    choose_cash(customer, booking)
    lifecycle.pay_booking(customer, booking.pk, payment_token="tok_visa", idempotency_key="card-1")
    booking.refresh_from_db()
    assert booking.status == S.CONFIRMED
    assert not booking.cash_on_collection


# ─── Over HTTP ────────────────────────────────────────────────────────────


def test_the_cash_desk_lists_only_its_branchs_held_cash_bookings(
    customer, car, pickup, return_, staff
):
    booking = held(customer, car, pickup, return_)
    other = held(customer, car, pickup + timedelta(days=5), return_ + timedelta(days=5))
    choose_cash(customer, booking)  # `other` waits for a card payment instead
    response = authenticated_client(staff).get(reverse("bookings:booking-awaiting-cash"))
    assert response.status_code == 200
    rows = response.json()["results"]
    assert [row["id"] for row in rows] == [booking.pk]
    assert rows[0]["customer_name"] == customer.user.name
    assert rows[0]["amount_due"] == "9248.00"
    assert rows[0]["cash_on_collection"] is True
    assert other.pk not in [row["id"] for row in rows]
    elsewhere = authenticated_client(BranchStaffFactory().user)
    assert elsewhere.get(reverse("bookings:booking-awaiting-cash")).json()["results"] == []


def test_recording_cash_over_http_asks_for_the_staff_password(
    customer, car, pickup, return_, staff
):
    booking = held(customer, car, pickup, return_)
    choose_cash(customer, booking)
    client = authenticated_client(staff)
    url = reverse("bookings:booking-cash", args=[booking.pk])
    body = {"amount_received": "9248.00", "idempotency_key": "cash-http-1", "password": "wrong"}
    refused = client.post(url, body, format="json")
    assert refused.status_code == 400 and "password" in refused.json()
    assert AuditLog.objects.filter(action="Payment Re-authentication Failed").exists()
    response = client.post(url, {**body, "password": PASSWORD}, format="json")
    assert response.status_code == 200
    assert response.json()["status"] == "Confirmed"
    assert response.json()["pickup_code"] == ""  # staff never see the code (History.Privacy)
    repeat = client.post(url, {**body, "password": PASSWORD}, format="json")
    assert repeat.status_code == 200  # the same key: the first result, nothing recorded again
    another = client.post(
        url, {**body, "password": PASSWORD, "idempotency_key": "cash-http-2"}, format="json"
    )
    assert (another.status_code, another.json()["code"]) == (409, "invalid_state")
    assert CashPayment.objects.filter(booking=booking).count() == 2


def test_paying_online_needs_a_channel_and_cash_needs_no_token(customer, car, pickup, return_):
    booking = held(customer, car, pickup, return_)
    client = authenticated_client(customer.user)
    url = reverse("bookings:booking-pay", args=[booking.pk])
    base = {"idempotency_key": "pay-http-01", "password": PASSWORD}
    no_channel = client.post(url, {**base, "method": "online", "payment_token": "t"}, format="json")
    assert no_channel.status_code == 400 and "channel" in no_channel.json()
    no_token = client.post(url, {**base, "method": "card"}, format="json")
    assert no_token.status_code == 400 and "payment_token" in no_token.json()
    cash = client.post(url, {**base, "method": "cash"}, format="json")
    assert cash.status_code == 200
    assert cash.json()["status"] == "Pending Payment"
    assert cash.json()["cash_on_collection"] is True
