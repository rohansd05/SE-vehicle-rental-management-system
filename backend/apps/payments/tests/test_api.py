"""Payments over HTTP: every endpoint and role (SE-4), scoping (SE-5), SE-9, Pay.Idempotent."""

import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchManagerFactory,
    BranchStaffFactory,
    MaintenanceTechnicianFactory,
)
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings import lifecycle
from apps.core.models import AuditLog
from apps.payments import services
from apps.payments.models import Payment, RefundRequest
from apps.payments.tests.conftest import (
    PASSWORD,
    cash_confirmed,
    confirmed,
    eligible_customer,
    held,
    original,
)
from integrations.payment_gateway.mock import MockPaymentGateway

pytestmark = pytest.mark.django_db

ROLES = ["anonymous", "customer", "staff", "technician", "manager", "admin"]


@pytest.fixture
def people(customer, branch):
    return {
        "customer": customer.user,
        "staff": BranchStaffFactory(branch=branch).user,
        "technician": MaintenanceTechnicianFactory().user,
        "manager": BranchManagerFactory(branch=branch).user,
        "admin": AdministratorFactory().user,
    }


def client_for(people, role) -> APIClient:
    return APIClient() if role == "anonymous" else authenticated_client(people[role])


# Each case: set up what the endpoint needs, then return (method, url, body).


def due_get(ctx):
    return "get", reverse("payments:due"), None


def due_post(ctx):
    services.record_due(ctx["customer"], Decimal("100.00"), "Fuel")
    body = {"payment_token": "tok_visa", "idempotency_key": "due-api-0001", "password": PASSWORD}
    return "post", reverse("payments:due"), body


def capture(ctx):
    booking = confirmed(ctx["customer"], ctx["car"], ctx["pickup"], ctx["return_"])
    body = {
        "lines": [{"description": "Fuel shortfall (BR-12)", "amount": "250.00"}],
        "idempotency_key": "capture-api-1",
        "password": PASSWORD,
    }
    return "post", reverse("payments:booking-capture", args=[booking.pk]), body


def refund_create(ctx):
    booking = confirmed(ctx["customer"], ctx["car"], ctx["pickup"], ctx["return_"])
    body = {
        "amount": "10.00",
        "reason": "Goodwill",
        "idempotency_key": "refund-api-1",
        "password": PASSWORD,
    }
    return "post", reverse("payments:payment-refund", args=[original(booking).pk]), body


def refund_list(ctx):
    return "get", reverse("payments:refund-list"), None


def _pending(ctx):
    booking = confirmed(
        ctx["customer"], ctx["car"], ctx["pickup"], ctx["pickup"] + timedelta(days=3)
    )
    return services.refund_payment(
        original(booking), Decimal("6372.00"), "Cancelled", ctx["people"]["staff"]
    )


def approve(ctx):
    return (
        "post",
        reverse("payments:refund-approve", args=[_pending(ctx).pk]),
        {"password": PASSWORD},
    )


def reject(ctx):
    url = reverse("payments:refund-reject", args=[_pending(ctx).pk])
    return "post", url, {"reason": "After the cut-off.", "password": PASSWORD}


def pay_out(ctx):
    booking = cash_confirmed(
        ctx["customer"], ctx["car"], ctx["pickup"], ctx["return_"], ctx["people"]["staff"]
    )
    deposit = Payment.objects.get(
        booking=booking, original_payment=None, purpose="Security Deposit"
    )
    refund = services.refund_payment(deposit, Decimal("1000.00"), "Balance", ctx["people"]["admin"])
    body = {"customer_acknowledged": True, "password": PASSWORD}
    return "post", reverse("payments:refund-pay-out", args=[refund.pk]), body


def awaiting_cash(ctx):
    return "get", reverse("bookings:booking-awaiting-cash"), None


def _cash_chosen(ctx):
    booking = held(ctx["customer"], ctx["car"], ctx["pickup"], ctx["return_"])
    lifecycle.pay_booking(ctx["customer"], booking.pk, idempotency_key="choose-cash", method="cash")
    return booking


def record_cash(ctx):
    body = {"amount_received": "9248.00", "idempotency_key": "cash-api-0001", "password": PASSWORD}
    return "post", reverse("bookings:booking-cash", args=[_cash_chosen(ctx).pk]), body


def pay_cash(ctx):
    booking = held(ctx["customer"], ctx["car"], ctx["pickup"], ctx["return_"])
    body = {"method": "cash", "idempotency_key": "pay-cash-001", "password": PASSWORD}
    return "post", reverse("bookings:booking-pay", args=[booking.pk]), body


CUSTOMER_ONLY = {
    "anonymous": 401,
    "customer": 200,
    "staff": 403,
    "technician": 403,
    "manager": 403,
    "admin": 403,
}
STAFF_ONLY = {
    "anonymous": 401,
    "customer": 403,
    "staff": 200,
    "technician": 403,
    "manager": 403,
    "admin": 403,
}
ADMIN_ONLY = {
    "anonymous": 401,
    "customer": 403,
    "staff": 403,
    "technician": 403,
    "manager": 403,
    "admin": 200,
}
SETTLERS = {
    "anonymous": 401,
    "customer": 403,
    "staff": 200,
    "technician": 403,
    "manager": 403,
    "admin": 200,
}
CASES = [
    ("due-get", due_get, CUSTOMER_ONLY),
    ("due-post", due_post, CUSTOMER_ONLY),
    ("capture", capture, SETTLERS),
    ("refund-create", refund_create, {**SETTLERS, "staff": 201, "admin": 201}),
    (
        "refund-list",
        refund_list,
        {
            "anonymous": 401,
            "customer": 200,
            "staff": 200,
            "technician": 403,
            "manager": 200,
            "admin": 200,
        },
    ),
    ("approve", approve, ADMIN_ONLY),
    ("reject", reject, ADMIN_ONLY),
    ("pay-out", pay_out, STAFF_ONLY),
    ("awaiting-cash", awaiting_cash, STAFF_ONLY),
    ("record-cash", record_cash, STAFF_ONLY),
    ("pay-cash", pay_cash, CUSTOMER_ONLY),
]


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize(("name", "case", "expected"), CASES, ids=[c[0] for c in CASES])
def test_every_endpoint_for_every_role(
    name, case, expected, role, people, customer, car, pickup, return_
):
    ctx = {"people": people, "customer": customer, "car": car, "pickup": pickup, "return_": return_}
    method, url, body = case(ctx)
    response = getattr(client_for(people, role), method)(url, body, format="json")
    assert response.status_code == expected[role], response.content


@pytest.mark.parametrize("role", ROLES)
def test_the_gateway_notification_needs_only_its_signature(role, people):
    body = json.dumps({"id": f"evt_{role}", "type": "payment.captured"}).encode()
    response = client_for(people, role).post(
        reverse("payments:webhook"),
        data=body,
        content_type="application/json",
        HTTP_X_GATEWAY_SIGNATURE=MockPaymentGateway.sign(body),
    )
    assert response.status_code == 200


# ─── SE-9: the caller's password before money moves ──────────────────────

MONEY_CASES = [
    ("due-post", due_post, "customer"),
    ("capture", capture, "staff"),
    ("refund-create", refund_create, "staff"),
    ("approve", approve, "admin"),
    ("reject", reject, "admin"),
    ("pay-out", pay_out, "staff"),
    ("record-cash", record_cash, "staff"),
]


@pytest.mark.parametrize(("name", "case", "role"), MONEY_CASES, ids=[c[0] for c in MONEY_CASES])
def test_a_wrong_password_moves_no_money_and_is_audited(
    name, case, role, people, customer, car, pickup, return_
):
    ctx = {"people": people, "customer": customer, "car": car, "pickup": pickup, "return_": return_}
    method, url, body = case(ctx)
    refunds = list(RefundRequest.objects.values_list("pk", "status"))
    payments = Payment.objects.count()
    response = getattr(client_for(people, role), method)(
        url, {**body, "password": "wrong"}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {"password": ["That password is not correct."]}
    assert Payment.objects.count() == payments
    assert list(RefundRequest.objects.values_list("pk", "status")) == refunds
    assert AuditLog.objects.filter(action="Payment Re-authentication Failed").exists()


# ─── SE-5: scoping ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "case"),
    [
        ("capture", capture),
        ("refund-create", refund_create),
        ("pay-out", pay_out),
        ("record-cash", record_cash),
    ],
)
def test_staff_of_another_branch_get_a_404(name, case, people, customer, car, pickup, return_):
    ctx = {"people": people, "customer": customer, "car": car, "pickup": pickup, "return_": return_}
    method, url, body = case(ctx)
    response = getattr(authenticated_client(BranchStaffFactory().user), method)(
        url, body, format="json"
    )
    assert response.status_code == 404


def test_each_role_sees_only_the_refunds_in_its_scope(
    people, customer, car, pickup, return_, branch
):
    mine = services.refund_payment(
        original(confirmed(customer, car, pickup, return_)),
        Decimal("10.00"),
        "Mine",
        people["staff"],
    )
    stranger = eligible_customer()
    from apps.fleet.tests.factories import CarFactory
    from apps.pricing.tests.factories import TariffFactory

    elsewhere = CarFactory(available_from=car.available_from)
    TariffFactory(vehicle_category=elsewhere.category)
    theirs = services.refund_payment(
        original(confirmed(stranger, elsewhere, pickup, return_)), Decimal("10.00"), "Theirs", None
    )
    seen = {
        role: {
            row["id"]
            for row in authenticated_client(people[role])
            .get(reverse("payments:refund-list"))
            .json()["results"]
        }
        for role in ("customer", "staff", "manager", "admin")
    }
    assert seen == {
        "customer": {mine.pk},
        "staff": {mine.pk},
        "manager": {mine.pk},
        "admin": {mine.pk, theirs.pk},
    }


def test_the_administrator_queue_filters_by_status(people, customer, car, pickup):
    pending = _pending({"people": people, "customer": customer, "car": car, "pickup": pickup})
    response = authenticated_client(people["admin"]).get(
        reverse("payments:refund-list"), {"status": "Pending Approval"}
    )
    rows = response.json()["results"]
    assert [row["id"] for row in rows] == [pending.pk]
    assert rows[0]["amount"] == "6372.00"
    assert rows[0]["customer_name"] == customer.user.name
    assert rows[0]["purpose"] == "Rental" and rows[0]["method"] == "Card"


# ─── Pay.Idempotent over HTTP ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "case", "role"), MONEY_CASES[:3], ids=[c[0] for c in MONEY_CASES[:3]]
)
def test_a_repeated_submission_never_charges_or_refunds_twice(
    name, case, role, people, customer, car, pickup, return_
):
    ctx = {"people": people, "customer": customer, "car": car, "pickup": pickup, "return_": return_}
    method, url, body = case(ctx)
    client = client_for(people, role)
    first = getattr(client, method)(url, body, format="json")
    payments = Payment.objects.count()
    again = getattr(client, method)(url, body, format="json")
    assert first.status_code == again.status_code < 300
    assert again.json() == first.json()
    assert Payment.objects.count() == payments


def test_paying_the_due_returns_the_new_due_and_the_transaction(people, customer):
    services.record_due(customer, Decimal("100.00"), "Fuel")
    client = authenticated_client(customer.user)
    assert client.get(reverse("payments:due")).json() == {"outstanding_due": "100.00"}
    response = client.post(
        reverse("payments:due"),
        {
            "method": "online",
            "channel": "Wallet",
            "payment_token": "tok_wallet",
            "idempotency_key": "due-api-0009",
            "password": PASSWORD,
        },
        format="json",
    )
    assert response.status_code == 200
    assert response.json()["outstanding_due"] == "0.00"
    assert response.json()["transaction_id"].startswith("TXN-")


def test_a_declined_due_payment_is_a_402(people, customer):
    services.record_due(customer, Decimal("100.00"), "Fuel")
    response = authenticated_client(customer.user).post(
        reverse("payments:due"),
        {"payment_token": "tok_decline", "idempotency_key": "due-api-0010", "password": PASSWORD},
        format="json",
    )
    assert (response.status_code, response.json()["code"]) == (402, "payment_declined")


def test_the_booking_detail_shows_its_refunds(people, customer, car, pickup, return_):
    booking = confirmed(customer, car, pickup, return_)
    services.refund_payment(original(booking), Decimal("10.00"), "Goodwill", people["staff"])
    detail = authenticated_client(customer.user).get(
        reverse("bookings:booking-detail", args=[booking.pk])
    )
    [refund] = detail.json()["refunds"]
    assert (refund["status"], refund["amount"], refund["reason"]) == ("Issued", "10.00", "Goodwill")
    assert refund["refund_transaction_id"].startswith("TXN-")
