"""Module R3 booking notifications: Book.Done.Customer, Book.Done.Branch (Exp 2 UC 3
step 7, "notifies the actor and the branch"), Notify.Booking by SMS (R2 sends the
e-mails), CI-5, CI-6, SI-2.2. Each trigger writes exactly one Notification row per
channel per recipient, sent by Celery after the transaction commits.

Prices (car tariff 150/h, 1800/day, 18% tax, D14): 2 days 4248.00; deposit 5000.00.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.conf import settings
from freezegun import freeze_time

from apps.accounts.tests.factories import BranchStaffFactory
from apps.bookings import lifecycle, services, states
from apps.bookings.models import Booking
from apps.fleet.tests.factories import BranchFactory
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db

D = Decimal
S = Booking.Status
CARD = {"method": "card", "payment_token": "tok_visa", "channel": "", "upi_id": ""}
EMAIL, SMS, SENT = Notification.Channel.EMAIL, Notification.Channel.SMS, Notification.Status.SENT


def sent(user) -> list[tuple[str, str, str]]:
    """(template, channel, status) of every message `user` was sent, oldest first."""
    rows = Notification.objects.filter(recipient=user).order_by("pk")
    return list(rows.values_list("template", "channel", "status"))


def held(customer, car, pickup, return_):
    return lifecycle.create_booking(
        customer, vehicle=car, pickup=pickup, return_=return_, terms_accepted=True
    )


def confirmed(customer, car, pickup, return_):
    booking = held(customer, car, pickup, return_)
    return lifecycle.pay_booking(
        customer, booking.pk, payment_token="tok_visa", idempotency_key="pay-r3-0001"
    )


@pytest.fixture
def staff(car):
    return BranchStaffFactory(branch=car.home_branch).user


# ─── Book.Done.Customer, Book.Done.Branch ─────────────────────────────────


def test_book_done_e_mails_and_texts_the_customer_and_tells_the_branch(
    customer, car, pickup, return_, staff, outbox
):
    elsewhere = BranchStaffFactory(branch=BranchFactory(branch_name="Bandra")).user
    booking = confirmed(customer, car, pickup, return_)

    assert sent(customer.user) == [
        ("booking_confirmed", EMAIL, SENT),
        ("booking_confirmed_sms", SMS, SENT),
    ]
    assert sent(staff) == [("booking_branch_update", EMAIL, SENT)]
    assert sent(elsewhere) == []

    # CI-6: the booking, the price itemised as invoiced (UI-4) and the collection details.
    (mail,) = [m for m in outbox if m.recipient == customer.user.email]
    assert mail.subject.endswith(f"booking {booking.booking_reference} is confirmed")
    for text in (
        "Rental, 2 days: INR 3,600.00",
        "Tax: INR 648.00",
        "Total: INR 4,248.00",
        "Refundable security deposit, held apart: INR 5,000.00",
        car.home_branch.address,
        f"your driving licence {customer.licence.licence_number}",
        "Status: Confirmed",
    ):
        assert text in mail.body
    assert booking.pickup_code not in mail.body  # Book.Done.Customer: the code goes by SMS
    # CI-5: the reference and the pickup code by SMS, to the registered mobile.
    (text,) = [m for m in outbox if m.channel == "sms"]
    assert text.recipient == customer.user.mobile_no
    assert booking.booking_reference in text.body and booking.pickup_code in text.body
    (branch_mail,) = [m for m in outbox if m.recipient == staff.email]
    assert branch_mail.subject.endswith(f"booking {booking.booking_reference} is now Confirmed")
    # The pickup code is read at send time and never stored in the delivery log.
    assert all(booking.pickup_code not in str(n.context) for n in Notification.objects.all())


def test_cash_recorded_at_collection_confirms_and_notifies_the_same_way(
    customer, car, pickup, return_, staff
):
    booking = held(customer, car, pickup, return_)
    lifecycle.pay_booking(customer, booking.pk, method="cash", idempotency_key="cash-r3-0001")
    assert sent(customer.user) == []  # BR-9: confirmed only when the cash is received
    lifecycle.record_cash_payment(
        staff, booking.pk, amount_received=D("9248.00"), idempotency_key="cash-r3-0002"
    )
    assert sent(customer.user) == [
        ("booking_confirmed", EMAIL, SENT),
        ("booking_confirmed_sms", SMS, SENT),
    ]
    assert sent(staff) == [("booking_branch_update", EMAIL, SENT)]


def test_a_repeated_payment_sends_nothing_twice(customer, car, pickup, return_):
    booking = confirmed(customer, car, pickup, return_)
    lifecycle.pay_booking(
        customer, booking.pk, payment_token="tok_visa", idempotency_key="pay-r3-0001"
    )
    assert [t for t, _, _ in sent(customer.user)] == ["booking_confirmed", "booking_confirmed_sms"]


def test_a_failed_book_done_rolls_its_notifications_back(
    customer, car, pickup, return_, staff, monkeypatch
):
    """Book.Done.Failure: one transaction; no message about a booking that was not made."""
    booking = held(customer, car, pickup, return_)

    def broken(*args, **kwargs):
        raise RuntimeError("SMS queue down")

    monkeypatch.setattr(services, "queue_sms", broken)  # after the e-mail row was written
    with pytest.raises(RuntimeError):
        lifecycle.pay_booking(
            customer, booking.pk, payment_token="tok_visa", idempotency_key="pay-r3-0001"
        )
    booking.refresh_from_db()
    assert booking.status == S.PENDING_PAYMENT
    assert not Notification.objects.exists()


def test_a_declined_payment_sends_nothing(customer, car, pickup, return_):
    booking = held(customer, car, pickup, return_)
    with pytest.raises(lifecycle.PaymentDeclinedError):
        lifecycle.pay_booking(
            customer, booking.pk, payment_token="tok_decline", idempotency_key="pay-r3-0002"
        )
    assert not Notification.objects.exists()


# ─── Notify.Booking by SMS: modification, cancellation, extension, no-show ────


def texts_after_confirmation(booking) -> list[Notification]:
    rows = Notification.objects.filter(booking=booking, channel=SMS).order_by("pk")
    return list(rows.exclude(template="booking_confirmed_sms"))


def test_a_cancellation_is_texted_once_with_its_reference_and_status(
    customer, car, pickup, return_, outbox
):
    booking = confirmed(customer, car, pickup, return_)
    services.cancel_booking(customer, booking.pk, expected_refund=D("9248.00"))
    (row,) = texts_after_confirmation(booking)
    assert (row.template, row.status, row.destination) == (
        "booking_cancelled_sms",
        SENT,
        customer.user.mobile_no,
    )
    (text,) = [m.body for m in outbox if m.channel == "sms" and "cancelled" in m.body]
    assert booking.booking_reference in text and "Status: Cancelled" in text


def test_a_modification_is_texted_once(customer, car, pickup, return_, outbox):
    booking = confirmed(customer, car, pickup, return_)
    change = services.Modification(
        pickup=booking.pickup_datetime,
        return_=booking.return_datetime + timedelta(days=1),
        branch=booking.pickup_branch,
        add_ons=[],
        vehicle=None,
    )
    services.modify_booking(
        customer,
        booking.pk,
        change,
        expected_charge=D("2124.00"),
        expected_refund=D("0.00"),
        idempotency_key="modify-r3-01",
        payment=CARD,
    )
    assert [n.template for n in texts_after_confirmation(booking)] == ["booking_modified_sms"]
    (text,) = [m.body for m in outbox if m.channel == "sms" and "changed" in m.body]
    assert booking.booking_reference in text and "Status: Confirmed" in text


def test_an_extension_is_texted_once(customer, car, pickup, return_, outbox):
    booking = confirmed(customer, car, pickup, return_)
    with freeze_time(pickup):
        states.activate_booking(booking, None)
    later = return_ + timedelta(days=1)
    with freeze_time(pickup + timedelta(hours=1)):
        services.extend_booking(
            customer,
            booking.pk,
            later,
            expected_charge=D("2124.00"),
            idempotency_key="extend-r3-01",
            payment=CARD,
        )
    assert [n.template for n in texts_after_confirmation(booking)] == ["booking_extended_sms"]
    (text,) = [m.body for m in outbox if m.channel == "sms" and "now ends" in m.body]
    assert booking.booking_reference in text and "Status: Active" in text


def test_a_no_show_is_texted_once(customer, car, pickup, return_, outbox):
    booking = confirmed(customer, car, pickup, return_)
    with freeze_time(pickup + settings.NO_SHOW_AFTER):
        assert services.declare_no_shows() == 1
    assert [n.template for n in texts_after_confirmation(booking)] == ["booking_no_show_sms"]
    (text,) = [m.body for m in outbox if m.channel == "sms" and "no-show" in m.body]
    assert booking.booking_reference in text and "Status: No-show" in text
