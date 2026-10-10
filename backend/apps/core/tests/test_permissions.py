"""Object scoping (SE-5, History.Privacy): own records, own branch, or all."""

import pytest
from django.contrib.auth.models import AnonymousUser

from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchManagerFactory,
    BranchStaffFactory,
    CustomerFactory,
    MaintenanceTechnicianFactory,
)
from apps.bookings.models import Booking
from apps.bookings.tests.factories import BookingFactory
from apps.core.permissions import can_access, scope_queryset
from apps.fleet.tests.factories import BranchFactory, CarFactory

pytestmark = pytest.mark.django_db

LOOKUPS = {"customer_lookup": "customer_id", "branch_lookup": "pickup_branch_id"}


@pytest.fixture
def world():
    branch_a, branch_b = BranchFactory(), BranchFactory()
    alice, bob = CustomerFactory(), CustomerFactory()
    in_a = BookingFactory(customer=alice, vehicle=CarFactory(home_branch=branch_a))
    in_b = BookingFactory(customer=bob, vehicle=CarFactory(home_branch=branch_b))
    return {"a": branch_a, "alice": alice, "bob": bob, "in_a": in_a, "in_b": in_b}


def _visible(user):
    return set(scope_queryset(Booking.objects.all(), user, **LOOKUPS))


def test_customer_sees_only_own_bookings(world):
    alice = world["alice"].user
    assert _visible(alice) == {world["in_a"]}
    assert can_access(alice, world["in_a"], **LOOKUPS)
    assert not can_access(alice, world["in_b"], **LOOKUPS)


def test_branch_staff_see_only_their_branch(world):
    staff = BranchStaffFactory(branch=world["a"]).user
    assert _visible(staff) == {world["in_a"]}
    assert not can_access(staff, world["in_b"], **LOOKUPS)


def test_branch_manager_sees_only_their_branch(world):
    manager = BranchManagerFactory(branch=world["a"]).user
    assert _visible(manager) == {world["in_a"]}
    assert can_access(manager, world["in_a"], **LOOKUPS)
    assert not can_access(manager, world["in_b"], **LOOKUPS)


def test_administrator_sees_everything(world):
    admin = AdministratorFactory().user
    assert _visible(admin) == {world["in_a"], world["in_b"]}
    assert can_access(admin, world["in_b"], **LOOKUPS)


def test_technician_and_anonymous_see_no_bookings(world):
    technician = MaintenanceTechnicianFactory().user
    assert _visible(technician) == set()
    assert _visible(AnonymousUser()) == set()
    assert not can_access(AnonymousUser(), world["in_a"], **LOOKUPS)


def test_inactive_user_sees_nothing(world):
    alice = world["alice"].user
    alice.is_active = False
    assert _visible(alice) == set()


def test_without_a_lookup_non_admins_see_nothing(world):
    alice = world["alice"].user
    assert set(scope_queryset(Booking.objects.all(), alice)) == set()
