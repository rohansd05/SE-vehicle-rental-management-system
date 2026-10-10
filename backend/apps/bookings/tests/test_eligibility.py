"""Book.Eligible.Licence, BR-2, BR-3, BR-4: Exp 3 Licence.is_valid() and the customer checks."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import Licence
from apps.accounts.tests.factories import CustomerFactory, LicenceCategoryFactory, LicenceFactory
from apps.bookings.eligibility import NotEligibleError, age_on, check_eligibility
from apps.bookings.tests.conftest import eligible_customer, next_pickup
from apps.core.choices import VehicleType

pytestmark = pytest.mark.django_db

CAR = VehicleType.CAR
TWO_WHEELER = VehicleType.TWO_WHEELER


def refused(customer, vehicle_type=CAR, pickup=None, return_=None) -> str:
    pickup = pickup or next_pickup()
    with pytest.raises(NotEligibleError) as error:
        check_eligibility(customer, vehicle_type, pickup, return_ or pickup + timedelta(days=2))
    return error.value.code


def test_an_eligible_customer_passes():
    pickup = next_pickup()
    check_eligibility(eligible_customer(), CAR, pickup, pickup + timedelta(days=2))
    check_eligibility(eligible_customer(), TWO_WHEELER, pickup, pickup + timedelta(days=2))


# ─── BR-4 ─────────────────────────────────────────────────────────────────


def test_a_blacklisted_customer_cannot_book():
    assert refused(eligible_customer(is_blacklisted=True)) == "customer_blacklisted"


def test_a_customer_with_a_due_cannot_book():
    customer = eligible_customer(outstanding_due=Decimal("0.01"))
    with pytest.raises(NotEligibleError, match=r"INR 0.01"):
        check_eligibility(customer, CAR, next_pickup(), next_pickup() + timedelta(days=1))


# ─── Licence (Book.Eligible.Licence) ──────────────────────────────────────


def test_a_customer_without_a_licence_cannot_book():
    assert refused(CustomerFactory()) == "licence_not_verified"


@pytest.mark.parametrize(
    "status",
    [Licence.Status.NOT_SUBMITTED, Licence.Status.PENDING_VERIFICATION, Licence.Status.REJECTED],
)
def test_an_unverified_licence_is_refused(status):
    customer = eligible_customer()
    Licence.objects.filter(customer=customer).update(status=status)
    assert refused(customer) == "licence_not_verified"


def test_an_expired_licence_status_is_refused():
    customer = eligible_customer()
    Licence.objects.filter(customer=customer).update(status=Licence.Status.EXPIRED)
    assert refused(customer) == "licence_expired"


def test_a_verified_licence_past_its_expiry_date_is_refused():
    customer = eligible_customer()
    Licence.objects.filter(customer=customer).update(
        expiry_date=timezone.localdate() - timedelta(days=1)
    )
    assert refused(customer) == "licence_expired"


def test_a_licence_expiring_during_the_rental_is_refused():
    """BR-2: valid for the entire rental."""
    pickup = next_pickup()
    customer = eligible_customer()
    Licence.objects.filter(customer=customer).update(
        expiry_date=timezone.localdate(pickup) + timedelta(days=1)
    )
    assert refused(customer, pickup=pickup, return_=pickup + timedelta(days=2)) == (
        "licence_expires_before_return"
    )


def test_a_licence_expiring_on_the_return_date_is_accepted():
    pickup = next_pickup()
    return_ = pickup + timedelta(days=2)
    customer = eligible_customer()
    Licence.objects.filter(customer=customer).update(expiry_date=timezone.localdate(return_))
    check_eligibility(customer, CAR, pickup, return_)


def test_a_licence_without_an_expiry_date_is_refused():
    customer = eligible_customer()
    Licence.objects.filter(customer=customer).update(expiry_date=None)
    assert refused(customer) == "licence_expires_before_return"


def test_only_endorsed_categories_may_be_rented():
    """BR-3 with D18: the licence category is the vehicle type."""
    customer = CustomerFactory()
    LicenceCategoryFactory(licence=LicenceFactory(customer=customer), category=TWO_WHEELER)
    assert refused(customer, CAR) == "licence_category"
    check_eligibility(customer, TWO_WHEELER, next_pickup(), next_pickup() + timedelta(days=1))


# ─── Minimum age (BR-2, BK4: on the pickup date) ──────────────────────────


def _born_years_before(day: date, years: int, *, days_later: int = 0) -> date:
    return day.replace(year=day.year - years) + timedelta(days=days_later)


@pytest.mark.parametrize(
    ("vehicle_type", "years", "days_later", "eligible"),
    [
        (CAR, 21, 0, True),  # 21st birthday on the pickup date
        (CAR, 21, 1, False),  # one day short
        (TWO_WHEELER, 18, 0, True),
        (TWO_WHEELER, 18, 1, False),
        (TWO_WHEELER, 20, 0, True),  # old enough for a two-wheeler, not a car
    ],
)
def test_the_minimum_age_on_the_pickup_date(vehicle_type, years, days_later, eligible):
    pickup = next_pickup()
    birth = _born_years_before(timezone.localdate(pickup), years, days_later=days_later)
    customer = eligible_customer(date_of_birth=birth)
    if eligible:
        check_eligibility(customer, vehicle_type, pickup, pickup + timedelta(days=1))
    else:
        assert refused(customer, vehicle_type, pickup=pickup) == "under_age"


def test_twenty_is_too_young_for_a_car():
    pickup = next_pickup()
    customer = eligible_customer(date_of_birth=_born_years_before(timezone.localdate(pickup), 20))
    assert refused(customer, CAR, pickup=pickup) == "under_age"


def test_age_on():
    assert age_on(date(2000, 2, 29), date(2021, 2, 28)) == 20
    assert age_on(date(2000, 2, 29), date(2021, 3, 1)) == 21
