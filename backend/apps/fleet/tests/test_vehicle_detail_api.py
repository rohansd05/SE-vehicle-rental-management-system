"""Search.Detail over HTTP: GET fleet/vehicles/{id}/ (public, Search.Browse)."""

from datetime import date

import pytest
from django.urls import reverse

from apps.accounts.tests.factories import CustomerFactory
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings.tests.factories import RatingFactory
from apps.fleet.models import Vehicle
from apps.fleet.tests.factories import CarFactory, TwoWheelerFactory, VehiclePhotoFactory
from apps.pricing.tests.factories import TariffFactory

pytestmark = pytest.mark.django_db


def detail(client, vehicle):
    return client.get(reverse("fleet:vehicle-detail", args=[vehicle.pk]))


def test_anyone_may_see_a_vehicle(api_client):
    car = CarFactory()
    assert detail(api_client, car).status_code == 200
    assert detail(authenticated_client(CustomerFactory().user), car).status_code == 200


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_the_detail_is_read_only(api_client, method):
    url = reverse("fleet:vehicle-detail", args=[CarFactory().pk])
    assert getattr(api_client, method)(url).status_code == 405


def test_a_retired_vehicle_is_not_shown(api_client):
    """Fleet.Retire: a retired vehicle does not appear and is not bookable."""
    car = CarFactory(status=Vehicle.Status.RETIRED)
    assert detail(api_client, car).status_code == 404


def test_the_detail_shows_tariff_deposit_terms_rating_and_photos(api_client):
    car = CarFactory(last_service_date=date(2026, 9, 20))
    tariff = TariffFactory(vehicle_category=car.category)
    RatingFactory(booking__vehicle=car, booking__tariff=tariff, vehicle_rating=5)
    VehiclePhotoFactory.create_batch(4, vehicle=car)

    data = detail(api_client, car).json()
    assert data["id"] == car.pk
    assert data["status"] == "Available"
    assert data["vehicle_type"] == "Car"
    assert data["average_rating"] == "5.00"
    assert data["last_service_date"] == "2026-09-20"
    assert data["tariff"] == {
        "hourly_rate": "150.00",
        "daily_rate": "1800.00",
        "free_km_allowance_per_day": 250,
        "excess_km_rate": "12.00",
    }
    assert data["security_deposit"] == "5000.00"
    assert data["terms"]["cancellation_refunds"][1] == {
        "notice_hours_at_least": 12,
        "refund_percent": "75.00",
    }
    assert len(data["photos"]) == 4
    assert all("/api/v1/files/" in url for url in data["photos"])
    assert "estimate" not in data


def test_a_category_without_a_tariff_has_no_tariff_or_terms(api_client):
    data = detail(api_client, TwoWheelerFactory()).json()
    assert data["tariff"] is None
    assert data["terms"] is None
    assert data["security_deposit"] == "2000.00"  # BR-3 needs no tariff
    assert data["photos"] == []
