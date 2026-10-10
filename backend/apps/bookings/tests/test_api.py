"""Book Vehicle over HTTP: access (SE-4, SE-5), the answers for each alternative flow, the PDF."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from apps.accounts.models import Licence
from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchManagerFactory,
    BranchStaffFactory,
    MaintenanceTechnicianFactory,
)
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings.models import Booking
from apps.bookings.tests.conftest import PASSWORD, eligible_customer
from apps.bookings.tests.factories import BookingFactory
from apps.core.models import AuditLog
from apps.fleet.models import Vehicle

pytestmark = pytest.mark.django_db

S = Booking.Status


@pytest.fixture
def client(customer):
    return authenticated_client(customer.user)


def create_body(vehicle, pickup, return_, **extra):
    return {
        "vehicle": vehicle.pk,
        "pickup_datetime": pickup.isoformat(),
        "return_datetime": return_.isoformat(),
        "terms_accepted": True,
        **extra,
    }


def pay_body(**extra):
    return {
        "payment_token": "tok_visa",
        "idempotency_key": "pay-api-0001",
        "password": PASSWORD,
        **extra,
    }


def create(client, vehicle, pickup, return_, **extra):
    return client.post(
        reverse("bookings:booking-list"),
        create_body(vehicle, pickup, return_, **extra),
        format="json",
    )


def pay(client, booking_id, **extra):
    return client.post(
        reverse("bookings:booking-pay", args=[booking_id]), pay_body(**extra), format="json"
    )


# ─── Access (SE-4) ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "factory",
    [BranchStaffFactory, BranchManagerFactory, AdministratorFactory, MaintenanceTechnicianFactory],
    ids=lambda f: f.__name__,
)
def test_only_a_customer_can_book(factory, car, pickup, return_):
    response = create(authenticated_client(factory().user), car, pickup, return_)
    assert response.status_code == 403


def test_an_anonymous_visitor_cannot_book(api_client, car, pickup, return_):
    assert create(api_client, car, pickup, return_).status_code == 401


def test_a_technician_cannot_list_bookings():
    client = authenticated_client(MaintenanceTechnicianFactory().user)
    assert client.get(reverse("bookings:booking-list")).status_code == 403


@pytest.mark.parametrize("name", ["booking-pay", "booking-hold"])
def test_staff_cannot_pay_or_hold(name, car):
    booking = BookingFactory(vehicle=car)
    client = authenticated_client(AdministratorFactory().user)
    assert (
        client.post(reverse(f"bookings:{name}", args=[booking.pk]), {}, format="json").status_code
        == 403
    )


# ─── The main flow ────────────────────────────────────────────────────────


def test_create_then_pay(client, customer, car, pickup, return_):
    created = create(client, car, pickup, return_)
    assert created.status_code == 201
    data = created.json()
    assert data["status"] == "Pending Payment"
    assert data["hold_expires_at"] is not None
    assert data["price"]["total_payable"] == "4248.00"
    assert data["price"]["security_deposit"] == "5000.00"
    assert data["price"]["terms"]["late_return_hourly_rate"] == "150.00"
    assert data["booking_reference"] == "" and data["invoice_number"] is None

    paid = pay(client, data["id"])
    assert paid.status_code == 200
    confirmed = paid.json()
    assert confirmed["status"] == "Confirmed"
    assert confirmed["booking_reference"].startswith("VRMS-")
    assert len(confirmed["pickup_code"]) == 6  # shown to its customer (Book.Done.Store)
    assert confirmed["transaction_id"].startswith("TXN-")  # Pay.Confirm.OK
    assert confirmed["invoice_number"].startswith("INV-")
    assert confirmed["hold_expires_at"] is None


def test_the_invoice_downloads_as_a_pdf(client, customer, car, pickup, return_):
    booking_id = create(client, car, pickup, return_).json()["id"]
    invoice_number = pay(client, booking_id).json()["invoice_number"]
    response = client.get(reverse("bookings:booking-invoice", args=[booking_id]))
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"] == f'attachment; filename="{invoice_number}.pdf"'
    assert response.content.startswith(b"%PDF")


def test_a_held_booking_has_no_invoice_yet(client, car, pickup, return_):
    booking_id = create(client, car, pickup, return_).json()["id"]
    response = client.get(reverse("bookings:booking-invoice", args=[booking_id]))
    assert response.status_code == 404
    assert response.json() == {"detail": "This booking has no invoice yet."}


# ─── Alternative flows: each has its own answer ───────────────────────────


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (Licence.Status.PENDING_VERIFICATION, "licence_not_verified"),
        (Licence.Status.EXPIRED, "licence_expired"),
    ],
)
def test_a_licence_problem_is_answered_with_its_code(
    client, customer, car, pickup, return_, status, code
):
    Licence.objects.filter(customer=customer).update(status=status)
    response = create(client, car, pickup, return_)
    assert response.status_code == 400
    assert response.json()["code"] == code
    assert not Booking.objects.exists()


def test_a_taken_vehicle_is_a_409(client, car, pickup, return_):
    BookingFactory(vehicle=car, pickup_datetime=pickup, return_datetime=return_)
    response = create(client, car, pickup, return_)
    assert response.status_code == 409
    assert response.json()["code"] == "vehicle_unavailable"


def test_a_declined_payment_is_a_402_and_keeps_the_hold(client, car, pickup, return_):
    booking_id = create(client, car, pickup, return_).json()["id"]
    response = pay(client, booking_id, payment_token="tok_decline")
    assert response.status_code == 402
    assert response.json()["code"] == "payment_declined"
    assert Booking.objects.get(pk=booking_id).status == S.PENDING_PAYMENT
    assert pay(client, booking_id, idempotency_key="pay-api-0002").status_code == 200


def test_an_expired_hold_is_a_409_and_can_be_held_again(client, customer, car, pickup, return_):
    booking_id = create(client, car, pickup, return_).json()["id"]
    with freeze_time(timezone.now() + timedelta(minutes=16)):
        client = authenticated_client(customer.user)  # D19: access tokens last 5 minutes
        response = pay(client, booking_id)
        assert response.status_code == 409
        assert response.json()["code"] == "hold_expired"
        held = client.post(reverse("bookings:booking-hold", args=[booking_id]))
        assert held.status_code == 200
        assert held.json()["status"] == "Pending Payment"


def test_holding_a_held_booking_again_is_a_409(client, car, pickup, return_):
    booking_id = create(client, car, pickup, return_).json()["id"]
    response = client.post(reverse("bookings:booking-hold", args=[booking_id]))
    assert response.status_code == 409
    assert response.json()["code"] == "invalid_state"


# ─── Validation answers (400 on the field) ────────────────────────────────


def test_the_terms_must_be_accepted(client, car, pickup, return_):
    response = create(client, car, pickup, return_, terms_accepted=False)
    assert response.status_code == 400
    assert response.json() == {"terms_accepted": ["Accept the rental terms to continue."]}


def test_a_short_period_is_refused(client, car, pickup):
    response = create(client, car, pickup, pickup + timedelta(hours=1))
    assert response.status_code == 400
    assert "return_datetime" in response.json()


def test_a_missing_field_is_refused(client):
    response = client.post(reverse("bookings:booking-list"), {}, format="json")
    assert response.status_code == 400
    assert {"vehicle", "pickup_datetime", "return_datetime", "terms_accepted"} <= set(
        response.json()
    )


@pytest.mark.parametrize("key", ["short", "has spaces in it", "x" * 41])
def test_a_bad_idempotency_key_is_refused(client, car, pickup, return_, key):
    booking_id = create(client, car, pickup, return_).json()["id"]
    response = pay(client, booking_id, idempotency_key=key)
    assert response.status_code == 400
    assert "idempotency_key" in response.json()


# ─── SE-9: re-authentication before payment ───────────────────────────────


def test_a_wrong_password_stops_the_payment_and_is_audited(client, customer, car, pickup, return_):
    booking_id = create(client, car, pickup, return_).json()["id"]
    response = pay(client, booking_id, password="not-my-password")
    assert response.status_code == 400
    assert response.json() == {"password": ["That password is not correct."]}
    assert Booking.objects.get(pk=booking_id).status == S.PENDING_PAYMENT
    assert not Booking.objects.get(pk=booking_id).payments.exists()
    entry = AuditLog.objects.get(action="Payment Re-authentication Failed")
    assert (entry.actor_id, entry.entity_id) == (customer.user_id, str(booking_id))


def test_the_password_is_never_echoed(client, car, pickup, return_):
    booking_id = create(client, car, pickup, return_).json()["id"]
    assert PASSWORD not in pay(client, booking_id).content.decode()


# ─── Scoping (SE-5, History.Privacy) ──────────────────────────────────────


def test_another_customers_booking_is_invisible(car, pickup, return_):
    owner, stranger = eligible_customer(), eligible_customer()
    booking_id = create(authenticated_client(owner.user), car, pickup, return_).json()["id"]
    other = authenticated_client(stranger.user)
    for name in ("booking-detail", "booking-invoice"):
        assert other.get(reverse(f"bookings:{name}", args=[booking_id])).status_code == 404
    for name in ("booking-pay", "booking-hold"):
        assert (
            other.post(
                reverse(f"bookings:{name}", args=[booking_id]), pay_body(), format="json"
            ).status_code
            == 404
        )
    assert other.get(reverse("bookings:booking-list")).json()["count"] == 0


def test_branch_staff_see_their_branchs_bookings_without_the_pickup_code(
    client, car, pickup, return_
):
    booking_id = create(client, car, pickup, return_).json()["id"]
    pay(client, booking_id)
    staff = authenticated_client(BranchStaffFactory(branch=car.home_branch).user)
    data = staff.get(reverse("bookings:booking-detail", args=[booking_id])).json()
    assert data["booking_reference"].startswith("VRMS-")
    assert data["pickup_code"] == ""
    assert staff.get(reverse("bookings:booking-invoice", args=[booking_id])).status_code == 200
    elsewhere = authenticated_client(BranchStaffFactory().user)
    assert elsewhere.get(reverse("bookings:booking-detail", args=[booking_id])).status_code == 404


def test_the_history_lists_own_bookings_newest_pickup_first(client, customer, car, pickup):
    later = pickup + timedelta(days=10)
    first = create(client, car, pickup, pickup + timedelta(days=1)).json()["id"]
    second = create(client, car, later, later + timedelta(days=1)).json()["id"]
    BookingFactory()  # someone else's
    data = client.get(reverse("bookings:booking-list")).json()
    assert [row["id"] for row in data["results"]] == [second, first]
    filtered = client.get(reverse("bookings:booking-list"), {"status": "Confirmed"}).json()
    assert filtered["count"] == 0


def test_an_administrator_sees_every_booking():
    BookingFactory.create_batch(2)
    client = authenticated_client(AdministratorFactory().user)
    assert client.get(reverse("bookings:booking-list")).json()["count"] == 2


def test_the_vehicle_status_is_untouched_by_confirmation(client, car, pickup, return_):
    pay(client, create(client, car, pickup, return_).json()["id"])
    car.refresh_from_db()
    assert car.status == Vehicle.Status.AVAILABLE


def test_quoted_and_invoiced_totals_agree(client, car, pickup, return_):
    booking_id = create(client, car, pickup, return_).json()["id"]
    paid = pay(client, booking_id).json()
    assert Decimal(paid["total_amount"]) == Decimal(paid["price"]["total_payable"])
