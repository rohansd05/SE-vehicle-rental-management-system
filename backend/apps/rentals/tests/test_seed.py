"""Demo data from seed_demo: the handover booking (rentals/seed.py), ready to hand over, and
the return demo (rentals/seed_return.py), two Active rentals ready to return."""

from datetime import datetime, timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone
from freezegun import freeze_time

from apps.bookings import services as bookings
from apps.bookings.models import Booking
from apps.fleet.models import Vehicle
from apps.maintenance.models import MaintenanceJob
from apps.rentals import services
from apps.rentals.seed import (
    DELIVERY_ADDRESS,
    DELIVERY_PICKUP_CODE,
    DELIVERY_REGISTRATION,
    PICKUP_CODE,
    REGISTRATION,
)
from apps.rentals.seed_return import LATE_CAR, ON_TIME_CAR
from apps.rentals.services import ReturnReadings

pytestmark = pytest.mark.django_db


def _seed(*args):
    call_command("seed_demo", *args, stdout=StringIO())


def _demo_bookings():
    return Booking.objects.filter(vehicle__registration_no=REGISTRATION)


# Mid-morning IST on the demo day.
DEMO_DAY = timezone.make_aware(datetime(2026, 10, 16, 10, 0))


@freeze_time(DEMO_DAY)
def test_one_paid_confirmed_booking_today_at_andheri_with_nothing_blocking_it():
    _seed()
    (booking,) = _demo_bookings()
    assert booking.status == Booking.Status.CONFIRMED
    assert booking.pickup_branch.branch_name == "Andheri"
    assert booking.customer.user.email == "handover@vrms.test"
    assert booking.customer.user.check_password("Demo@1234")
    # Five minutes before seed_demo ran, so it can be handed over at once.
    assert booking.pickup_datetime == DEMO_DAY - timedelta(minutes=5)
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
    with freeze_time(DEMO_DAY + timedelta(hours=1)):
        _seed()
    assert _demo_bookings().count() == 1


def test_beat_no_longer_spoils_the_handover_demo():
    """R2's no-show task skips a booking until two hours after its pickup (Appendix B)."""
    with freeze_time(DEMO_DAY):
        _seed()
    with freeze_time(DEMO_DAY + timedelta(hours=1, minutes=50)):  # 1 h 55 min after pickup
        bookings.declare_no_shows()
        assert _demo_bookings().get().status == Booking.Status.CONFIRMED


def test_after_a_no_show_the_next_seed_adds_a_fresh_booking():
    with freeze_time(DEMO_DAY):
        _seed()
    with freeze_time(DEMO_DAY + timedelta(hours=3)):
        bookings.declare_no_shows()
        assert _demo_bookings().get().status == Booking.Status.NO_SHOW  # never handed over
        _seed()
        fresh = _demo_bookings().get(status=Booking.Status.CONFIRMED)
        assert fresh.pickup_datetime == timezone.now() - timedelta(minutes=5)
        assert services.handover_refusals(fresh) == []


def test_a_later_day_gets_a_booking_once_the_last_one_is_over():
    with freeze_time(DEMO_DAY):
        _seed()
    with freeze_time(DEMO_DAY.replace(day=20)):  # last week's booking still blocks the car
        _seed()
        assert _demo_bookings().count() == 1
    with freeze_time(DEMO_DAY.replace(day=24)):
        _seed()
        assert _demo_bookings().count() == 2


@freeze_time(DEMO_DAY)
def test_a_delivered_booking_is_upcoming_with_its_address_and_gets_its_reminder(outbox):
    """Module N4 (R4 follow-up): the branch list shows the delivery address, and the pickup
    reminder (Notify.Remind, version 2) says the vehicle is delivered there."""
    from apps.notifications import tasks

    _seed()
    booking = Booking.objects.get(vehicle__registration_no=DELIVERY_REGISTRATION)
    assert booking.status == Booking.Status.CONFIRMED
    assert (booking.delivery_address, booking.delivery_pincode) == (DELIVERY_ADDRESS, "400053")
    assert booking.add_ons.get().add_on.name == "Doorstep delivery"
    assert booking.pickup_datetime == DEMO_DAY + timedelta(hours=24, minutes=10)
    andheri = Booking.objects.filter(pickup_branch__branch_name="Andheri")
    assert booking in services.branch_collections(andheri, when="upcoming")
    assert services.branch_collections(andheri, query=DELIVERY_PICKUP_CODE).get() == booking
    with freeze_time(DEMO_DAY + timedelta(minutes=15)):  # Beat runs every 5 minutes
        tasks.send_pickup_reminders.delay().get()
    reminders = [m for m in outbox if booking.booking_reference in m.body]
    assert len(reminders) == 2  # e-mail and SMS
    assert all(DELIVERY_ADDRESS in m.body for m in reminders)


def test_the_maintenance_demo_jobs_are_untouched():
    _seed()
    assert MaintenanceJob.objects.count() == 3


def test_reset_removes_and_reloads_it():
    with freeze_time(DEMO_DAY):
        _seed()
        _seed("--reset")
    assert _demo_bookings().count() == 1


# ─── The return demo (rentals/seed_return.py) ─────────────────────────────


def _rental(registration):
    return Booking.objects.get(vehicle__registration_no=registration, status=Booking.Status.ACTIVE)


@freeze_time(DEMO_DAY)
def test_two_active_rentals_are_ready_to_return_one_on_time_and_one_late():
    _seed()
    on_time, late = _rental(ON_TIME_CAR), _rental(LATE_CAR)
    assert on_time.customer.user.email == "return@vrms.test"
    assert on_time.customer.user.check_password("Demo@1234")
    assert on_time.return_datetime == DEMO_DAY + timedelta(hours=2)  # due back today
    assert late.return_datetime == DEMO_DAY - timedelta(hours=3)
    for booking in (on_time, late):
        assert booking.pickup_branch.branch_name == "Andheri"
        assert booking.vehicle.status == Vehicle.Status.ON_RENT
        assert booking.payments.filter(status="Succeeded").count() == 2
        report = services.handover_report(booking)
        assert report.fuel_level == Decimal("100.00") and not report.is_signed_in_db
        assert report.odometer_reading == booking.vehicle.odometer
        assert services.return_refusals(booking) == []
    assert services.handover_report(late).accessories == [{"name": "Child seat", "quantity": 1}]
    andheri = Booking.objects.filter(pickup_branch__branch_name="Andheri")
    assert list(services.branch_returns(andheri)) == [late, on_time]


@freeze_time(DEMO_DAY)
def test_the_late_rental_shows_the_br10_br11_and_br12_lines():
    _seed()
    late = _rental(LATE_CAR)
    staff = late.pickup_branch.staff.get().user
    reading = services.handover_report(late).odometer_reading + 400
    quote = services.return_quote(
        late,
        staff,
        ReturnReadings(reading, Decimal("75.00"), timezone.now()),
    )
    kinds = [line.kind for line in quote.settlement.lines]
    assert kinds == ["late_return", "excess_km", "fuel_shortfall", "tax"]
    assert not quote.override_required


def test_seeding_the_return_demo_again_adds_nothing():
    with freeze_time(DEMO_DAY):
        _seed()
    with freeze_time(DEMO_DAY + timedelta(hours=1)):
        _seed()
    assert Booking.objects.filter(vehicle__registration_no__in=[ON_TIME_CAR, LATE_CAR]).count() == 2
