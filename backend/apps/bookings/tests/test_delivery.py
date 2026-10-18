"""Module R4: doorstep delivery (Book.Addons, Book.Deliver.Location, BR-7; Exp 2 UC 3
extend "Add Doorstep Delivery"; Exp 5 "Address serviceable?"), SA-2 at booking, and
the cancel_booking() actor (N3 follow-up).

Prices (car tariff 150/h, 1800/day, 18% tax, D14): delivery at 300.00 per day.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts.tests.factories import AdministratorFactory, BranchStaffFactory
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings import lifecycle, services
from apps.bookings.models import Booking
from apps.core.models import AuditLog
from apps.fleet.tests.factories import BranchFactory, BranchServiceableAreaFactory, CarFactory
from apps.pricing.tests.factories import AddOnFactory, TariffFactory

pytestmark = pytest.mark.django_db

CARD = {"method": "card", "payment_token": "tok_visa", "channel": "", "upi_id": ""}


@pytest.fixture
def delivery():
    return AddOnFactory(name="Doorstep delivery", daily_rate="300.00", vehicle_type="")


@pytest.fixture
def area(branch):
    return BranchServiceableAreaFactory(branch=branch, pincode="400053", locality="Andheri West")


def create(customer, car, pickup, return_, add_ons=(), **kwargs):
    return lifecycle.create_booking(
        customer,
        vehicle=car,
        pickup=pickup,
        return_=return_,
        add_ons=list(add_ons),
        terms_accepted=True,
        **kwargs,
    )


def delivered(customer, car, pickup, return_, delivery, pincode="400053"):
    return create(
        customer,
        car,
        pickup,
        return_,
        add_ons=[(delivery.pk, 1)],
        delivery_address="  12 Demo Lane, Andheri (W)  ",
        delivery_pincode=pincode,
    )


# ─── Book.Deliver.Location ────────────────────────────────────────────────


def test_an_address_in_the_serviceable_area_is_booked_and_charged(
    customer, car, pickup, return_, delivery, area
):
    booking = delivered(customer, car, pickup, return_, delivery)
    assert (booking.delivery_address, booking.delivery_pincode) == (
        "12 Demo Lane, Andheri (W)",
        "400053",
    )
    line = booking.add_ons.get()
    assert (line.add_on_id, line.daily_rate) == (delivery.pk, Decimal("300.00"))  # BR-7
    assert booking.status == Booking.Status.PENDING_PAYMENT


def test_an_address_outside_the_serviceable_area_is_refused_on_its_field(
    customer, car, pickup, return_, delivery, area
):
    other = BranchFactory(branch_name="Thane")
    BranchServiceableAreaFactory(branch=other, pincode="400601")  # another branch's area
    with pytest.raises(lifecycle.BookingError) as refused:
        delivered(customer, car, pickup, return_, delivery, pincode="400601")
    assert refused.value.field == "delivery_pincode"
    assert "We don't deliver to 400601" in str(refused.value)
    assert not Booking.objects.exists()


def test_delivery_needs_an_address(customer, car, pickup, return_, delivery, area):
    with pytest.raises(lifecycle.BookingError) as refused:
        create(customer, car, pickup, return_, [(delivery.pk, 1)], delivery_pincode="400053")
    assert refused.value.field == "delivery_address"


@pytest.mark.parametrize("pincode", ["", "40005", "4000531", "40O053"])
def test_delivery_needs_a_six_digit_pincode(customer, car, pickup, return_, delivery, pincode):
    with pytest.raises(lifecycle.BookingError) as refused:
        delivered(customer, car, pickup, return_, delivery, pincode=pincode)
    assert refused.value.field == "delivery_pincode"


def test_without_delivery_an_address_is_not_kept(customer, car, pickup, return_):
    booking = create(
        customer, car, pickup, return_, delivery_address="Somewhere", delivery_pincode="400053"
    )
    assert (booking.delivery_address, booking.delivery_pincode) == ("", "")


def test_the_api_puts_the_refusal_next_to_the_field(customer, car, pickup, return_, delivery):
    client = authenticated_client(customer.user)
    response = client.post(
        reverse("bookings:booking-list"),
        {
            "vehicle": car.pk,
            "pickup_datetime": pickup.isoformat(),
            "return_datetime": return_.isoformat(),
            "add_ons": [{"add_on": delivery.pk, "quantity": 1}],
            "delivery_address": "12 Demo Lane",
            "delivery_pincode": "400099",
            "terms_accepted": True,
        },
        format="json",
    )
    assert response.status_code == 400
    assert list(response.data) == ["delivery_pincode"]


def test_the_api_stores_and_shows_the_address(customer, car, pickup, return_, delivery, area):
    client = authenticated_client(customer.user)
    response = client.post(
        reverse("bookings:booking-list"),
        {
            "vehicle": car.pk,
            "pickup_datetime": pickup.isoformat(),
            "return_datetime": return_.isoformat(),
            "add_ons": [{"add_on": delivery.pk, "quantity": 1}],
            "delivery_address": "12 Demo Lane",
            "delivery_pincode": "400053",
            "terms_accepted": True,
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    assert (response.data["delivery_address"], response.data["delivery_pincode"]) == (
        "12 Demo Lane",
        "400053",
    )
    # Branch staff see it on the booking (display only), e.g. from the handover screen.
    staff = authenticated_client(BranchStaffFactory(branch=car.home_branch).user)
    detail = staff.get(reverse("bookings:booking-detail", args=[response.data["id"]]))
    assert detail.data["delivery_address"] == "12 Demo Lane"


def test_holding_again_checks_the_area_again(customer, car, pickup, return_, delivery, area):
    booking = delivered(customer, car, pickup, return_, delivery)
    lifecycle._back_to_draft(booking, actor=None, reason="test", request=None)
    area.delete()  # an Administrator removed the area meanwhile (N3)
    with pytest.raises(lifecycle.BookingError) as refused:
        lifecycle.hold_again(customer, booking.pk)
    assert refused.value.field == "delivery_pincode"


def test_cash_is_not_offered_with_delivery(customer, car, pickup, return_, delivery, area):
    """BR-9: cash only for a booking collected at a branch (R1, unchanged)."""
    booking = delivered(customer, car, pickup, return_, delivery)
    with pytest.raises(lifecycle.BookingError) as refused:
        lifecycle.pay_booking(customer, booking.pk, idempotency_key="cash-0001", method="cash")
    assert refused.value.code == "cash_not_available"


def test_the_confirmation_e_mail_names_the_delivery_address(
    customer, car, pickup, return_, delivery, area, outbox
):
    booking = delivered(customer, car, pickup, return_, delivery)
    lifecycle.pay_booking(customer, booking.pk, payment_token="tok_visa", idempotency_key="d-0001")
    email = next(m for m in outbox if m.channel == "email" and m.recipient == customer.user.email)
    assert "Doorstep delivery: we bring the vehicle to 12 Demo Lane, Andheri (W), 400053" in (
        email.body
    )


def test_a_branch_collection_e_mail_names_the_branch(customer, car, pickup, return_, outbox):
    booking = create(customer, car, pickup, return_)
    lifecycle.pay_booking(customer, booking.pk, payment_token="tok_visa", idempotency_key="d-0002")
    email = next(m for m in outbox if m.channel == "email" and m.recipient == customer.user.email)
    assert f"Collection: our {car.home_branch.branch_name} branch" in email.body


# ─── R2 changes keep the delivery honest (R4-P2) ──────────────────────────


def _confirmed_delivery(customer, car, pickup, return_, delivery):
    booking = delivered(customer, car, pickup, return_, delivery)
    return lifecycle.pay_booking(
        customer, booking.pk, payment_token="tok_visa", idempotency_key="pay-dl-0001"
    )


def _change(booking, **overrides):
    values = {
        "pickup": booking.pickup_datetime,
        "return_": booking.return_datetime,
        "branch": booking.pickup_branch,
        "add_ons": list(booking.add_ons.values_list("add_on_id", "quantity")),
        "vehicle": None,
    }
    return services.Modification(**{**values, **overrides})


def test_delivery_cannot_be_removed_by_a_change(customer, car, pickup, return_, delivery, area):
    booking = _confirmed_delivery(customer, car, pickup, return_, delivery)
    with pytest.raises(lifecycle.BookingError) as refused:
        services.modification_quote(customer, booking.pk, _change(booking, add_ons=[]))
    assert refused.value.code == "delivery_unchangeable"


def test_a_new_branch_must_serve_the_delivery_address(
    customer, car, pickup, return_, delivery, area
):
    booking = _confirmed_delivery(customer, car, pickup, return_, delivery)
    bandra = BranchFactory(branch_name="Bandra")
    CarFactory(home_branch=bandra, category=car.category, available_from=date(2026, 1, 1))
    with pytest.raises(lifecycle.BookingError) as refused:
        services.modification_quote(customer, booking.pk, _change(booking, branch=bandra))
    assert refused.value.field == "delivery_pincode"


def test_a_kept_delivery_on_the_same_branch_is_quoted(
    customer, car, pickup, return_, delivery, area
):
    booking = _confirmed_delivery(customer, car, pickup, return_, delivery)
    quote = services.modification_quote(
        customer, booking.pk, _change(booking, return_=return_ + (return_ - pickup))
    )
    assert quote.vehicle_free


# ─── SA-2 at booking ──────────────────────────────────────────────────────


def test_a_vehicle_overdue_for_its_service_cannot_be_booked(customer, branch, pickup, return_):
    car = CarFactory(
        home_branch=branch,
        available_from=date(2026, 1, 1),
        odometer=16000,
        last_service_odometer=11000,  # BR-15: 5,000 km reached
        last_service_date=date(2026, 9, 1),
    )
    TariffFactory(vehicle_category=car.category)
    with pytest.raises(lifecycle.VehicleUnavailableError) as refused:
        create(customer, car, pickup, return_)
    assert refused.value.code == "service_overdue"
    assert "SA-2" in str(refused.value)


# ─── cancel_booking(actor=...) (N3 follow-up) ─────────────────────────────


def test_a_cancellation_records_the_customer_by_default(customer, car, pickup, return_):
    booking = create(customer, car, pickup, return_)
    booking = lifecycle.pay_booking(
        customer, booking.pk, payment_token="tok_visa", idempotency_key="pay-cx-0001"
    )
    quote = services.cancellation_quote(customer, booking.pk)
    services.cancel_booking(customer, booking.pk, expected_refund=quote.total_refund)
    entry = AuditLog.objects.get(action="Booking Status Changed", after__status="Cancelled")
    assert entry.actor == customer.user
    assert entry.after["reason"].startswith("The customer cancelled")


def test_a_cancellation_records_the_given_actor_and_reason(customer, car, pickup, return_):
    admin = AdministratorFactory().user
    booking = create(customer, car, pickup, return_)
    booking = lifecycle.pay_booking(
        customer, booking.pk, payment_token="tok_visa", idempotency_key="pay-cx-0002"
    )
    quote = services.cancellation_quote(customer, booking.pk)
    services.cancel_booking(
        customer, booking.pk, expected_refund=quote.total_refund, actor=admin, reason="Fraud."
    )
    entry = AuditLog.objects.get(action="Booking Status Changed", after__status="Cancelled")
    assert (entry.actor, entry.after["reason"]) == (admin, "Fraud.")
    released = AuditLog.objects.get(action="Vehicle Released From Booking")
    assert released.actor == admin
