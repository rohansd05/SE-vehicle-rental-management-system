"""Pricing over HTTP: POST pricing/quote/ and GET pricing/add-ons/ (SE-4, Book.Quote.Display)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

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
from apps.core.choices import VehicleType
from apps.fleet.tests.factories import CarFactory, TwoWheelerFactory
from apps.pricing.models import DiscountCode
from apps.pricing.tests.factories import AddOnFactory, DiscountCodeFactory, TariffFactory

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 11, 6, 0, tzinfo=UTC)
PICKUP = datetime(2026, 10, 20, 4, 30, tzinfo=UTC)
RETURN = PICKUP + timedelta(days=2)


@pytest.fixture(autouse=True)
def _frozen_clock():
    with freeze_time(NOW):
        yield


@pytest.fixture
def car():
    vehicle = CarFactory()
    TariffFactory(vehicle_category=vehicle.category, effective_from=NOW - timedelta(days=30))
    return vehicle


@pytest.fixture
def customer_client():
    return authenticated_client(CustomerFactory().user)


def body(vehicle, **extra):
    return {
        "vehicle": vehicle.pk,
        "pickup_datetime": PICKUP.isoformat(),
        "return_datetime": RETURN.isoformat(),
        **extra,
    }


def post_quote(client, payload):
    return client.post(reverse("pricing:quote"), payload, format="json")


# ─── Access (SE-4) ────────────────────────────────────────────────────────


def test_an_anonymous_visitor_cannot_quote(api_client, car):
    assert post_quote(api_client, body(car)).status_code == 401


@pytest.mark.parametrize(
    "factory",
    [BranchStaffFactory, MaintenanceTechnicianFactory, AdministratorFactory, BranchManagerFactory],
    ids=lambda f: f.__name__,
)
def test_only_a_customer_can_quote(car, factory):
    client = authenticated_client(factory().user)
    assert post_quote(client, body(car)).status_code == 403


def test_the_add_on_list_is_public(api_client):
    assert api_client.get(reverse("pricing:add-on-list")).status_code == 200


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_the_add_on_list_is_read_only(api_client, method):
    assert getattr(api_client, method)(reverse("pricing:add-on-list")).status_code == 405


def test_a_quote_cannot_be_read_with_get(customer_client):
    assert customer_client.get(reverse("pricing:quote")).status_code == 405


# ─── The quote ────────────────────────────────────────────────────────────


def test_the_quote_is_itemised_with_the_deposit_apart(customer_client, car):
    seat = AddOnFactory(name="Child seat", daily_rate=Decimal("100.00"), vehicle_type=VehicleType.CAR)
    DiscountCodeFactory(code="WELCOME10", valid_from=NOW - timedelta(days=1))
    response = post_quote(
        customer_client,
        body(car, add_ons=[{"add_on": seat.pk, "quantity": 1}], discount_code="welcome10"),
    )
    assert response.status_code == 200
    data = response.json()
    terms = data.pop("terms")
    assert data == {
        "tariff_id": car.category.tariffs.get().pk,
        "billing_unit": "day",
        "billing_count": 2,
        "unit_rate": "1800.00",
        "base_charge": "3600.00",
        "add_ons": [
            {
                "add_on_id": seat.pk,
                "name": "Child seat",
                "quantity": 1,
                "daily_rate": "100.00",
                "days": 2,
                "amount": "200.00",
            }
        ],
        "add_ons_total": "200.00",
        "rental_charge": "3800.00",
        "discount_code": "WELCOME10",
        "discount_amount": "380.00",
        "taxable_amount": "3420.00",
        "tax_rate_percent": "18.00",
        "tax_amount": "615.60",
        "total_payable": "4035.60",
        "security_deposit": "5000.00",
        "free_helmets_per_rider": 0,
    }
    assert terms["excess_km_rate"] == "12.00"
    assert terms["cancellation_refunds"][0] == {"notice_hours_at_least": 48, "refund_percent": "100.00"}


def test_add_ons_and_code_are_optional(customer_client, car):
    response = post_quote(customer_client, body(car))
    assert response.status_code == 200
    assert response.json()["add_ons"] == []
    assert response.json()["total_payable"] == "4248.00"


def test_a_quote_saves_nothing_and_does_not_use_the_code(customer_client, car):
    discount = DiscountCodeFactory(code="ONCE", usage_limit=1, valid_from=NOW - timedelta(days=1))
    assert post_quote(customer_client, body(car, discount_code="ONCE")).status_code == 200
    discount.refresh_from_db()
    assert discount.times_used == 0
    assert Booking.objects.count() == 0


def test_a_two_wheeler_quote_has_the_smaller_deposit_and_a_free_helmet(customer_client):
    scooter = TwoWheelerFactory()
    TariffFactory(vehicle_category=scooter.category, effective_from=NOW - timedelta(days=1))
    data = post_quote(customer_client, body(scooter)).json()
    assert data["security_deposit"] == "2000.00"
    assert data["free_helmets_per_rider"] == 1


# ─── Refusals (400, on the field at fault) ────────────────────────────────


def test_a_period_under_four_hours_is_refused(customer_client, car):
    payload = body(car, return_datetime=(PICKUP + timedelta(hours=2)).isoformat())
    response = post_quote(customer_client, payload)
    assert response.status_code == 400
    assert response.json() == {"return_datetime": ["A rental lasts at least 4 hours (BR-5)."]}


def test_an_unknown_vehicle_is_refused(customer_client, car):
    response = post_quote(customer_client, {**body(car), "vehicle": car.pk + 999})
    assert response.status_code == 400
    assert "vehicle" in response.json()


def test_a_vehicle_without_a_tariff_is_refused(customer_client):
    response = post_quote(customer_client, body(CarFactory()))
    assert response.status_code == 400
    assert response.json() == {"vehicle": ["This vehicle has no tariff in force yet."]}


def test_an_add_on_for_the_other_vehicle_type_is_refused(customer_client, car):
    helmet = AddOnFactory(name="Additional helmet", vehicle_type=VehicleType.TWO_WHEELER)
    response = post_quote(customer_client, body(car, add_ons=[{"add_on": helmet.pk}]))
    assert response.status_code == 400
    assert response.json() == {
        "add_ons": ["Additional helmet is only offered with a two-wheeler."]
    }


def test_a_quantity_below_one_is_refused(customer_client, car):
    seat = AddOnFactory()
    response = post_quote(customer_client, body(car, add_ons=[{"add_on": seat.pk, "quantity": 0}]))
    assert response.status_code == 400
    assert "add_ons" in response.json()


def test_an_expired_code_is_refused(customer_client, car):
    DiscountCodeFactory(
        code="OLD",
        discount_type=DiscountCode.DiscountType.FIXED,
        valid_from=NOW - timedelta(days=10),
        valid_to=NOW - timedelta(days=1),
    )
    response = post_quote(customer_client, body(car, discount_code="OLD"))
    assert response.status_code == 400
    assert response.json() == {"discount_code": ["This discount code is not valid now."]}


# ─── Add-on list (Book.Addons) ────────────────────────────────────────────


def test_active_add_ons_are_listed_with_their_daily_rate(api_client):
    AddOnFactory(name="Child seat", daily_rate=Decimal("100.00"), vehicle_type=VehicleType.CAR)
    AddOnFactory(name="Retired item", is_active=False)
    response = api_client.get(reverse("pricing:add-on-list"))
    assert [(row["name"], row["daily_rate"], row["vehicle_type"]) for row in response.data] == [
        ("Child seat", "100.00", "Car")
    ]


def test_the_list_can_be_narrowed_to_a_vehicle_type(api_client):
    AddOnFactory(name="Child seat", vehicle_type=VehicleType.CAR)
    AddOnFactory(name="Additional helmet", vehicle_type=VehicleType.TWO_WHEELER)
    AddOnFactory(name="Doorstep delivery", vehicle_type="")
    response = api_client.get(reverse("pricing:add-on-list"), {"vehicle_type": "Two-Wheeler"})
    assert [row["name"] for row in response.data] == ["Additional helmet", "Doorstep delivery"]


def test_an_unknown_vehicle_type_is_refused(api_client):
    response = api_client.get(reverse("pricing:add-on-list"), {"vehicle_type": "Truck"})
    assert response.status_code == 400
    assert response.data == {"vehicle_type": ["Choose Car or Two-Wheeler."]}
