"""Fixtures for the payments tests (Module R1): paid bookings, staff, an Administrator."""

from datetime import timedelta

import pytest

from apps.accounts.tests.factories import AdministratorFactory, BranchStaffFactory
from apps.bookings import lifecycle
from apps.bookings.tests import conftest as booking_fixtures
from apps.payments.models import Payment

# The Book Vehicle fixtures, shared (pytest finds fixtures by their module-level names).
PASSWORD = booking_fixtures.PASSWORD
eligible_customer = booking_fixtures.eligible_customer
branch = booking_fixtures.branch
car = booking_fixtures.car
customer = booking_fixtures.customer
pickup = booking_fixtures.pickup
return_ = booking_fixtures.return_


def held(customer, vehicle, pickup, return_):
    return lifecycle.create_booking(
        customer,
        vehicle=vehicle,
        pickup=pickup,
        return_=return_,
        terms_accepted=True,
        safety_notice_acknowledged=True,
    )


def confirmed(customer, vehicle, pickup, return_, *, method="card", channel="", token="tok_visa"):
    """A booking paid by card (or on-line) and confirmed through Book.Done."""
    booking = held(customer, vehicle, pickup, return_)
    lifecycle.pay_booking(
        customer,
        booking.pk,
        payment_token=token,
        idempotency_key=f"pay-{booking.pk:08d}",
        method=method,
        channel=channel,
    )
    booking.refresh_from_db()
    return booking


def cash_confirmed(customer, vehicle, pickup, return_, staff_user):
    """BR-9: cash chosen by the customer, then recorded at the branch by `staff_user`."""
    booking = held(customer, vehicle, pickup, return_)
    lifecycle.pay_booking(customer, booking.pk, idempotency_key="choose-cash-1", method="cash")
    booking.refresh_from_db()
    lifecycle.record_cash_payment(
        staff_user,
        booking.pk,
        amount_received=booking.total_amount + booking.security_deposit,
        idempotency_key=f"cash-{booking.pk:08d}",
    )
    booking.refresh_from_db()
    return booking


def original(booking, purpose=Payment.Purpose.RENTAL) -> Payment:
    return Payment.objects.get(booking=booking, original_payment=None, purpose=purpose)


def deposit_of(booking) -> Payment:
    return original(booking, Payment.Purpose.SECURITY_DEPOSIT)


@pytest.fixture
def staff(branch):
    return BranchStaffFactory(branch=branch).user


@pytest.fixture
def admin():
    return AdministratorFactory().user


@pytest.fixture
def paid(customer, car, pickup, return_):
    """Two days of a car: rental 4248.00 (3600 + 18% tax), deposit 5000.00 (BR-3)."""
    return confirmed(customer, car, pickup, return_)


@pytest.fixture
def long_paid(customer, car, pickup):
    """Three days of a car: rental 6372.00, above the 5000.00 automatic approval limit."""
    return confirmed(customer, car, pickup, pickup + timedelta(days=3))
