"""Demo handover data from seed_demo: one Confirmed booking at Andheri, ready to hand over."""

from datetime import datetime, time
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone
from freezegun import freeze_time

from apps.bookings.models import Booking
from apps.maintenance.models import MaintenanceJob
from apps.rentals import services
from apps.rentals.seed import PICKUP_CODE, REGISTRATION

pytestmark = pytest.mark.django_db


def _seed(*args):
    call_command("seed_demo", *args, stdout=StringIO())


def _demo_bookings():
    return Booking.objects.filter(vehicle__registration_no=REGISTRATION)


# Mid-morning IST on the demo day, after the 07:00 pickup.
DEMO_DAY = timezone.make_aware(datetime(2026, 10, 16, 10, 0))


@freeze_time(DEMO_DAY)
def test_one_paid_confirmed_booking_today_at_andheri_with_nothing_blocking_it():
    _seed()
    (booking,) = _demo_bookings()
    assert booking.status == Booking.Status.CONFIRMED
    assert booking.pickup_branch.branch_name == "Andheri"
    assert booking.customer.user.email == "handover@vrms.test"
    assert booking.customer.user.check_password("Demo@1234")
    assert timezone.localtime(booking.pickup_datetime).date() == DEMO_DAY.date()
    assert timezone.localtime(booking.pickup_datetime).time() == time(7, 0)
    assert booking.pickup_code == PICKUP_CODE
    assert booking.booking_reference.startswith("VRMS-20261016-")
    assert services.handover_refusals(booking) == []
    assert services.expected_accessories(booking) == [{"name": "Child seat", "quantity": 1}]
    # The booking passed through the state machine, audited.
    assert booking.total_amount > 0 and booking.payments.filter(status="Succeeded").count() == 2


@freeze_time(DEMO_DAY)
def test_it_appears_in_todays_collections_and_by_its_pickup_code():
    _seed()
    andheri = Booking.objects.filter(pickup_branch__branch_name="Andheri")
    assert list(services.branch_collections(andheri)) == list(_demo_bookings())
    assert services.branch_collections(andheri, query=PICKUP_CODE).count() == 1


def test_seeding_again_the_same_day_adds_nothing():
    with freeze_time(DEMO_DAY):
        _seed()
        _seed()
    assert _demo_bookings().count() == 1


def test_a_later_day_gets_a_booking_once_the_last_one_is_over():
    with freeze_time(DEMO_DAY):
        _seed()
    with freeze_time(DEMO_DAY.replace(day=20)):  # last week's booking still blocks the car
        _seed()
        assert _demo_bookings().count() == 1
    with freeze_time(DEMO_DAY.replace(day=24)):
        _seed()
        assert _demo_bookings().count() == 2


def test_the_maintenance_demo_jobs_are_untouched():
    _seed()
    assert MaintenanceJob.objects.count() == 3


def test_reset_removes_and_reloads_it():
    with freeze_time(DEMO_DAY):
        _seed()
        _seed("--reset")
    assert _demo_bookings().count() == 1
