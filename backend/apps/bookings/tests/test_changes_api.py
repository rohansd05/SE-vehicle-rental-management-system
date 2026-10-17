"""Module R2 over HTTP: modify, cancel and extend endpoints (SE-4, SE-5, SE-9) and the
History.View filters (date range, status, vehicle type, reference)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from freezegun import freeze_time

from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchManagerFactory,
    BranchStaffFactory,
    MaintenanceTechnicianFactory,
)
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings import lifecycle, states
from apps.bookings.models import Booking
from apps.bookings.tests.conftest import PASSWORD, eligible_customer
from apps.bookings.tests.factories import BookingFactory
from apps.core.models import AuditLog
from apps.fleet.tests.factories import CarFactory, TwoWheelerFactory

pytestmark = pytest.mark.django_db

S = Booking.Status
D = Decimal


def confirmed(customer, vehicle, pickup, return_, key="pay-api-r2-01"):
    booking = lifecycle.create_booking(
        customer, vehicle=vehicle, pickup=pickup, return_=return_, terms_accepted=True
    )
    return lifecycle.pay_booking(
        customer, booking.pk, payment_token="tok_visa", idempotency_key=key
    )


@pytest.fixture
def booking(customer, car, pickup, return_):
    return confirmed(customer, car, pickup, return_)


@pytest.fixture
def client(customer):
    return authenticated_client(customer.user)


def url(name, booking):
    return reverse(f"bookings:{name}", args=[booking.pk])


def period(booking, **extra):
    return {
        "pickup_datetime": booking.pickup_datetime.isoformat(),
        "return_datetime": booking.return_datetime.isoformat(),
        "pickup_branch": booking.pickup_branch_id,
        **extra,
    }


def paid(**extra):
    return {
        "payment_token": "tok_visa",
        "idempotency_key": "r2-api-key-01",
        "password": PASSWORD,
        **extra,
    }


# ─── Access: every endpoint, every role (SE-4, SE-5) ──────────────────────

ENDPOINTS = [
    ("get", "booking-cancel"),
    ("post", "booking-cancel"),
    ("post", "booking-modify-quote"),
    ("post", "booking-modify"),
    ("post", "booking-extend-quote"),
    ("post", "booking-extend"),
]
STAFF_ROLES = [BranchStaffFactory, BranchManagerFactory, AdministratorFactory]


@pytest.mark.parametrize(("method", "name"), ENDPOINTS)
@pytest.mark.parametrize(
    "factory", [*STAFF_ROLES, MaintenanceTechnicianFactory], ids=lambda f: f.__name__
)
def test_only_customers_change_bookings(booking, method, name, factory, branch):
    user = (
        factory(branch=branch).user
        if factory in (BranchStaffFactory, BranchManagerFactory)
        else factory().user
    )
    response = getattr(authenticated_client(user), method)(url(name, booking), {}, format="json")
    assert response.status_code == 403  # UC 4: the actor is the customer


@pytest.mark.parametrize(("method", "name"), ENDPOINTS)
def test_an_anonymous_visitor_is_asked_to_sign_in(api_client, booking, method, name):
    assert getattr(api_client, method)(url(name, booking), {}, format="json").status_code == 401


@pytest.mark.parametrize(("method", "name"), ENDPOINTS)
def test_another_customers_booking_is_not_found(booking, method, name):
    stranger = authenticated_client(eligible_customer().user)
    assert getattr(stranger, method)(url(name, booking), {}, format="json").status_code == 404


# ─── Cancel ───────────────────────────────────────────────────────────────


def test_the_customer_sees_the_refund_then_cancels(client, booking):
    quote = client.get(url("booking-cancel", booking))
    assert quote.status_code == 200
    assert quote.json() == {
        "notice_hours": quote.json()["notice_hours"],
        "refund_percent": "100.00",
        "rental_amount": "4248.00",
        "rental_refund": "4248.00",
        "deposit_refund": "5000.00",
        "total_refund": "9248.00",
        "awaits_approval": False,
    }
    response = client.post(
        url("booking-cancel", booking),
        {"expected_refund": "9248.00", "password": PASSWORD},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["status"] == S.CANCELLED
    assert [r["status"] for r in response.json()["refunds"]] == ["Issued", "Issued"]


def test_cancelling_asks_for_the_password(client, booking):
    response = client.post(
        url("booking-cancel", booking),
        {"expected_refund": "9248.00", "password": "wrong"},
        format="json",
    )
    assert response.status_code == 400 and "password" in response.json()
    assert AuditLog.objects.filter(action="Payment Re-authentication Failed").exists()
    booking.refresh_from_db()
    assert booking.status == S.CONFIRMED


def test_a_changed_refund_is_a_409(client, booking):
    response = client.post(
        url("booking-cancel", booking),
        {"expected_refund": "1.00", "password": PASSWORD},
        format="json",
    )
    assert (response.status_code, response.json()["code"]) == (409, "refund_changed")


def test_an_active_booking_cannot_be_cancelled_over_http(client, booking, pickup):
    with freeze_time(pickup):
        states.activate_booking(booking, None)
    assert client.get(url("booking-cancel", booking)).json()["code"] == "invalid_state"


# ─── Modify ───────────────────────────────────────────────────────────────


def test_the_customer_prices_then_makes_a_change(client, booking, return_):
    body = period(booking, return_datetime=(return_ + timedelta(days=1)).isoformat())
    quote = client.post(url("booking-modify-quote", booking), body, format="json")
    assert quote.status_code == 200
    data = quote.json()
    assert (data["extra_charge"], data["refund_amount"], data["vehicle_free"]) == (
        "2124.00",
        "0.00",
        True,
    )
    assert data["price"]["total_payable"] == "6372.00"
    response = client.post(
        url("booking-modify", booking),
        {**body, **paid(), "expected_charge": "2124.00", "expected_refund": "0.00"},
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["total_amount"] == "6372.00"


def test_a_busy_vehicle_lists_alternatives(client, booking, car, branch, return_):
    same = CarFactory(home_branch=branch, category=car.category, available_from=date(2026, 1, 1))
    later = return_ + timedelta(days=3)
    confirmed(eligible_customer(), car, later, later + timedelta(days=2), key="pay-api-r2-02")
    body = period(
        booking,
        pickup_datetime=later.isoformat(),
        return_datetime=(later + timedelta(days=2)).isoformat(),
    )
    data = client.post(url("booking-modify-quote", booking), body, format="json").json()
    assert data["vehicle_free"] is False
    assert [v["id"] for v in data["alternatives"]] == [same.pk]
    refused = client.post(
        url("booking-modify", booking),
        {**body, **paid(), "expected_charge": "0.00", "expected_refund": "0.00"},
        format="json",
    )
    assert (refused.status_code, refused.json()["code"]) == (409, "vehicle_unavailable")


def test_the_cut_off_is_a_409_that_says_so(customer, booking, pickup):
    with freeze_time(pickup - timedelta(hours=11)):
        client = authenticated_client(customer.user)  # a token valid at the frozen time
        response = client.post(url("booking-modify-quote", booking), period(booking), format="json")
    assert (response.status_code, response.json()["code"]) == (409, "modification_cutoff")


def test_a_declined_extra_charge_is_a_402(client, booking, return_):
    body = period(booking, return_datetime=(return_ + timedelta(days=1)).isoformat())
    response = client.post(
        url("booking-modify", booking),
        {
            **body,
            **paid(payment_token="tok_decline"),
            "expected_charge": "2124.00",
            "expected_refund": "0.00",
        },
        format="json",
    )
    assert (response.status_code, response.json()["code"]) == (402, "payment_declined")


def test_a_period_outside_br5_is_a_field_error(client, booking, pickup):
    body = period(booking, return_datetime=(pickup + timedelta(hours=3)).isoformat())
    response = client.post(url("booking-modify-quote", booking), body, format="json")
    assert response.status_code == 400 and "return_datetime" in response.json()


def test_modifying_asks_for_the_password(client, booking):
    response = client.post(
        url("booking-modify", booking),
        {
            **period(booking),
            **paid(password="wrong"),
            "expected_charge": "0",
            "expected_refund": "0",
        },
        format="json",
    )
    assert response.status_code == 400 and "password" in response.json()


# ─── Extend ───────────────────────────────────────────────────────────────


def test_the_customer_prices_then_extends_a_rental(customer, booking, pickup, return_):
    with freeze_time(pickup):
        states.activate_booking(booking, None)
    later = (return_ + timedelta(days=1)).isoformat()
    with freeze_time(pickup + timedelta(hours=1)):
        client = authenticated_client(customer.user)
        quote = client.post(
            url("booking-extend-quote", booking), {"return_datetime": later}, format="json"
        )
        assert (quote.status_code, quote.json()["extra_charge"]) == (200, "2124.00")
        response = client.post(
            url("booking-extend", booking),
            {"return_datetime": later, "expected_charge": "2124.00", **paid()},
            format="json",
        )
    assert response.status_code == 200
    assert (response.json()["status"], response.json()["total_amount"]) == (S.ACTIVE, "6372.00")


def test_a_confirmed_booking_cannot_be_extended_over_http(client, booking, return_):
    response = client.post(
        url("booking-extend-quote", booking),
        {"return_datetime": (return_ + timedelta(days=1)).isoformat()},
        format="json",
    )
    assert (response.status_code, response.json()["code"]) == (409, "invalid_state")


# ─── History.View filters ─────────────────────────────────────────────────


def test_history_filters_by_dates_status_vehicle_type_and_reference(customer, client):
    car = BookingFactory(
        customer=customer,
        pickup_datetime=pickup_at(2026, 11, 2),
        booking_reference="VRMS-20261020-0007",
    )
    scooter = BookingFactory(
        customer=customer,
        vehicle=TwoWheelerFactory(),
        status=S.CANCELLED,
        pickup_datetime=pickup_at(2026, 12, 5),
        booking_reference="VRMS-20261021-0042",
    )
    BookingFactory(pickup_datetime=pickup_at(2026, 11, 2))  # someone else's (History.Privacy)

    def ids(**params):
        response = client.get(reverse("bookings:booking-list"), params)
        assert response.status_code == 200
        return [row["id"] for row in response.json()["results"]]

    assert ids() == [scooter.pk, car.pk]
    assert ids(pickup_from="2026-11-01", pickup_to="2026-11-30") == [car.pk]
    assert ids(pickup_from="2026-12-05") == [scooter.pk]
    assert ids(status=S.CANCELLED) == [scooter.pk]
    assert ids(vehicle_type="Two-Wheeler") == [scooter.pk]
    assert ids(vehicle_type="Car", status=S.CONFIRMED) == [car.pk]
    assert ids(reference="0042") == [scooter.pk]
    assert ids(reference="vrms-20261020") == [car.pk]
    response = client.get(reverse("bookings:booking-list"), {"vehicle_type": "Lorry"})
    assert response.status_code == 400


def pickup_at(year, month, day):
    from django.utils import timezone

    return timezone.make_aware(timezone.datetime(year, month, day, 10, 0))
