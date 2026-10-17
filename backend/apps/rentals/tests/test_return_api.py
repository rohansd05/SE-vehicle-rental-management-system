"""Return Vehicle API (SRS 3.3 Return.*; Exp 2 use case 8): scoping (SE-5), payloads,
refusals and the double Settle. Who may call which endpoint (SE-4) is in
test_permissions.py."""

import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.factories import BranchManagerFactory, BranchStaffFactory
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings.models import Booking
from apps.bookings.tests.factories import BookingFactory
from apps.payments.models import LedgerEntry, RefundRequest
from apps.rentals.tests.factories import active_booking, image_file

pytestmark = pytest.mark.django_db

LIST = reverse("rentals:returns")


@pytest.fixture(autouse=True)
def _media_in_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def staff_client(booking):
    return authenticated_client(BranchStaffFactory(branch=booking.pickup_branch).user)


def url(name, booking):
    return reverse(f"rentals:{name}", args=[booking.pk])


def readings(**overrides) -> dict:
    data = {
        "odometer_reading": 12400,
        "fuel_level": "100",
        "returned_at": (timezone.now() - timedelta(minutes=1)).isoformat(),
    }
    data.update(overrides)
    return data


def form(**overrides) -> dict:
    """The multipart form of an on-time return 150 km over the allowance (1,770.00 at 18%)."""
    data = {
        **readings(),
        "missing_accessories": json.dumps([]),
        "damage_charges": json.dumps([]),
        "damage_marks": json.dumps([{"x": 50, "y": 85, "note": "Rear: new scratch"}]),
        "expected_total": "2124.00",
        "photo_front": image_file("front.jpg"),
        "photo_rear": image_file("rear.jpg"),
        "photo_left": image_file("left.jpg"),
        "photo_right": image_file("right.jpg"),
        "signature": image_file("signature.png", "PNG"),
    }
    data.update(overrides)
    return {key: value for key, value in data.items() if value is not None}


# ─── The desk list (UC 8 step 1) ──────────────────────────────────────────


def test_returns_lists_only_the_callers_branch():
    mine = active_booking()
    active_booking()  # another branch
    response = staff_client(mine).get(LIST)
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["results"]] == [mine.pk]
    assert "pickup_code" not in response.json()["results"][0]


def test_a_branch_manager_finds_a_rental_by_reference():
    booking = active_booking(due_in=timedelta(days=3))
    client = authenticated_client(BranchManagerFactory(branch=booking.pickup_branch).user)
    assert client.get(LIST).json()["count"] == 0  # not due yet
    found = client.get(LIST, {"q": booking.booking_reference}).json()
    assert [row["id"] for row in found["results"]] == [booking.pk]


# ─── Detail ───────────────────────────────────────────────────────────────


def test_detail_shows_the_handover_report_what_is_paid_and_the_terms():
    booking = active_booking()
    data = staff_client(booking).get(url("return-detail", booking)).json()
    assert data["can_return"] is True and data["refusals"] == []
    assert data["handover_report"]["report_type"] == "Handover"
    assert data["handover_report"]["odometer_reading"] == 12000
    assert data["return_report"] is None and data["settlement"] is None
    assert data["photo_sides"] == ["Front", "Rear", "Left", "Right"]
    paid = [{"description": "Rental charge (Book.Done)", "amount": "1800.00"}]
    assert data["rental_paid"] == paid
    assert data["security_deposit"] == "5000.00" and data["deposit_method"] == "Card"
    assert data["vehicle"]["fuel_capacity"] == "40.00"
    assert data["terms"]["late_return_grace_minutes"] == 15  # BR-10


def test_a_booking_of_another_branch_is_not_found():
    booking = active_booking()
    client = authenticated_client(BranchStaffFactory().user)
    assert client.get(url("return-detail", booking)).status_code == 404
    assert client.post(url("return-quote", booking), readings(), format="json").status_code == 404
    response = client.post(url("return-complete", booking), form(), format="multipart")
    assert response.status_code == 404


# ─── Quote (Return.Charges) ───────────────────────────────────────────────


def test_quote_itemises_the_settlement_and_saves_nothing():
    booking = active_booking()
    response = staff_client(booking).post(
        url("return-quote", booking),
        readings(missing_accessories=[{"name": "Child seat", "quantity": 1, "cost": "500.00"}]),
        format="json",
    )
    assert response.status_code == 200, response.content
    data = response.json()
    assert [(line["kind"], line["amount"]) for line in data["lines"]] == [
        ("excess_km", "1800.00"),
        ("accessory", "500.00"),
        ("tax", "414.00"),
    ]
    assert (data["total"], data["deposit_used"], data["refund"], data["due"]) == (
        "2714.00",
        "2714.00",
        "2286.00",
        "0.00",
    )
    assert data["accessories_returned"] == [] and data["override_required"] is False
    assert data["distance"] == 400 and data["free_km"] == 250
    assert Booking.objects.get(pk=booking.pk).status == Booking.Status.ACTIVE


def test_a_reading_below_the_handover_is_400_on_the_field():
    booking = active_booking()
    response = staff_client(booking).post(
        url("return-quote", booking), readings(odometer_reading=11000), format="json"
    )
    assert response.status_code == 400
    assert response.json()["code"] == "odometer_lower"
    assert "odometer_reading" in response.json()


def test_quoting_a_booking_not_handed_over_is_409_with_the_reason():
    booking = BookingFactory()  # Confirmed
    response = staff_client(booking).post(url("return-quote", booking), readings(), format="json")
    assert response.status_code == 409
    assert response.json()["code"] == "return_refused"
    assert [r["code"] for r in response.json()["refusals"]] == ["not_handed_over"]


# ─── Complete (BranchStaff.return_vehicle()) ──────────────────────────────


def test_complete_returns_the_signed_settlement():
    booking = active_booking()
    client = staff_client(booking)
    response = client.post(url("return-complete", booking), form(), format="multipart")
    assert response.status_code == 201, response.content
    data = response.json()
    assert data["status"] == "Completed" and data["distance_travelled"] == 400
    assert data["vehicle"]["status"] == "Available" and data["vehicle"]["odometer"] == 12400
    report = data["return_report"]
    assert report["report_type"] == "Return" and report["signature_url"]
    assert [p["caption"] for p in report["photos"]] == ["Front", "Rear", "Left", "Right"]
    assert report["damage_marks"] == [{"x": 50, "y": 85, "note": "Rear: new scratch"}]
    settlement = data["settlement"]
    assert settlement["total"] == "2124.00" and settlement["refund"] == "2876.00"
    assert settlement["refund_status"] == RefundRequest.Status.ISSUED
    assert data["refusals"][0]["code"] == "already_returned"
    # SI-3: the photos come back as signed links that work without a session.
    assert client.get(report["photos"][0]["url"]).status_code == 200


def test_a_double_click_on_settle_charges_once():
    booking = active_booking()
    client = staff_client(booking)
    first = client.post(url("return-complete", booking), form(), format="multipart")
    entries = LedgerEntry.objects.count()
    second = client.post(url("return-complete", booking), form(), format="multipart")
    assert (first.status_code, second.status_code) == (201, 201)
    assert second.json()["settlement"] == first.json()["settlement"]
    assert LedgerEntry.objects.count() == entries
    assert RefundRequest.objects.count() == 1


def test_changed_charges_are_409_and_change_nothing():
    booking = active_booking()
    response = staff_client(booking).post(
        url("return-complete", booking), form(expected_total="0.00"), format="multipart"
    )
    assert response.status_code == 409 and response.json()["code"] == "settlement_changed"
    assert Booking.objects.get(pk=booking.pk).status == Booking.Status.ACTIVE


def test_a_cancelled_booking_cannot_be_returned():
    booking = BookingFactory(status=Booking.Status.CANCELLED)
    response = staff_client(booking).post(
        url("return-complete", booking), form(), format="multipart"
    )
    assert response.status_code == 409
    assert response.json()["refusals"][0]["code"] == "booking_cancelled"


def test_flagging_needs_a_severity_and_whether_the_vehicle_is_fit():
    booking = active_booking()
    response = staff_client(booking).post(
        url("return-complete", booking), form(flag_problem="Brakes squeal"), format="multipart"
    )
    assert response.status_code == 400
    assert {"flag_severity", "flag_unfit"} <= set(response.json())


def test_a_flagged_unfit_vehicle_goes_under_maintenance():
    booking = active_booking()
    response = staff_client(booking).post(
        url("return-complete", booking),
        form(flag_problem="Brakes squeal", flag_severity="High", flag_unfit="true"),
        format="multipart",
    )
    assert response.status_code == 201, response.content
    data = response.json()
    assert data["vehicle"]["status"] == "Under Maintenance"
    assert data["settlement"]["maintenance_job"] is not None


def test_an_implausible_distance_without_an_override_is_400():
    booking = active_booking()
    response = staff_client(booking).post(
        url("return-complete", booking),
        form(odometer_reading="14000", expected_total="24780.00"),  # 1,750 km over
        format="multipart",
    )
    assert response.status_code == 400, response.content
    assert response.json()["code"] == "override_required"
    assert "override_reason" in response.json()


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"photo_right": None}, "photo_right"),  # Return.Checklist: at least four photographs
        ({"signature": None}, "signature"),  # the customer acknowledges the settlement
        ({"returned_at": None}, "returned_at"),  # "the actual return time"
        ({"expected_total": None}, "expected_total"),
        (
            {"damage_charges": json.dumps([{"description": "Dent", "amount": "10"}])},
            "damage_charges",
        ),
        (
            {"missing_accessories": json.dumps([{"name": "Seat", "quantity": 1}])},
            "missing_accessories",
        ),
    ],
    ids=["missing-side", "unsigned", "no-return-time", "no-total", "no-justification", "no-cost"],
)
def test_an_incomplete_return_is_400(overrides, field):
    booking = active_booking()
    response = staff_client(booking).post(
        url("return-complete", booking), form(**overrides), format="multipart"
    )
    assert response.status_code == 400
    assert field in response.json()
    assert Booking.objects.get(pk=booking.pk).status == Booking.Status.ACTIVE


def test_r1s_refusal_is_passed_on_and_nothing_changes():
    booking = active_booking()
    booking.payments.update(status="Failed")  # as if nothing had been paid
    client = staff_client(booking)
    assert client.get(url("return-detail", booking)).json()["deposit_method"] is None
    response = client.post(url("return-complete", booking), form(), format="multipart")
    assert response.status_code == 409 and response.json()["code"] == "not_paid"
    assert Booking.objects.get(pk=booking.pk).status == Booking.Status.ACTIVE


def test_the_settlement_shows_a_refund_awaiting_approval(settings):
    settings.REFUND_AUTO_APPROVAL_LIMIT = Decimal("1000.00")
    booking = active_booking()
    response = staff_client(booking).post(
        url("return-complete", booking), form(), format="multipart"
    )
    assert response.json()["settlement"]["refund_status"] == "Pending Approval"
