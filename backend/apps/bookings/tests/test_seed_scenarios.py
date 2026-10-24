"""Demo data for the Exp 8 / Exp 10 Booking scenarios (seed_scenarios.py)."""

from datetime import datetime, time, timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone
from freezegun import freeze_time

from apps.accounts.models import Customer, Licence
from apps.bookings import services
from apps.bookings.eligibility import NotEligibleError, check_eligibility
from apps.bookings.models import Booking
from apps.bookings.seed_scenarios import (
    EMAILS,
    LOCKOUT_EMAIL,
    REFUNDS_EMAIL,
    REGISTRATIONS,
    YOUNG_EMAIL,
)
from apps.core.choices import VehicleType
from apps.fleet.models import Car

pytestmark = pytest.mark.django_db

SEEDED_AT = "2026-10-24 04:37:00+00:00"  # 10:07 am IST, not on a 15-minute step


def _scenarios() -> str:
    out = StringIO()
    call_command("seed_booking_scenarios", stdout=out)
    return out.getvalue()


@pytest.fixture(autouse=True)
def seeded():
    with freeze_time(SEEDED_AT):
        call_command("seed_demo", stdout=StringIO())
        _scenarios()
        yield


def _bookings():
    return Booking.objects.filter(vehicle__registration_no__in=REGISTRATIONS).order_by(
        "-pickup_datetime"
    )


def _at(day, hour=10):
    return timezone.make_aware(datetime.combine(day, time(hour)))


def test_a_second_run_creates_nothing():
    output = _scenarios()
    assert "Created: nothing." in output
    assert all(email in output for email in EMAILS)
    assert _bookings().count() == 3
    assert Car.objects.filter(registration_no__in=REGISTRATIONS).count() == 3
    assert Customer.objects.filter(user__email__in=EMAILS).count() == 3


def test_the_refund_bookings_quote_the_three_br8_slabs():
    customer = Customer.objects.get(user__email=REFUNDS_EMAIL)
    bookings = list(_bookings())
    assert [b.status for b in bookings] == [Booking.Status.CONFIRMED] * 3
    assert [b.customer_id for b in bookings] == [customer.pk] * 3
    assert all(b.pickup_datetime.minute % 15 == 0 for b in bookings)
    assert all(b.return_datetime - b.pickup_datetime == timedelta(days=1) for b in bookings)
    quotes = [services.cancellation_quote(customer, b.pk) for b in bookings]
    assert [q.refund_percent for q in quotes] == [Decimal("100"), Decimal("75"), Decimal("50")]
    # the amounts docs/demo/exp-scenarios-booking.md quotes (demo Hatchback tariff, one day)
    assert [q.rental_refund for q in quotes] == [Decimal(a) for a in ("2124", "1593", "1062")]
    assert [q.deposit_refund for q in quotes] == [b.security_deposit for b in bookings]
    assert all(b.security_deposit > 0 for b in bookings)
    assert all(b.vehicle.photos.count() >= 4 and b.vehicle.fuel_capacity for b in bookings)


def test_young_is_refused_a_car_before_the_birthday_but_not_a_two_wheeler():
    customer = Customer.objects.get(user__email=YOUNG_EMAIL)
    birthday = timezone.localdate() + timedelta(days=7)
    before, on = _at(birthday - timedelta(days=1)), _at(birthday)
    with pytest.raises(NotEligibleError) as refused:
        check_eligibility(customer, VehicleType.CAR, before, before + timedelta(days=1))
    assert refused.value.code == "under_age"
    check_eligibility(customer, VehicleType.TWO_WHEELER, before, before + timedelta(days=1))
    check_eligibility(customer, VehicleType.CAR, on, on + timedelta(days=1))


def test_the_lockout_customer_has_a_verified_licence_and_no_bookings():
    customer = Customer.objects.get(user__email=LOCKOUT_EMAIL)
    assert customer.user.check_password("Demo@1234")
    licence = Licence.objects.get(customer=customer)
    assert licence.status == Licence.Status.VERIFIED
    assert set(licence.categories.values_list("category", flat=True)) == {
        VehicleType.CAR,
        VehicleType.TWO_WHEELER,
    }
    assert not Booking.objects.filter(customer=customer).exists()
