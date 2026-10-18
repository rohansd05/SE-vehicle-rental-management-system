"""Module R4: the catalogue search (SRS 3.2 Search.Filter, Search.Price, Search.Detail;
Exp 2 UC 2 and its extension 3a; SA-2) over GET fleet/search/, fleet/search/alternatives/
and fleet/vehicles/{id}/."""

from datetime import UTC, date, datetime, timedelta

import pytest
from django.urls import reverse
from freezegun import freeze_time

from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchManagerFactory,
    BranchStaffFactory,
    CustomerFactory,
    MaintenanceTechnicianFactory,
)
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings.models import Booking
from apps.bookings.tests.factories import BookingFactory, RatingFactory
from apps.core.choices import FuelType, VehicleType
from apps.fleet.models import Car, Vehicle
from apps.fleet.services.availability import is_available, service_overdue
from apps.fleet.tests.factories import (
    BranchFactory,
    CarFactory,
    TwoWheelerFactory,
    VehicleCategoryFactory,
)
from apps.maintenance.models import MaintenanceJob
from apps.maintenance.tests.factories import MaintenanceJobFactory
from apps.pricing.tests.factories import TariffFactory

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 11, 6, 0, tzinfo=UTC)
PICKUP = datetime(2026, 10, 13, 4, 30, tzinfo=UTC)
RETURN = PICKUP + timedelta(days=2)
IN_SERVICE = date(2026, 9, 1)

ROLE_FACTORIES = {
    "customer": CustomerFactory,
    "staff": BranchStaffFactory,
    "technician": MaintenanceTechnicianFactory,
    "manager": BranchManagerFactory,
    "admin": AdministratorFactory,
}


@pytest.fixture(autouse=True)
def _frozen_clock():
    with freeze_time(NOW):
        yield


@pytest.fixture
def branch():
    return BranchFactory(branch_name="Andheri")


def _car(branch, daily="1800.00", category=None, **fields):
    category = category or VehicleCategoryFactory()
    car = CarFactory(home_branch=branch, available_from=IN_SERVICE, category=category, **fields)
    if not category.tariffs.exists():
        TariffFactory(
            vehicle_category=category, daily_rate=daily, effective_from=NOW - timedelta(days=1)
        )
    return car


def _scooter(branch, **fields):
    scooter = TwoWheelerFactory(
        home_branch=branch,
        available_from=IN_SERVICE,
        registration_no="MH01TW0001",
        chassis_number="TWCHASSIS0001",
        **fields,
    )
    if not scooter.category.tariffs.exists():
        TariffFactory(
            vehicle_category=scooter.category,
            daily_rate="600.00",
            effective_from=NOW - timedelta(days=1),
        )
    return scooter


def _rate(vehicle, *scores):
    for index, score in enumerate(scores):
        start = NOW - timedelta(days=20 + 3 * index)
        booking = BookingFactory(
            vehicle=vehicle,
            tariff=vehicle.category.tariffs.first(),
            status=Booking.Status.COMPLETED,
            pickup_datetime=start,
            return_datetime=start + timedelta(days=1),
        )
        RatingFactory(booking=booking, vehicle_rating=score)


def search(client, branch, pickup=PICKUP, return_=RETURN, name="fleet:search", **extra):
    params = {
        "branch": branch.pk,
        "pickup_datetime": pickup.isoformat(),
        "return_datetime": return_.isoformat(),
        **extra,
    }
    return client.get(reverse(name), params)


def ids(response) -> list[int]:
    assert response.status_code == 200, response.content
    return [vehicle["id"] for vehicle in response.data["results"]]


# ─── Search.Filter ────────────────────────────────────────────────────────


def test_filter_by_vehicle_type(api_client, branch):
    car, scooter = _car(branch), _scooter(branch)
    assert ids(search(api_client, branch, vehicle_type=VehicleType.CAR)) == [car.pk]
    assert ids(search(api_client, branch, vehicle_type=VehicleType.TWO_WHEELER)) == [scooter.pk]


def test_filter_by_category(api_client, branch):
    suv = _car(branch, category=VehicleCategoryFactory(name="SUV"))
    _car(branch, category=VehicleCategoryFactory(name="Hatchback"))
    assert ids(search(api_client, branch, category=suv.category_id)) == [suv.pk]


def test_filter_by_brand_and_model(api_client, branch):
    city = _car(branch, brand="Honda", model="City")
    _car(branch, brand="Hyundai", model="Verna")
    _car(branch, brand="Honda", model="Amaze")
    assert ids(search(api_client, branch, brand="honda", model="cit")) == [city.pk]


def test_filter_by_fuel(api_client, branch):
    ev = _car(branch, fuel_type=FuelType.ELECTRIC)
    _car(branch, fuel_type=FuelType.PETROL)
    assert ids(search(api_client, branch, fuel_type=FuelType.ELECTRIC)) == [ev.pk]


def test_filter_by_transmission_keeps_only_cars(api_client, branch):
    automatic = _car(branch, transmission=Car.Transmission.AUTOMATIC)
    _car(branch, transmission=Car.Transmission.MANUAL)
    _scooter(branch)
    assert ids(search(api_client, branch, transmission="Automatic")) == [automatic.pk]


def test_filter_by_minimum_seats(api_client, branch):
    seven = _car(branch, seating_capacity=7)
    _car(branch, seating_capacity=5)
    assert ids(search(api_client, branch, min_seats=6)) == [seven.pk]


def test_price_range_uses_the_estimate_for_the_period(api_client, branch):
    cheap = _car(branch, daily="1000.00")  # 2 days: 2,360.00 with 18% tax
    dear = _car(branch, daily="3000.00")  # 7,080.00
    assert ids(search(api_client, branch, max_price="3000")) == [cheap.pk]
    assert ids(search(api_client, branch, min_price="3000")) == [dear.pk]
    assert ids(search(api_client, branch, min_price="2360.00", max_price="7080.00", sort="price"))[
        :2
    ] == [cheap.pk, dear.pk]


def test_price_uses_the_tariff_in_force_on_the_searched_dates(api_client, branch):
    """N3 tariffs have effective dates: a tariff starting before the pickup prices the search."""
    car = _car(branch, daily="1000.00")
    TariffFactory(
        vehicle_category=car.category,
        daily_rate="3000.00",
        effective_from=PICKUP - timedelta(hours=1),  # after now, before the pickup
    )
    response = search(api_client, branch, max_price="3000")
    assert ids(response) == []
    result = search(api_client, branch).data["results"][0]
    assert result["estimate"]["total_payable"] == "7080.00"


def test_a_low_highest_price_is_refused_on_its_field(api_client, branch):
    response = search(api_client, branch, min_price="500", max_price="100")
    assert response.status_code == 400 and "max_price" in response.data


def test_filter_by_minimum_rating(api_client, branch):
    good, poor, unrated = _car(branch), _car(branch), _car(branch)
    _rate(good, 5, 4)
    _rate(poor, 2)
    assert ids(search(api_client, branch, min_rating="4")) == [good.pk]
    assert unrated.pk not in ids(search(api_client, branch, min_rating="1"))


@pytest.mark.parametrize("value", ["0", "5.5", "x"])
def test_a_minimum_rating_outside_1_to_5_is_refused(api_client, branch, value):
    assert search(api_client, branch, min_rating=value).status_code == 400


# ─── Sorting ──────────────────────────────────────────────────────────────


def test_sort_by_price_both_ways(api_client, branch):
    mid = _car(branch, daily="2000.00")
    low = _car(branch, daily="1000.00")
    high = _car(branch, daily="3000.00")
    assert ids(search(api_client, branch, sort="price")) == [low.pk, mid.pk, high.pk]
    assert ids(search(api_client, branch, sort="-price")) == [high.pk, mid.pk, low.pk]


def test_sort_by_rating_puts_unrated_last(api_client, branch):
    unrated, three, five = _car(branch), _car(branch), _car(branch)
    _rate(three, 3)
    _rate(five, 5)
    assert ids(search(api_client, branch, sort="rating")) == [five.pk, three.pk, unrated.pk]


def test_an_unknown_sort_is_refused(api_client, branch):
    assert search(api_client, branch, sort="colour").status_code == 400


def test_results_carry_the_rating_count(api_client, branch):
    car = _car(branch)
    _rate(car, 5, 4, 3)
    result = search(api_client, branch).data["results"][0]
    assert (result["average_rating"], result["rating_count"]) == ("4.00", 3)


# ─── Search.Available: what can actually be booked ────────────────────────


@pytest.mark.parametrize(
    "status",
    [Vehicle.Status.UNDER_MAINTENANCE, Vehicle.Status.UNSAFE, Vehicle.Status.RETIRED],
)
def test_vehicles_that_cannot_be_booked_are_never_offered(api_client, branch, status):
    _car(branch, status=status)
    assert ids(search(api_client, branch)) == []


def test_the_br1_buffer_still_applies(api_client, branch):
    car = _car(branch)
    BookingFactory(
        vehicle=car,
        tariff=car.category.tariffs.first(),
        pickup_datetime=PICKUP - timedelta(days=1),
        return_datetime=PICKUP - timedelta(minutes=30),  # 60-minute buffer reaches the pickup
    )
    assert ids(search(api_client, branch)) == []


# ─── SA-2: overdue for the preventive service (BR-15) ─────────────────────


def test_a_car_overdue_by_date_is_not_offered(api_client, branch):
    car = _car(
        branch, odometer=12000, last_service_odometer=11000, last_service_date=date(2026, 4, 10)
    )
    assert service_overdue(car)  # 6 months (BR-15) passed on 10 Oct 2026
    assert ids(search(api_client, branch)) == []
    assert not is_available(car, PICKUP, RETURN)


def test_a_car_overdue_by_distance_is_not_offered(api_client, branch):
    car = _car(
        branch, odometer=16000, last_service_odometer=11000, last_service_date=date(2026, 9, 1)
    )
    assert service_overdue(car)  # 5,000 km (BR-15) reached
    assert ids(search(api_client, branch)) == []


def test_a_car_not_yet_due_is_offered(api_client, branch):
    car = _car(
        branch, odometer=15999, last_service_odometer=11000, last_service_date=date(2026, 4, 12)
    )
    assert not service_overdue(car)
    assert ids(search(api_client, branch)) == [car.pk]


def test_a_vehicle_without_a_service_on_record_is_never_overdue(api_client, branch):
    car = _car(branch)
    assert not service_overdue(car)
    assert ids(search(api_client, branch)) == [car.pk]


def test_the_detail_marks_an_overdue_vehicle(api_client, branch):
    car = _car(
        branch, odometer=16000, last_service_odometer=11000, last_service_date=date(2026, 9, 1)
    )
    response = api_client.get(reverse("fleet:vehicle-detail", args=[car.pk]))
    assert response.status_code == 200 and response.data["service_overdue"] is True


# ─── UC 2 extension 3a: the nearest alternatives ──────────────────────────


def test_alternatives_by_branch(api_client, branch):
    bandra = BranchFactory(branch_name="Bandra")
    powai = BranchFactory(branch_name="Powai")
    _car(bandra)
    _car(bandra)
    _car(powai, brand="Tata")  # filtered out below
    response = search(api_client, branch, name="fleet:search-alternatives", brand="Maruti")
    assert response.status_code == 200
    by_branch = [row for row in response.data if row["branch"] != branch.pk]
    assert [(row["branch_name"], row["vehicles"]) for row in by_branch] == [("Bandra", 2)]
    assert datetime.fromisoformat(by_branch[0]["pickup_datetime"]) == PICKUP
    assert datetime.fromisoformat(by_branch[0]["return_datetime"]) == RETURN


def test_alternatives_by_date_nearest_first(api_client, branch):
    car = _car(branch)
    BookingFactory(  # holds the car for the searched period, plus BR-1's 60-minute buffer
        vehicle=car,
        tariff=car.category.tariffs.first(),
        pickup_datetime=PICKUP,
        return_datetime=RETURN,
    )
    response = search(api_client, branch, name="fleet:search-alternatives")
    shifts = [
        datetime.fromisoformat(row["pickup_datetime"]) - PICKUP
        for row in response.data
        if row["branch"] == branch.pk
    ]
    # +1, -1 and +2 days overlap the booking or its buffer; -2 and -3 start in the past.
    assert shifts == [timedelta(days=3)]


def test_no_alternatives_is_an_empty_list(api_client, branch):
    assert search(api_client, branch, name="fleet:search-alternatives").data == []


def test_alternatives_validate_like_the_search(api_client, branch):
    response = search(api_client, branch, return_=PICKUP, name="fleet:search-alternatives")
    assert response.status_code == 400 and "return_datetime" in response.data


# ─── Search.Detail ────────────────────────────────────────────────────────


def test_last_serviced_comes_from_the_latest_closed_job(api_client, branch):
    car = _car(branch, last_service_date=date(2026, 8, 1), last_service_odometer=11000)
    for service_date, status in [
        (date(2026, 9, 5), MaintenanceJob.Status.COMPLETED),
        (date(2026, 9, 20), MaintenanceJob.Status.COMPLETED),
        (date(2026, 10, 1), MaintenanceJob.Status.IN_PROGRESS),  # not closed
    ]:
        MaintenanceJobFactory(vehicle=car, status=status, service_date=service_date)
    detail = api_client.get(reverse("fleet:vehicle-detail", args=[car.pk])).data
    assert detail["last_service_date"] == "2026-09-20"
    assert search(api_client, branch).data["results"][0]["last_service_date"] == "2026-09-20"


def test_last_serviced_falls_back_to_the_service_on_record(api_client, branch):
    car = _car(branch, last_service_date=date(2026, 8, 1), last_service_odometer=11000)
    detail = api_client.get(reverse("fleet:vehicle-detail", args=[car.pk])).data
    assert detail["last_service_date"] == "2026-08-01"


def test_the_detail_carries_the_rating_and_its_count(api_client, branch):
    car = _car(branch)
    _rate(car, 4, 5)
    detail = api_client.get(reverse("fleet:vehicle-detail", args=[car.pk])).data
    assert (detail["average_rating"], detail["rating_count"]) == ("4.50", 2)
    assert detail["service_overdue"] is False


# ─── Access (SE-4, Search.Browse): public, for every role ─────────────────


@pytest.mark.parametrize("role", ["anonymous", *ROLE_FACTORIES])
@pytest.mark.parametrize("name", ["fleet:search", "fleet:search-alternatives"])
def test_every_visitor_may_search_with_filters(api_client, branch, role, name):
    _car(branch)
    client = (
        api_client if role == "anonymous" else authenticated_client(ROLE_FACTORIES[role]().user)
    )
    response = search(client, branch, name=name, sort="price", min_rating="1")
    assert response.status_code == 200


@pytest.mark.parametrize("role", ["anonymous", *ROLE_FACTORIES])
def test_every_visitor_may_view_a_vehicle(api_client, branch, role):
    car = _car(branch)
    client = (
        api_client if role == "anonymous" else authenticated_client(ROLE_FACTORIES[role]().user)
    )
    assert client.get(reverse("fleet:vehicle-detail", args=[car.pk])).status_code == 200


def test_the_search_stays_within_a_few_queries(api_client, branch, django_assert_max_num_queries):
    for _ in range(6):
        _rate(_car(branch), 4)
    with django_assert_max_num_queries(12):
        assert len(ids(search(api_client, branch, sort="rating", min_rating="1"))) == 6


def test_rating_constants_follow_uc6():
    from django.conf import settings

    assert settings.RATING_WINDOW == timedelta(days=14)
    assert settings.RATING_EDIT_WINDOW == timedelta(hours=24)
    assert isinstance(settings.SEARCH_ALTERNATIVE_DAYS, int)
