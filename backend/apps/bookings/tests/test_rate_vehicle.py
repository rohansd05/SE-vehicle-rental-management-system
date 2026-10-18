"""Module R4: Exp 2 UC 6 Rate Vehicle (D13) over POST and PATCH bookings/{id}/rating/.

Preconditions, steps and extension 2a: only the customer's own Completed
booking, within 14 days of its return, once; vehicle and service scored 1 to
5 with an optional comment; editable within 24 hours of submission; the
vehicle's average rating and count are current at once.
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchManagerFactory,
    BranchStaffFactory,
    CustomerFactory,
    MaintenanceTechnicianFactory,
)
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings.models import Booking, Rating
from apps.bookings.services import RatingError, edit_rating, submit_rating
from apps.bookings.tests.factories import BookingFactory
from apps.core.models import AuditLog
from apps.fleet.models import Vehicle
from apps.fleet.services.catalogue import with_catalogue_facts

pytestmark = pytest.mark.django_db

SCORES = {"vehicle_rating": 4, "service_rating": 5, "comment": "Clean and on time."}


def completed(days_ago: float = 2, **fields) -> Booking:
    """A booking N2's complete_booking() closed `days_ago` days ago."""
    returned = timezone.now() - timedelta(days=days_ago)
    return BookingFactory(
        status=Booking.Status.COMPLETED,
        pickup_datetime=returned - timedelta(days=2),
        return_datetime=returned,
        returned_at=returned,
        **fields,
    )


def url(booking: Booking) -> str:
    return reverse("bookings:booking-rating", args=[booking.pk])


def rate(booking: Booking, data=SCORES, method="post"):
    client = authenticated_client(booking.customer.user)
    return getattr(client, method)(url(booking), data, format="json")


# ─── UC 6 steps 2-3 ───────────────────────────────────────────────────────


def test_a_completed_booking_is_rated_and_the_average_is_current():
    booking = completed()
    response = rate(booking)
    assert response.status_code == 201, response.content
    assert response.data["rating"]["vehicle_rating"] == 4
    assert response.data["rating"]["service_rating"] == 5
    assert response.data["rating_open_until"] is None  # rated: no further invitation
    vehicle = with_catalogue_facts(Vehicle.objects.filter(pk=booking.vehicle_id)).get()
    assert (vehicle.average_rating, vehicle.rating_count) == (Decimal("4"), 1)
    assert AuditLog.objects.filter(action="Create", entity_type="bookings.Rating").exists()


def test_the_comment_is_optional():
    response = rate(completed(), {"vehicle_rating": 3, "service_rating": 3})
    assert response.status_code == 201 and response.data["rating"]["comment"] == ""


@pytest.mark.parametrize("field", ["vehicle_rating", "service_rating"])
@pytest.mark.parametrize("value", [0, 6, "x"])
def test_scores_run_from_1_to_5(field, value):
    response = rate(completed(), {**SCORES, field: value})
    assert response.status_code == 400 and field in response.data
    assert not Rating.objects.exists()


def test_the_booking_invites_a_rating_while_it_can_be_given():
    booking = completed(days_ago=3)
    detail = authenticated_client(booking.customer.user).get(
        reverse("bookings:booking-detail", args=[booking.pk])
    )
    open_until = datetime.fromisoformat(detail.data["rating_open_until"])
    assert open_until == booking.returned_at + timedelta(days=14)
    assert detail.data["rating"] is None


# ─── Refusals, each with its message ──────────────────────────────────────


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (Booking.Status.CANCELLED, "A cancelled booking can't be rated."),
        (Booking.Status.NO_SHOW, "A booking that was not collected (no-show) can't be rated."),
        (Booking.Status.ACTIVE, "You can rate this rental once the vehicle has been returned."),
        (Booking.Status.CONFIRMED, "Only a completed booking can be rated."),
    ],
)
def test_a_booking_that_is_not_completed_is_refused(status, message):
    booking = BookingFactory(status=status)
    response = rate(booking)
    assert response.status_code == 409
    assert response.data == {"detail": message, "code": "rating_refused"}
    assert not Rating.objects.exists()


def test_a_booking_returned_more_than_14_days_ago_is_refused():
    response = rate(completed(days_ago=14.01))
    assert response.status_code == 409
    assert response.data["detail"] == "A rental can be rated only within 14 days of its return."


def test_a_booking_returned_just_under_14_days_ago_may_be_rated():
    assert rate(completed(days_ago=13.99)).status_code == 201


def test_a_booking_is_rated_only_once():
    booking = completed()
    rate(booking)
    response = rate(booking, {**SCORES, "vehicle_rating": 1})
    assert response.status_code == 409
    assert response.data["detail"] == "This booking has already been rated."
    assert Rating.objects.get().vehicle_rating == 4


def test_another_customers_booking_is_not_found():
    booking = completed()
    stranger = authenticated_client(CustomerFactory().user)
    assert stranger.post(url(booking), SCORES, format="json").status_code == 404
    assert stranger.patch(url(booking), SCORES, format="json").status_code == 404


def test_the_service_refuses_someone_elses_booking():
    with pytest.raises(RatingError, match="only your own"):
        submit_rating(CustomerFactory(), completed().pk, vehicle_rating=4, service_rating=4)


# ─── UC 6 extension 2a: edit within 24 hours ──────────────────────────────


def test_the_review_is_edited_within_24_hours_and_audited():
    booking = completed()
    rate(booking)
    with freeze_time(timezone.now() + timedelta(hours=23, minutes=59)):
        response = rate(booking, {**SCORES, "vehicle_rating": 2, "comment": ""}, "patch")
    assert response.status_code == 200, response.content
    assert response.data["rating"]["vehicle_rating"] == 2
    assert Rating.objects.get().comment == ""
    update = AuditLog.objects.get(action="Update", entity_type="bookings.Rating")
    assert (update.before["vehicle_rating"], update.after["vehicle_rating"]) == (4, 2)
    vehicle = with_catalogue_facts(Vehicle.objects.filter(pk=booking.vehicle_id)).get()
    assert vehicle.average_rating == Decimal("2")  # recalculated (UC 6 step 3)


def test_the_review_cannot_be_edited_after_24_hours():
    booking = completed()
    rate(booking)
    with freeze_time(timezone.now() + timedelta(hours=24, minutes=1)):
        response = rate(booking, {**SCORES, "vehicle_rating": 1}, "patch")
    assert response.status_code == 409
    assert (
        response.data["detail"] == "A review can be edited only within 24 hours of submitting it."
    )
    assert Rating.objects.get().vehicle_rating == 4


def test_editing_needs_a_review_first():
    booking = completed()
    response = rate(booking, method="patch")
    assert response.status_code == 409
    assert response.data["detail"] == "This booking has not been rated yet."
    with pytest.raises(RatingError):
        edit_rating(booking.customer, booking.pk, vehicle_rating=4, service_rating=4)


def test_the_detail_says_until_when_the_review_is_editable():
    booking = completed()
    response = rate(booking)
    editable_until = datetime.fromisoformat(response.data["rating"]["editable_until"])
    assert editable_until == Rating.objects.get().created_at + timedelta(hours=24)


# ─── Permissions (SE-4): only a customer rates ────────────────────────────

OTHER_ROLES = {
    "staff": BranchStaffFactory,
    "technician": MaintenanceTechnicianFactory,
    "manager": BranchManagerFactory,
    "admin": AdministratorFactory,
}


@pytest.mark.parametrize("method", ["post", "patch"])
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_staff_roles_cannot_rate(role, method):
    booking = completed()
    client = authenticated_client(OTHER_ROLES[role]().user)
    assert getattr(client, method)(url(booking), SCORES, format="json").status_code == 403


@pytest.mark.parametrize("method", ["post", "patch"])
def test_an_anonymous_visitor_cannot_rate(api_client, method):
    response = getattr(api_client, method)(url(completed()), SCORES, format="json")
    assert response.status_code == 401


@pytest.mark.parametrize("method", ["post", "patch"])
def test_the_customer_role_is_allowed(method):
    booking = completed()
    if method == "patch":
        rate(booking)
    assert rate(booking, method=method).status_code in (200, 201)
