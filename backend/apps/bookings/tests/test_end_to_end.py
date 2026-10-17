"""Exp 4 sequence diagram 1 (Book Vehicle), end to end over HTTP, on the seed_demo data.

Every step goes through the public API exactly as the frontend calls it,
signed in through the real login endpoint (D21). The comments name the
sequence-diagram message each request carries.

Main flow:        test_book_vehicle_main_flow
Alternative flows: licence invalid  -> test_alt_licence_not_verified_then_verified
                                       test_alt_licence_expires_before_return
                   vehicle not free -> test_alt_vehicle_not_available
                   payment declined -> test_alt_payment_declined_hold_retained (also main flow)
                   hold expired     -> test_alt_hold_expires_and_is_held_again
"""

from datetime import timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.accounts.models import Licence
from apps.bookings.models import Booking
from apps.bookings.seed import DEMO_REGISTRATIONS, PENDING_EMAIL
from apps.bookings.tests.conftest import eligible_customer, next_pickup
from apps.core.models import AuditLog
from apps.fleet.models import Branch, Vehicle
from apps.payments.models import Invoice, LedgerEntry, Payment
from apps.pricing.models import AddOn, DiscountCode

pytestmark = pytest.mark.django_db

PASSWORD = "Demo@1234"  # seed_demo


@pytest.fixture(autouse=True)
def demo_data():
    call_command("seed_demo", stdout=StringIO())


def sign_in(email: str, password: str = PASSWORD) -> APIClient:
    client = APIClient()
    response = client.post(
        reverse("accounts:login"), {"email": email, "password": password}, format="json"
    )
    assert response.status_code == 200, response.content
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.json()['access']}")
    return client


def period(days: int = 2) -> dict:
    pickup = next_pickup()
    return {
        "pickup_datetime": pickup.isoformat(),
        "return_datetime": (pickup + timedelta(days=days)).isoformat(),
    }


def search(client, when: dict) -> list[int]:
    andheri = Branch.objects.get(branch_name="Andheri")
    response = client.get(reverse("fleet:search"), {"branch": andheri.pk, **when})
    assert response.status_code == 200
    return [row["id"] for row in response.json()["results"]]


def create(client, vehicle: Vehicle, when: dict, **extra):
    body = {"vehicle": vehicle.pk, **when, "terms_accepted": True, **extra}
    return client.post(reverse("bookings:booking-list"), body, format="json")


def pay(
    client,
    booking_id: int,
    token: str = "tok_visa",
    key: str = "e2e-pay-key-01",
    password: str = PASSWORD,
):
    body = {"payment_token": token, "idempotency_key": key, "password": password}
    return client.post(reverse("bookings:booking-pay", args=[booking_id]), body, format="json")


def demo_car() -> Vehicle:
    return Vehicle.objects.get(registration_no=DEMO_REGISTRATIONS[0])  # Hatchback, Andheri


# ─── Main flow ────────────────────────────────────────────────────────────


def test_book_vehicle_main_flow():
    customer = sign_in("customer@vrms.test")
    when = period()
    car = demo_car()
    seat = AddOn.objects.get(name="Child seat")

    # Search.Available, Search.Price: the vehicle is offered with an estimate.
    found = customer.get(reverse("fleet:search"), {"branch": car.home_branch_id, **when}).json()[
        "results"
    ]
    row = next(r for r in found if r["id"] == car.pk)
    assert row["estimate"]["total_payable"] == "4248.00"  # 2 x 1800 + 18%

    # Search.Detail
    detail = customer.get(reverse("fleet:vehicle-detail", args=[car.pk])).json()
    assert detail["tariff"]["daily_rate"] == "1800.00"
    assert detail["security_deposit"] == "5000.00"

    # Tariff.calculate_price() before committing (Book.Quote.Display).
    quoted = customer.post(
        reverse("pricing:quote"),
        {
            "vehicle": car.pk,
            **when,
            "add_ons": [{"add_on": seat.pk, "quantity": 1}],
            "discount_code": "WELCOME10",
        },
        format="json",
    ).json()
    # (3600 + child seat 2 x 150) - 10% = 3510, + 18% tax = 4141.80
    assert (quoted["discount_amount"], quoted["tax_amount"], quoted["total_payable"]) == (
        "390.00",
        "631.80",
        "4141.80",
    )

    # 1 Customer -> Booking.create_booking()
    # 2 Booking -> Licence.is_valid()            (verified, covers a car, valid to return, age 21+)
    # 3 Booking -> Vehicle.check_availability()  (free for the period + BR-1 buffer)
    # 4 Booking -> Tariff.calculate_price()      (snapshot on the booking)
    created = create(
        customer, car, when, add_ons=[{"add_on": seat.pk, "quantity": 1}], discount_code="WELCOME10"
    )
    assert created.status_code == 201, created.content
    booking = created.json()
    assert booking["status"] == "Pending Payment"  # Book.Hold: 15 minutes
    assert booking["price"]["total_payable"] == quoted["total_payable"]
    assert car.pk not in search(customer, when)  # the hold keeps it from everyone else

    # 5 alt [declined]: hold retained
    declined = pay(customer, booking["id"], token="tok_decline", key="e2e-declined-01")
    assert declined.status_code == 402 and declined.json()["code"] == "payment_declined"
    assert Booking.objects.get(pk=booking["id"]).status == Booking.Status.PENDING_PAYMENT

    # 5 Booking -> Payment.authorize()   (SE-9 password; rental + deposit, one authorisation)
    # 6 Booking -> Vehicle.update_status() (Book.Done.Block; status unchanged by decision)
    # 7 Booking -> Invoice.generate_invoice()
    # 8 status Confirmed, pickup code returned
    last_audit_id = AuditLog.objects.order_by("-id").values_list("id", flat=True).first()
    paid = pay(customer, booking["id"])
    assert paid.status_code == 200, paid.content
    confirmed = paid.json()
    assert confirmed["status"] == "Confirmed"
    assert confirmed["booking_reference"].startswith(f"VRMS-{timezone.localdate():%Y%m%d}-")
    assert len(confirmed["pickup_code"]) == 6
    assert confirmed["transaction_id"].startswith("TXN-")

    stored = Booking.objects.get(pk=booking["id"])
    car.refresh_from_db()
    assert car.status == Vehicle.Status.AVAILABLE
    invoice = Invoice.objects.get(booking=stored)
    assert invoice.total_amount == Decimal(quoted["total_payable"])
    assert invoice.tax_amount == Decimal(quoted["tax_amount"])
    assert sorted(
        Payment.objects.filter(booking=stored, status="Succeeded").values_list("purpose", "amount")
    ) == [("Rental", Decimal("4141.80")), ("Security Deposit", Decimal("5000.00"))]
    assert list(
        LedgerEntry.objects.filter(booking=stored).values_list("entry_type", flat=True)
    ) == [
        "Charge",
        "Deposit Hold",
    ]
    assert DiscountCode.objects.get(code="WELCOME10").times_used == 1
    assert car.pk not in search(customer, when)  # Book.Done.Block

    # SE-10: the successful payment wrote one audit entry per step, in sequence-diagram order.
    steps = list(
        AuditLog.objects.filter(id__gt=last_audit_id)
        .order_by("id")
        .values_list("entity_type", "action")
    )
    assert steps == [
        ("payments.CardPayment", "Payment Authorized"),  # 5 Payment.authorize(): rental
        ("payments.CardPayment", "Payment Authorized"),  # ... and the deposit
        ("bookings.Booking", "Booking Status Changed"),  # Pending Payment -> Confirmed
        ("fleet.Vehicle", "Vehicle Blocked For Booking"),  # 6 update_status() = Book.Done.Block
        ("payments.Invoice", "Invoice Issued"),  # 7 Invoice.generate_invoice()
        ("bookings.Booking", "Ledger Entries Recorded"),  # Pay.Ledger
    ]
    assert AuditLog.objects.verify_chain()

    # History.View, History.Download
    history = customer.get(reverse("bookings:booking-list")).json()
    assert [row["booking_reference"] for row in history["results"]] == [
        confirmed["booking_reference"]
    ]
    pdf = customer.get(reverse("bookings:booking-invoice", args=[booking["id"]]))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    # Pay.Idempotent: a refreshed page resubmitting the same key is not charged again.
    again = pay(customer, booking["id"])
    assert again.status_code == 200
    assert Payment.objects.filter(booking=stored, status="Succeeded").count() == 2

    # History.Privacy: the demo branch staff (Andheri) see it, without the pickup code.
    staff_view = sign_in("staff@vrms.test").get(
        reverse("bookings:booking-detail", args=[booking["id"]])
    )
    assert staff_view.status_code == 200 and staff_view.json()["pickup_code"] == ""


# ─── alt: licence invalid -> booking refused ──────────────────────────────


def test_alt_licence_not_verified_then_verified():
    pending = sign_in(PENDING_EMAIL)
    when = period()
    refused = create(pending, demo_car(), when)
    assert refused.status_code == 400
    assert refused.json()["code"] == "licence_not_verified"
    assert not Booking.objects.filter(customer__user__email=PENDING_EMAIL).exists()

    # Licence.verify(): the demo branch staff approve it (SE-10), then the booking goes through.
    licence = Licence.objects.get(customer__user__email=PENDING_EMAIL)
    approved = sign_in("staff@vrms.test").post(
        reverse("accounts:licence-approve", args=[licence.pk])
    )
    assert approved.status_code == 200
    assert create(pending, demo_car(), when).status_code == 201


def test_alt_licence_expires_before_return():
    customer = sign_in("customer@vrms.test")
    when = period(days=3)
    Licence.objects.filter(customer__user__email="customer@vrms.test").update(
        expiry_date=next_pickup().date() + timedelta(days=1)
    )
    refused = create(customer, demo_car(), when)
    assert refused.status_code == 400
    assert refused.json()["code"] == "licence_expires_before_return"


# ─── alt: vehicle not free ────────────────────────────────────────────────


def test_alt_vehicle_not_available():
    when = period()
    first = sign_in("customer@vrms.test")
    booking_id = create(first, demo_car(), when).json()["id"]
    assert pay(first, booking_id).status_code == 200

    rival = eligible_customer()
    rival.user.set_password(PASSWORD)
    rival.user.save()
    second = sign_in(rival.user.email)
    overlapping = {
        "pickup_datetime": (next_pickup() + timedelta(days=1)).isoformat(),
        "return_datetime": (next_pickup() + timedelta(days=3)).isoformat(),
    }
    assert demo_car().pk not in search(second, overlapping)  # not offered...
    refused = create(second, demo_car(), overlapping)  # ...and refused if asked for anyway
    assert refused.status_code == 409
    assert refused.json()["code"] == "vehicle_unavailable"
    assert Booking.objects.filter(vehicle=demo_car()).count() == 1


# ─── alt: payment declined -> hold retained ───────────────────────────────


def test_alt_payment_declined_hold_retained():
    customer = sign_in("customer@vrms.test")
    booking_id = create(customer, demo_car(), period()).json()["id"]
    for attempt in range(2):
        declined = pay(customer, booking_id, token="tok_decline", key=f"e2e-decline-{attempt:02d}")
        assert declined.status_code == 402
    booking = Booking.objects.get(pk=booking_id)
    assert booking.status == Booking.Status.PENDING_PAYMENT
    assert not Invoice.objects.filter(booking=booking).exists()
    assert set(booking.payments.values_list("status", flat=True)) == {"Failed"}
    wrong_password = pay(customer, booking_id, password="not-it")
    assert wrong_password.status_code == 400  # SE-9, nothing sent to the gateway
    assert booking.payments.count() == 4


# ─── Book.Hold.Expire ─────────────────────────────────────────────────────


def test_alt_hold_expires_and_is_held_again():
    customer = sign_in("customer@vrms.test")
    booking_id = create(customer, demo_car(), period()).json()["id"]
    with freeze_time(timezone.now() + timedelta(minutes=16)):
        customer = sign_in("customer@vrms.test")  # D19: the access token lived 5 minutes
        expired = pay(customer, booking_id)
        assert expired.status_code == 409 and expired.json()["code"] == "hold_expired"
        assert Booking.objects.get(pk=booking_id).status == Booking.Status.DRAFT
        held = customer.post(reverse("bookings:booking-hold", args=[booking_id]))
        assert held.status_code == 200 and held.json()["status"] == "Pending Payment"
        assert pay(customer, booking_id, key="e2e-after-rehold").status_code == 200
