"""Demo booking data from seed_demo: bookable Andheri vehicles and a pending-licence customer."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command

from apps.accounts.models import Customer, Licence
from apps.bookings import lifecycle
from apps.bookings.eligibility import NotEligibleError
from apps.bookings.seed import DEMO_REGISTRATIONS, PENDING_EMAIL
from apps.bookings.tests.conftest import next_pickup
from apps.fleet.models import Branch, Vehicle
from apps.fleet.services.availability import available_vehicles
from apps.maintenance.models import MaintenanceJob
from apps.maintenance.seed import DEMO_PROBLEMS

pytestmark = pytest.mark.django_db


def _seed(*args):
    call_command("seed_demo", *args, stdout=StringIO())


def test_four_bookable_vehicles_are_added_at_andheri():
    _seed()
    vehicles = Vehicle.objects.filter(registration_no__in=DEMO_REGISTRATIONS).select_related(
        "category", "home_branch"
    )
    assert vehicles.count() == 4
    assert {v.home_branch.branch_name for v in vehicles} == {"Andheri"}
    assert {v.status for v in vehicles} == {Vehicle.Status.AVAILABLE}
    assert {v.category.name for v in vehicles} == {"Hatchback", "SUV", "Scooter", "Motorcycle"}
    assert all(v.documents.count() == 1 for v in vehicles)


def test_the_demo_vehicles_show_in_an_andheri_search():
    _seed()
    pickup = next_pickup()
    found = available_vehicles(
        branch=Branch.objects.get(branch_name="Andheri"),
        pickup=pickup,
        return_=pickup + timedelta(days=2),
    ).values_list("registration_no", flat=True)
    # The four demo vehicles, the one original Andheri vehicle maintenance leaves free,
    # the two payments demo cars (payments/seed.py), booked on other days, and the
    # booking-changes no-show car (seed_changes.py; its twin is booked then).
    assert set(DEMO_REGISTRATIONS) <= set(found)
    assert len(found) == 8


def test_the_demo_customer_can_book_and_pay_for_one():
    _seed()
    customer = Customer.objects.get(user__email="customer@vrms.test")
    vehicle = Vehicle.objects.get(registration_no=DEMO_REGISTRATIONS[0])
    pickup = next_pickup()
    booking = lifecycle.create_booking(
        customer,
        vehicle=vehicle,
        pickup=pickup,
        return_=pickup + timedelta(days=2),
        discount_code="WELCOME10",
        terms_accepted=True,
    )
    booking = lifecycle.pay_booking(
        customer, booking.pk, payment_token="tok_visa", idempotency_key="seed-demo-pay-1"
    )
    assert booking.status == booking.Status.CONFIRMED
    assert booking.invoice.invoice_number.startswith("INV-")


def test_the_pending_customer_is_refused_for_an_unverified_licence():
    _seed()
    customer = Customer.objects.get(user__email=PENDING_EMAIL)
    assert customer.licence.status == Licence.Status.PENDING_VERIFICATION
    assert customer.user.check_password("Demo@1234")
    pickup = next_pickup()
    with pytest.raises(NotEligibleError) as error:
        lifecycle.create_booking(
            customer,
            vehicle=Vehicle.objects.get(registration_no=DEMO_REGISTRATIONS[1]),
            pickup=pickup,
            return_=pickup + timedelta(days=1),
            terms_accepted=True,
        )
    assert error.value.code == "licence_not_verified"


def test_the_maintenance_demo_data_is_unchanged():
    _seed()
    assert MaintenanceJob.objects.filter(reported_problem__in=DEMO_PROBLEMS).count() == 3
    assert not MaintenanceJob.objects.filter(
        vehicle__registration_no__in=DEMO_REGISTRATIONS
    ).exists()


def test_seeding_twice_adds_nothing_and_reset_reloads():
    _seed()
    _seed()
    assert Vehicle.objects.filter(registration_no__in=DEMO_REGISTRATIONS).count() == 4
    assert Customer.objects.filter(user__email=PENDING_EMAIL).count() == 1
    _seed("--reset")
    assert Vehicle.objects.filter(registration_no__in=DEMO_REGISTRATIONS).count() == 4
    assert Customer.objects.filter(user__email=PENDING_EMAIL).count() == 1
