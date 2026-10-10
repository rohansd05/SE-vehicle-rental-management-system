"""Search.Available, BR-1, BR-5, Fleet.Add, Fleet.Retire: the availability service.

Every rule has a test that shows it excluding a vehicle and a boundary test
that shows it not excluding one too many.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from django.db import IntegrityError, transaction
from freezegun import freeze_time

from apps.bookings.models import Booking
from apps.bookings.tests.factories import BookingFactory
from apps.fleet.models import Vehicle
from apps.fleet.services.availability import (
    RentalPeriodError,
    available_vehicles,
    bookable_statuses,
    check_period,
    is_available,
    requested_block,
)
from apps.fleet.tests.factories import (
    BranchFactory,
    CarFactory,
    TwoWheelerFactory,
    VehicleCategoryFactory,
)
from apps.maintenance.models import MaintenanceJob
from apps.maintenance.tests.factories import MaintenanceJobFactory
from apps.pricing.models import Tariff
from apps.pricing.tests.factories import TariffFactory

pytestmark = pytest.mark.django_db

Status = Booking.Status
VStatus = Vehicle.Status

NOW = datetime(2026, 10, 11, 6, 0, tzinfo=UTC)  # 11:30 in Asia/Kolkata
PICKUP = datetime(2026, 10, 13, 4, 30, tzinfo=UTC)  # 13 Oct, 10:00 IST
RETURN = PICKUP + timedelta(days=1)
BUFFER = timedelta(minutes=60)  # BR-1


@pytest.fixture(autouse=True)
def _frozen_clock():
    with freeze_time(NOW):
        yield


@pytest.fixture
def branch():
    return BranchFactory(branch_name="Andheri")


@pytest.fixture
def car(branch):
    return CarFactory(home_branch=branch, available_from=date(2026, 9, 1))


def found(branch, pickup=PICKUP, return_=RETURN, **kwargs) -> set[int]:
    return set(
        available_vehicles(branch=branch, pickup=pickup, return_=return_, **kwargs).values_list(
            "pk", flat=True
        )
    )


def book(vehicle, start, end, status=Status.CONFIRMED) -> Booking:
    # One tariff per category: with the clock frozen, a second tariff would
    # share effective_from and break pricing_tariff_unique_start.
    tariff = Tariff.objects.filter(vehicle_category=vehicle.category).first() or TariffFactory(
        vehicle_category=vehicle.category
    )
    return BookingFactory(
        vehicle=vehicle, tariff=tariff, pickup_datetime=start, return_datetime=end, status=status
    )


# ─── Vehicle status (Search.Available, Appendix B, Fleet.Retire) ──────────


def test_bookable_statuses_come_from_the_status_service():
    """Only Available may be handed over (Available -> On Rent), so only it is bookable."""
    assert bookable_statuses() == {VStatus.AVAILABLE}


def test_an_available_vehicle_at_the_branch_is_found(branch, car):
    assert found(branch) == {car.pk}


def test_a_vehicle_of_another_branch_is_not_found(branch, car):
    CarFactory(home_branch=BranchFactory(branch_name="Bandra"))
    assert found(branch) == {car.pk}


@pytest.mark.parametrize(
    "status", [VStatus.ON_RENT, VStatus.UNDER_MAINTENANCE, VStatus.UNSAFE, VStatus.RETIRED]
)
def test_a_vehicle_that_cannot_be_handed_over_is_excluded(branch, car, status):
    Vehicle.objects.filter(pk=car.pk).update(status=status)
    assert found(branch) == set()


# ─── Bookings and the BR-1 turnaround buffer ──────────────────────────────


@pytest.mark.parametrize("status", [Status.PENDING_PAYMENT, Status.CONFIRMED, Status.ACTIVE])
def test_a_booking_that_holds_the_vehicle_excludes_it(branch, car, status):
    """Search.Available (Confirmed, Active) and Book.Hold (Pending Payment)."""
    book(car, PICKUP + timedelta(hours=2), PICKUP + timedelta(hours=8), status)
    assert found(branch) == set()


@pytest.mark.parametrize(
    "status", [Status.DRAFT, Status.CANCELLED, Status.COMPLETED, Status.NO_SHOW]
)
def test_a_booking_that_does_not_hold_the_vehicle_is_ignored(branch, car, status):
    book(car, PICKUP, RETURN, status)
    assert found(branch) == {car.pk}


def test_a_booking_of_another_vehicle_is_ignored(branch, car):
    book(CarFactory(home_branch=branch), PICKUP, RETURN)
    assert car.pk in found(branch)


@pytest.mark.parametrize(
    ("gap", "expected"),
    [(timedelta(minutes=30), False), (timedelta(minutes=59), False), (BUFFER, True)],
)
def test_pickup_after_an_earlier_booking_respects_the_buffer(branch, car, gap, expected):
    """BR-1: the earlier booking blocks until its return plus 60 minutes."""
    book(car, PICKUP - timedelta(hours=10), PICKUP - gap)
    assert (car.pk in found(branch)) is expected


@pytest.mark.parametrize(
    ("gap", "expected"),
    [(timedelta(minutes=30), False), (timedelta(minutes=59), False), (BUFFER, True)],
)
def test_return_before_a_later_booking_respects_the_buffer(branch, car, gap, expected):
    """BR-1: the requested booking blocks until its own return plus 60 minutes."""
    book(car, RETURN + gap, RETURN + timedelta(hours=10))
    assert (car.pk in found(branch)) is expected


@pytest.mark.parametrize("gap_minutes", [0, 30, 59, 60, 90])
def test_search_agrees_with_the_exclusion_constraint(branch, car, gap_minutes):
    """A vehicle is offered exactly when the database would accept a booking of it."""
    book(car, PICKUP - timedelta(hours=10), PICKUP - timedelta(minutes=gap_minutes))
    offered = car.pk in found(branch)
    try:
        with transaction.atomic():
            book(car, PICKUP, RETURN, Status.PENDING_PAYMENT)
        accepted = True
    except IntegrityError as error:
        assert "bookings_no_overlapping_vehicle_blocks" in str(error)
        accepted = False
    assert offered is accepted


def test_requested_block_matches_what_a_booking_stores(car):
    booking = book(car, PICKUP, RETURN)
    assert requested_block(PICKUP, RETURN) == booking.compute_blocked_period()


# ─── Maintenance windows (Search.Available, Maint.Schedule) ───────────────


def _job(vehicle, status, start, end):
    return MaintenanceJobFactory(
        vehicle=vehicle, status=status, scheduled_from=start, scheduled_to=end
    )


@pytest.mark.parametrize(
    "status", [MaintenanceJob.Status.SCHEDULED, MaintenanceJob.Status.IN_PROGRESS]
)
def test_an_open_maintenance_window_in_the_period_excludes_the_vehicle(branch, car, status):
    _job(car, status, PICKUP + timedelta(hours=3), PICKUP + timedelta(hours=5))
    assert found(branch) == set()


@pytest.mark.parametrize(
    "status",
    [
        MaintenanceJob.Status.REPORTED,
        MaintenanceJob.Status.COMPLETED,
        MaintenanceJob.Status.CANCELLED,
    ],
)
def test_a_closed_or_unscheduled_job_is_ignored(branch, car, status):
    _job(car, status, PICKUP, RETURN)
    assert found(branch) == {car.pk}


def test_a_window_ending_at_pickup_or_starting_at_return_is_ignored(branch, car):
    scheduled = MaintenanceJob.Status.SCHEDULED
    _job(car, scheduled, PICKUP - timedelta(hours=4), PICKUP)
    _job(car, scheduled, RETURN, RETURN + timedelta(hours=4))
    assert found(branch) == {car.pk}


# ─── Availability date (Fleet.Add) ────────────────────────────────────────


def test_a_vehicle_not_yet_in_service_is_excluded(branch, car):
    Vehicle.objects.filter(pk=car.pk).update(available_from=date(2026, 10, 14))
    assert found(branch) == set()


def test_a_vehicle_is_bookable_from_its_availability_date(branch, car):
    Vehicle.objects.filter(pk=car.pk).update(available_from=date(2026, 10, 13))
    assert found(branch) == {car.pk}


def test_the_availability_date_is_read_in_local_time(branch, car):
    """00:30 IST on 13 Oct is still 12 Oct in UTC; the local date decides."""
    Vehicle.objects.filter(pk=car.pk).update(available_from=date(2026, 10, 13))
    pickup = datetime(2026, 10, 12, 19, 0, tzinfo=UTC)
    assert found(branch, pickup, pickup + timedelta(hours=6)) == {car.pk}


# ─── Category filter ──────────────────────────────────────────────────────


def test_the_category_filter_narrows_the_results(branch, car):
    scooter = TwoWheelerFactory(home_branch=branch, available_from=date(2026, 9, 1))
    assert found(branch) == {car.pk, scooter.pk}
    assert found(branch, category=scooter.category) == {scooter.pk}
    assert found(branch, category=VehicleCategoryFactory(name="SUV")) == set()


# ─── Rental period (BR-5) ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("pickup", "return_", "field"),
    [
        (NOW - timedelta(hours=1), NOW + timedelta(hours=5), "pickup_datetime"),
        (NOW, NOW + timedelta(hours=5), "pickup_datetime"),
        (PICKUP, PICKUP, "return_datetime"),
        (PICKUP, PICKUP - timedelta(hours=5), "return_datetime"),
        (PICKUP, PICKUP + timedelta(hours=3, minutes=59), "return_datetime"),
        (PICKUP, PICKUP + timedelta(days=30, minutes=1), "return_datetime"),
    ],
    ids=["past", "now", "zero-length", "reversed", "under-4-hours", "over-30-days"],
)
def test_a_period_outside_the_rules_is_refused(pickup, return_, field):
    with pytest.raises(RentalPeriodError) as error:
        check_period(pickup, return_)
    assert error.value.field == field


def test_the_messages_cite_br5():
    with pytest.raises(RentalPeriodError, match=r"at least 4 hours \(BR-5\)"):
        check_period(PICKUP, PICKUP + timedelta(hours=2))
    with pytest.raises(RentalPeriodError, match=r"at most 30 days \(BR-5\)"):
        check_period(PICKUP, PICKUP + timedelta(days=31))


@pytest.mark.parametrize("length", [timedelta(hours=4), timedelta(days=30)])
def test_the_br5_limits_themselves_are_allowed(length):
    check_period(PICKUP, PICKUP + length)


def test_the_search_refuses_a_bad_period(branch):
    with pytest.raises(RentalPeriodError):
        found(branch, PICKUP, PICKUP + timedelta(hours=1))


# ─── Vehicle.check_availability() (Exp 3) ─────────────────────────────────


def test_check_availability_for_a_free_vehicle(car):
    assert car.check_availability(PICKUP, RETURN) is True


def test_check_availability_ignores_other_vehicles(branch, car):
    other = CarFactory(home_branch=branch)
    book(other, PICKUP, RETURN)
    _job(other, MaintenanceJob.Status.SCHEDULED, PICKUP, RETURN)
    assert is_available(car, PICKUP, RETURN) is True


def test_check_availability_refuses_a_vehicle_that_cannot_be_handed_over(car):
    car.status = VStatus.UNSAFE
    assert is_available(car, PICKUP, RETURN) is False


def test_check_availability_refuses_before_the_availability_date(car):
    car.available_from = date(2026, 10, 20)
    assert is_available(car, PICKUP, RETURN) is False


def test_check_availability_refuses_a_held_vehicle(car):
    book(car, RETURN + timedelta(minutes=30), RETURN + timedelta(hours=6), Status.PENDING_PAYMENT)
    assert is_available(car, PICKUP, RETURN) is False


def test_check_availability_refuses_a_vehicle_in_the_workshop(car):
    _job(car, MaintenanceJob.Status.IN_PROGRESS, PICKUP, PICKUP + timedelta(hours=1))
    assert is_available(car, PICKUP, RETURN) is False
