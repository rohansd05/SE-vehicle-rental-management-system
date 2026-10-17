"""Demo data for Module R2 (seed_changes.py): modify, cancel, 3a alternatives, no-show."""

from datetime import timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command

from apps.accounts.models import Customer
from apps.bookings import services
from apps.bookings.models import Booking
from apps.bookings.seed_changes import CHANGE_CAR, CUSTOMER_EMAIL, NO_SHOW_CAR, REGISTRATIONS
from apps.maintenance.models import MaintenanceJob
from apps.maintenance.seed import DEMO_PROBLEMS

pytestmark = pytest.mark.django_db

S = Booking.Status


def _seed(*args):
    call_command("seed_demo", *args, stdout=StringIO())


def _bookings():
    return Booking.objects.filter(vehicle__registration_no__in=REGISTRATIONS).order_by(
        "pickup_datetime"
    )


def test_the_demo_customer_has_three_paid_bookings():
    _seed()
    customer = Customer.objects.get(user__email=CUSTOMER_EMAIL)
    assert customer.user.check_password("Demo@1234")
    missed, change, blocker = _bookings()
    assert {b.status for b in (missed, change, blocker)} == {S.CONFIRMED}
    assert {b.customer_id for b in (missed, change, blocker)} == {customer.pk}
    assert all(b.payments.filter(status="Succeeded").count() == 2 for b in _bookings())
    assert missed.vehicle.registration_no == NO_SHOW_CAR
    assert change.vehicle.registration_no == CHANGE_CAR
    # The existing demo accounts and jobs are untouched.
    assert not Booking.objects.filter(customer__user__email="customer@vrms.test").exists()
    assert MaintenanceJob.objects.filter(reported_problem__in=DEMO_PROBLEMS).count() == 3


def test_the_change_booking_can_be_cancelled_in_full_or_moved_to_an_alternative():
    _seed()
    customer = Customer.objects.get(user__email=CUSTOMER_EMAIL)
    _, change, blocker = _bookings()
    assert services.cancellation_quote(customer, change.pk).refund_percent == Decimal("100")
    busy = services.Modification(
        pickup=blocker.pickup_datetime,
        return_=blocker.pickup_datetime + timedelta(days=1),
        branch=change.pickup_branch,
        add_ons=[],
    )
    quote = services.modification_quote(customer, change.pk, busy)
    assert not quote.vehicle_free
    assert NO_SHOW_CAR in [vehicle.registration_no for vehicle in quote.alternatives]


def test_the_missed_booking_becomes_a_no_show():
    _seed()
    missed = _bookings().first()
    assert services.declare_no_shows() >= 1  # with the handover demo's after 09:00 IST
    missed.refresh_from_db()
    assert missed.status == S.NO_SHOW


def test_seeding_twice_adds_nothing_and_reset_reloads():
    _seed()
    _seed()
    assert _bookings().count() == 3
    assert Customer.objects.filter(user__email=CUSTOMER_EMAIL).count() == 1
    _seed("--reset")
    assert _bookings().count() == 3
