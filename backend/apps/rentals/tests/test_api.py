"""Handover API (SRS 3.3; Exp 2 use case 7): scoping (SE-5), payloads and refusals.

Who may call which endpoint (SE-4) is in test_permissions.py.
"""

import json
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.factories import BranchManagerFactory, BranchStaffFactory
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings.models import Booking
from apps.bookings.tests.factories import BookingAddOnFactory, BookingFactory
from apps.fleet.models import Vehicle
from apps.pricing.tests.factories import AddOnFactory
from apps.rentals.tests.factories import image_file, ready_booking

pytestmark = pytest.mark.django_db

LIST = reverse("rentals:branch-bookings")


@pytest.fixture(autouse=True)
def _media_in_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def staff_client(booking):
    return authenticated_client(BranchStaffFactory(branch=booking.pickup_branch).user)


def detail_url(booking):
    return reverse("rentals:handover-detail", args=[booking.pk])


def complete_url(booking):
    return reverse("rentals:handover-complete", args=[booking.pk])


def form(**overrides) -> dict:
    data = {
        "odometer_reading": "15000",
        "fuel_level": "75",
        "accessories": json.dumps([{"name": "Child seat", "quantity": 1}]),
        "damage_marks": json.dumps([{"x": 20, "y": 80, "note": "Scratch"}]),
        "photo_front": image_file("front.jpg"),
        "photo_rear": image_file("rear.jpg"),
        "photo_left": image_file("left.jpg"),
        "photo_right": image_file("right.jpg"),
        "signature": image_file("signature.png", "PNG"),
    }
    data.update(overrides)
    return {key: value for key, value in data.items() if value is not None}


# ─── Branch bookings ──────────────────────────────────────────────────────


def test_branch_bookings_lists_only_the_callers_branch_and_hides_the_pickup_code():
    mine = BookingFactory(pickup_datetime=timezone.now())
    BookingFactory(pickup_datetime=timezone.now())  # another branch
    response = staff_client(mine).get(LIST)
    assert response.status_code == 200
    (row,) = response.json()["results"]
    assert row["id"] == mine.pk
    assert row["customer_name"] == mine.customer.user.name
    assert row["vehicle"]["registration_no"] == mine.vehicle.registration_no
    assert "pickup_code" not in row


def test_a_branch_manager_sees_their_branch_too():
    booking = BookingFactory(pickup_datetime=timezone.now() + timedelta(days=3))
    client = authenticated_client(BranchManagerFactory(branch=booking.pickup_branch).user)
    response = client.get(LIST, {"when": "upcoming"})
    assert [row["id"] for row in response.json()["results"]] == [booking.pk]


def test_find_by_pickup_code_stays_inside_the_branch():
    booking = BookingFactory()
    other_branch = BranchStaffFactory().user
    assert staff_client(booking).get(LIST, {"q": booking.pickup_code}).json()["count"] == 1
    response = authenticated_client(other_branch).get(LIST, {"q": booking.pickup_code})
    assert response.json()["count"] == 0


# ─── Handover detail ──────────────────────────────────────────────────────


def test_detail_shows_the_checklist_and_no_refusal_when_ready():
    booking = ready_booking()
    BookingAddOnFactory(booking=booking, add_on=AddOnFactory(name="Child seat"))
    data = staff_client(booking).get(detail_url(booking)).json()
    assert data["can_hand_over"] is True and data["refusals"] == []
    assert data["licence"]["status"] == "Verified"
    assert data["accessories"] == [{"name": "Child seat", "quantity": 1}]
    assert data["photo_sides"] == ["Front", "Rear", "Left", "Right"]
    assert data["terms"]["late_return_grace_minutes"] == 15  # BR-10, in the rental agreement
    assert data["report"] is None


def test_detail_states_which_condition_failed():
    booking = ready_booking()
    Vehicle.objects.filter(pk=booking.vehicle_id).update(status=Vehicle.Status.UNSAFE)
    data = staff_client(booking).get(detail_url(booking)).json()
    assert data["can_hand_over"] is False
    assert [r["code"] for r in data["refusals"]] == ["vehicle_unsafe"]
    assert "Unsafe" in data["refusals"][0]["message"]


def test_a_booking_of_another_branch_is_not_found():
    booking = ready_booking()
    client = authenticated_client(BranchStaffFactory().user)
    assert client.get(detail_url(booking)).status_code == 404
    assert client.post(complete_url(booking), form(), format="multipart").status_code == 404


# ─── Complete the handover ────────────────────────────────────────────────


def test_complete_hands_the_vehicle_over_and_returns_the_signed_report():
    booking = ready_booking()
    client = staff_client(booking)
    response = client.post(complete_url(booking), form(), format="multipart")
    assert response.status_code == 201, response.content
    data = response.json()
    assert data["status"] == "Active" and data["handed_over_at"]
    assert data["vehicle"]["status"] == "On Rent"
    report = data["report"]
    assert report["odometer_reading"] == 15000 and report["fuel_level"] == "75.00"
    assert [p["caption"] for p in report["photos"]] == ["Front", "Rear", "Left", "Right"]
    assert report["signature_url"] and report["signed_at"]
    # SI-3: the stored files come back only as signed links that work without a session.
    photo = client.get(report["photos"][0]["url"])
    assert photo.status_code == 200
    assert data["refusals"][0]["code"] == "already_handed_over"


def test_extra_photos_are_kept():
    booking = ready_booking()
    extras = [image_file("a.jpg"), image_file("b.jpg")]
    response = staff_client(booking).post(
        complete_url(booking), form(extra_photos=extras), format="multipart"
    )
    assert len(response.json()["report"]["photos"]) == 6


def test_a_refused_handover_is_409_with_every_failed_condition():
    booking = ready_booking()
    booking.payments.all().delete()
    response = staff_client(booking).post(complete_url(booking), form(), format="multipart")
    assert response.status_code == 409
    assert response.json()["code"] == "handover_refused"
    assert [r["code"] for r in response.json()["refusals"]] == ["payment_due"]
    assert Booking.objects.get(pk=booking.pk).status == Booking.Status.CONFIRMED


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"photo_left": None}, "photo_left"),  # Handover.Checklist: every side
        ({"signature": None}, "signature"),  # Handover.Sign
        ({"odometer_reading": None}, "odometer_reading"),
        ({"fuel_level": "101"}, "fuel_level"),
        ({"photo_rear": image_file("rear.gif")}, "photo_rear"),
        ({"accessories": json.dumps([{"name": "Seat", "quantity": 0}])}, "accessories"),
        ({"damage_marks": json.dumps([{"x": 120, "y": 5}])}, "damage_marks"),
        ({"damage_marks": "not json"}, "damage_marks"),
        ({"accessories": json.dumps({"name": "Seat"})}, "accessories"),
    ],
    ids=[
        "missing-side",
        "unsigned",
        "no-odometer",
        "fuel-over-100",
        "not-an-image-type",
        "zero-quantity",
        "mark-off-the-diagram",
        "bad-json",
        "not-a-list",
    ],
)
def test_an_incomplete_checklist_is_400(overrides, field):
    booking = ready_booking()
    response = staff_client(booking).post(
        complete_url(booking), form(**overrides), format="multipart"
    )
    assert response.status_code == 400
    assert field in response.json()
    assert Booking.objects.get(pk=booking.pk).status == Booking.Status.CONFIRMED


def test_a_corrupt_photo_is_refused():
    booking = ready_booking()
    image = SimpleUploadedFile(
        "front.jpg", b"\xff\xd8 not really a jpeg", content_type="image/jpeg"
    )
    response = staff_client(booking).post(
        complete_url(booking), form(photo_front=image), format="multipart"
    )
    assert response.status_code == 400 and "photo_front" in response.json()
