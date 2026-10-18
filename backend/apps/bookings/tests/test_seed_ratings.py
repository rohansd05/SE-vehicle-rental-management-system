"""Module R4 demo data: catalogue photos (plain seed_demo) and the Rate Vehicle demo
(seed_demo --reports, bookings/seed_ratings.py)."""

from io import StringIO

import pytest
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.urls import reverse

from apps.accounts.tests.helpers import authenticated_client
from apps.bookings.models import Booking, Rating
from apps.bookings.seed_ratings import RATER_EMAIL
from apps.core.models import AuditLog
from apps.fleet.models import BranchServiceableArea, Vehicle
from apps.pricing.models import AddOn
from apps.reports.seed import CUSTOMER_EMAIL

pytestmark = pytest.mark.django_db


def _seed(*args):
    call_command("seed_demo", *args, stdout=StringIO())


def test_every_demo_vehicle_has_four_photos_and_the_delivery_data():
    _seed()
    for vehicle in Vehicle.objects.filter(chassis_number__startswith="DEMO"):
        photos = list(vehicle.photos.all())
        assert len(photos) >= 4, vehicle
        assert all(default_storage.exists(photo.image.name) for photo in photos)
    assert BranchServiceableArea.objects.exists()
    assert AddOn.objects.filter(name="Doorstep delivery", is_active=True).exists()
    assert not Rating.objects.exists()  # the rating demo needs --reports


def test_the_detail_shows_the_seeded_photos(api_client):
    _seed()
    vehicle = Vehicle.objects.filter(chassis_number__startswith="DEMOCHASSIS").first()
    detail = api_client.get(reverse("fleet:vehicle-detail", args=[vehicle.pk]))
    assert len(detail.data["photos"]) == 4


def test_the_rating_demo_rates_and_invites():
    _seed("--reports")
    _seed("--reports")  # idempotent
    rated = Rating.objects.filter(booking__customer__user__email=CUSTOMER_EMAIL)
    assert rated.count() == 5
    assert AuditLog.objects.filter(action="Create", entity_type="bookings.Rating").count() == 5

    rater = Booking.objects.filter(customer__user__email=RATER_EMAIL).order_by("-pickup_datetime")
    assert list(rater.values_list("status", flat=True)) == ["Completed", "Completed"]
    recent, old = rater
    client = authenticated_client(recent.customer.user)
    assert client.get(reverse("bookings:booking-detail", args=[recent.pk])).data[
        "rating_open_until"
    ]
    assert not client.get(reverse("bookings:booking-detail", args=[old.pk])).data[
        "rating_open_until"
    ]
    refused = client.post(
        reverse("bookings:booking-rating", args=[old.pk]),
        {"vehicle_rating": 4, "service_rating": 4},
        format="json",
    )
    assert refused.status_code == 409  # older than 14 days (UC 6)
    accepted = client.post(
        reverse("bookings:booking-rating", args=[recent.pk]),
        {"vehicle_rating": 5, "service_rating": 5},
        format="json",
    )
    assert accepted.status_code == 201
