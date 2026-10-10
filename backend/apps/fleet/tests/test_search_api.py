"""SRS 3.2 over HTTP: GET fleet/branches/, fleet/categories/ and fleet/search/.

The rules themselves are tested in test_availability.py; these tests cover
access (SE-4, Search.Browse), request validation, the response shape and the
query count.
"""

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
from apps.fleet.models import Car
from apps.fleet.tests.factories import (
    BranchFactory,
    CarFactory,
    TwoWheelerFactory,
    VehicleCategoryFactory,
)
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
    "admin": AdministratorFactory,
    "manager": BranchManagerFactory,
}


@pytest.fixture(autouse=True)
def _frozen_clock():
    with freeze_time(NOW):
        yield


@pytest.fixture
def branch():
    return BranchFactory(branch_name="Andheri")


def search(client, branch, pickup=PICKUP, return_=RETURN, **extra):
    params = {
        "branch": branch.pk,
        "pickup_datetime": pickup.isoformat(),
        "return_datetime": return_.isoformat(),
        **extra,
    }
    return client.get(reverse("fleet:search"), params)


# ─── Access (SE-4, Search.Browse) ─────────────────────────────────────────


@pytest.mark.parametrize("role", ["anonymous", *ROLE_FACTORIES])
@pytest.mark.parametrize("name", ["fleet:search", "fleet:branch-list", "fleet:category-list"])
def test_every_visitor_may_search_and_browse(api_client, branch, role, name):
    client = api_client if role == "anonymous" else authenticated_client(ROLE_FACTORIES[role]().user)
    if name == "fleet:search":
        response = search(client, branch)
    else:
        response = client.get(reverse(name))
    assert response.status_code == 200


def test_a_stale_token_does_not_block_a_public_search(api_client, branch):
    api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-valid-token")
    assert search(api_client, branch).status_code == 200


@pytest.mark.parametrize("name", ["fleet:search", "fleet:branch-list", "fleet:category-list"])
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_the_catalogue_is_read_only(api_client, name, method):
    assert getattr(api_client, method)(reverse(name)).status_code == 405


# ─── Validation ───────────────────────────────────────────────────────────


def test_the_branch_and_period_are_required(api_client):
    response = api_client.get(reverse("fleet:search"))
    assert response.status_code == 400
    assert set(response.data) == {"branch", "pickup_datetime", "return_datetime"}


def test_an_unknown_branch_is_refused(api_client, branch):
    response = api_client.get(
        reverse("fleet:search"),
        {
            "branch": branch.pk + 999,
            "pickup_datetime": PICKUP.isoformat(),
            "return_datetime": RETURN.isoformat(),
        },
    )
    assert response.status_code == 400
    assert "branch" in response.data


def test_an_unknown_category_is_refused(api_client, branch):
    response = search(api_client, branch, category=987654)
    assert response.status_code == 400
    assert "category" in response.data


def test_a_period_under_four_hours_is_refused_on_the_return_field(api_client, branch):
    response = search(api_client, branch, PICKUP, PICKUP + timedelta(hours=3))
    assert response.status_code == 400
    assert response.data == {"return_datetime": ["A rental lasts at least 4 hours (BR-5)."]}


def test_a_past_pickup_is_refused_on_the_pickup_field(api_client, branch):
    response = search(api_client, branch, NOW - timedelta(hours=1), NOW + timedelta(hours=5))
    assert response.status_code == 400
    assert list(response.data) == ["pickup_datetime"]


def test_a_local_time_with_an_offset_is_understood(api_client, branch):
    """CO-6: the server compares instants; 10:00+05:30 is 04:30 UTC."""
    CarFactory(home_branch=branch, available_from=IN_SERVICE)
    response = api_client.get(
        reverse("fleet:search"),
        {
            "branch": branch.pk,
            "pickup_datetime": "2026-10-13T10:00:00+05:30",
            "return_datetime": "2026-10-15T10:00:00+05:30",
        },
    )
    assert response.status_code == 200
    assert response.data["count"] == 1


# ─── Results ──────────────────────────────────────────────────────────────


def test_a_car_result_carries_its_specification(api_client, branch):
    car = CarFactory(
        home_branch=branch,
        available_from=IN_SERVICE,
        brand="Hyundai",
        model="Creta",
        transmission=Car.Transmission.AUTOMATIC,
        seating_capacity=5,
        last_service_date=date(2026, 9, 20),
    )
    RatingFactory(booking__vehicle=car, booking__tariff__vehicle_category=car.category, vehicle_rating=4)
    response = search(api_client, branch)
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0] == {
        "id": car.pk,
        "brand": "Hyundai",
        "model": "Creta",
        "year": car.year,
        "colour": car.colour,
        "fuel_type": car.fuel_type,
        "vehicle_type": "Car",
        "category": car.category.name,
        "category_id": car.category_id,
        "home_branch": "Andheri",
        "home_branch_id": branch.pk,
        "transmission": "Automatic",
        "seating_capacity": 5,
        "engine_cc": None,
        "average_rating": "4.00",
        "last_service_date": "2026-09-20",
        # Search.Price: two days at the factory tariff's 1800.00, plus 18% tax (PR9).
        "estimate": {
            "billing_unit": "day",
            "billing_count": 2,
            "total_payable": "4248.00",
            "security_deposit": "5000.00",
        },
    }


def test_a_two_wheeler_result_carries_its_engine(api_client, branch):
    TwoWheelerFactory(home_branch=branch, available_from=IN_SERVICE, engine_cc=125)
    result = search(api_client, branch).data["results"][0]
    assert result["vehicle_type"] == "Two-Wheeler"
    assert result["engine_cc"] == 125
    assert result["transmission"] is None
    assert result["seating_capacity"] is None
    assert result["average_rating"] is None
    assert result["estimate"] is None  # no tariff in force for its category


def test_a_booked_vehicle_is_left_out(api_client, branch):
    free = CarFactory(home_branch=branch, available_from=IN_SERVICE)
    taken = CarFactory(home_branch=branch, available_from=IN_SERVICE)
    BookingFactory(
        vehicle=taken,
        pickup_datetime=PICKUP + timedelta(hours=5),
        return_datetime=PICKUP + timedelta(hours=10),
        status=Booking.Status.CONFIRMED,
    )
    ids = [row["id"] for row in search(api_client, branch).data["results"]]
    assert ids == [free.pk]


def test_the_category_parameter_filters(api_client, branch):
    CarFactory(home_branch=branch, available_from=IN_SERVICE)
    scooter = TwoWheelerFactory(home_branch=branch, available_from=IN_SERVICE)
    response = search(api_client, branch, category=scooter.category_id)
    assert [row["id"] for row in response.data["results"]] == [scooter.pk]


def test_results_are_sorted_by_brand_and_model(api_client, branch):
    for brand, model in [("Tata", "Nexon"), ("Honda", "City"), ("Honda", "Amaze")]:
        CarFactory(home_branch=branch, available_from=IN_SERVICE, brand=brand, model=model)
    rows = search(api_client, branch).data["results"]
    assert [(row["brand"], row["model"]) for row in rows] == [
        ("Honda", "Amaze"),
        ("Honda", "City"),
        ("Tata", "Nexon"),
    ]


def test_results_are_paginated(api_client, branch):
    CarFactory.create_batch(21, home_branch=branch, available_from=IN_SERVICE)
    first = search(api_client, branch).data
    assert first["count"] == 21
    assert len(first["results"]) == 20
    assert first["next"] is not None
    assert len(search(api_client, branch, page=2).data["results"]) == 1


def test_the_query_count_does_not_grow_with_the_results(
    api_client, branch, django_assert_max_num_queries
):
    category = VehicleCategoryFactory(name="Hatchback")
    CarFactory.create_batch(6, home_branch=branch, available_from=IN_SERVICE, category=category)
    TwoWheelerFactory.create_batch(6, home_branch=branch, available_from=IN_SERVICE)
    TariffFactory(vehicle_category=category)
    with django_assert_max_num_queries(7):
        response = search(api_client, branch)
    assert response.data["count"] == 12


# ─── Estimated price (Search.Price) ───────────────────────────────────────


def test_the_estimate_uses_each_categorys_tariff_in_force(api_client, branch):
    scooter = TwoWheelerFactory(home_branch=branch, available_from=IN_SERVICE)
    TariffFactory(
        vehicle_category=scooter.category,
        hourly_rate="60.00",
        daily_rate="500.00",
        effective_from=NOW - timedelta(days=60),
    )
    TariffFactory(  # later, so it is the one in force
        vehicle_category=scooter.category,
        hourly_rate="70.00",
        daily_rate="600.00",
        effective_from=NOW - timedelta(days=1),
    )
    TariffFactory(  # not in force yet
        vehicle_category=scooter.category, daily_rate="900.00", effective_from=NOW + timedelta(days=1)
    )
    estimate = search(api_client, branch).data["results"][0]["estimate"]
    assert estimate == {
        "billing_unit": "day",
        "billing_count": 2,
        "total_payable": "1416.00",  # 2 x 600.00 + 18% tax
        "security_deposit": "2000.00",
    }


def test_a_short_search_is_estimated_in_hours(api_client, branch):
    car = CarFactory(home_branch=branch, available_from=IN_SERVICE)
    TariffFactory(vehicle_category=car.category, effective_from=NOW - timedelta(days=1))
    estimate = search(api_client, branch, PICKUP, PICKUP + timedelta(hours=5, minutes=10)).data[
        "results"
    ][0]["estimate"]
    assert (estimate["billing_unit"], estimate["billing_count"], estimate["total_payable"]) == (
        "hour",
        5,
        "885.00",  # 5 x 150.00 + 18%; 10 minutes is inside the grace (BR-6)
    )


# ─── Branches and categories ──────────────────────────────────────────────


def test_branches_are_listed_by_name(api_client):
    BranchFactory(branch_name="Thane")
    BranchFactory(branch_name="Andheri", address="Andheri (E), Mumbai")
    response = api_client.get(reverse("fleet:branch-list"))
    assert [row["branch_name"] for row in response.data] == ["Andheri", "Thane"]
    assert set(response.data[0]) == {"branch_id", "branch_name", "address"}


def test_categories_are_listed_with_their_vehicle_type(api_client):
    VehicleCategoryFactory(name="SUV")
    VehicleCategoryFactory(name="Scooter", vehicle_type="Two-Wheeler")
    response = api_client.get(reverse("fleet:category-list"))
    assert {(row["name"], row["vehicle_type"]) for row in response.data} == {
        ("SUV", "Car"),
        ("Scooter", "Two-Wheeler"),
    }
