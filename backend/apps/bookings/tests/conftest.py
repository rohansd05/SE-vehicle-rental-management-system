"""Shared fixtures for the Book Vehicle tests (Exp 4 sequence 1)."""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.accounts.tests.factories import (
    DEFAULT_PASSWORD,
    CustomerFactory,
    LicenceCategoryFactory,
    LicenceFactory,
)
from apps.core.choices import VehicleType
from apps.fleet.tests.factories import BranchFactory, CarFactory, TwoWheelerFactory
from apps.pricing.tests.factories import TariffFactory

PASSWORD = DEFAULT_PASSWORD


def next_pickup():
    """10:00 IST three days ahead, as an aware UTC instant."""
    local = timezone.localtime() + timedelta(days=3)
    return local.replace(hour=10, minute=0, second=0, microsecond=0)


def eligible_customer(**customer_kwargs):
    """A customer with a verified licence for cars and two-wheelers (BR-2, BR-3)."""
    customer = CustomerFactory(**customer_kwargs)
    licence = LicenceFactory(customer=customer)
    LicenceCategoryFactory(licence=licence, category=VehicleType.CAR)
    LicenceCategoryFactory(licence=licence, category=VehicleType.TWO_WHEELER)
    return customer


@pytest.fixture
def pickup():
    return next_pickup()


@pytest.fixture
def return_(pickup):
    return pickup + timedelta(days=2)


@pytest.fixture
def branch():
    return BranchFactory(branch_name="Andheri")


@pytest.fixture
def car(branch):
    vehicle = CarFactory(home_branch=branch, available_from=date(2026, 1, 1))
    TariffFactory(vehicle_category=vehicle.category)  # 150/h, 1800/day
    return vehicle


@pytest.fixture
def scooter(branch):
    vehicle = TwoWheelerFactory(home_branch=branch, available_from=date(2026, 1, 1))
    TariffFactory(vehicle_category=vehicle.category, hourly_rate="60.00", daily_rate="500.00")
    return vehicle


@pytest.fixture
def customer():
    return eligible_customer()
