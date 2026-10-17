"""seed_demo: idempotent demo data with a safe --reset."""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from apps.accounts.models import (
    Administrator,
    BranchManager,
    BranchStaff,
    Customer,
    Licence,
    LicenceCategory,
    MaintenanceTechnician,
    User,
)
from apps.bookings.tests.factories import BookingFactory
from apps.core.models import AuditLog
from apps.fleet.models import (
    Branch,
    BranchServiceableArea,
    Car,
    TwoWheeler,
    Vehicle,
    VehicleCategory,
    VehicleDocument,
)
from apps.pricing.models import AddOn, DiscountCode, FuelPrice, Tariff

pytestmark = pytest.mark.django_db

EXPECTED = {
    Branch: 5,
    BranchServiceableArea: 12,
    VehicleCategory: 5,
    Tariff: 5,
    AddOn: 5,
    DiscountCode: 2,  # one percent, one fixed (D17)
    FuelPrice: 4,
    # 20 + 4 bookable Andheri vehicles (bookings/seed.py) + the handover car (rentals/seed.py)
    Vehicle: 25,
    Car: 15,
    TwoWheeler: 10,
    VehicleDocument: 28,  # one each, and the handover car's four (SA-3)
    User: 7,  # 5 + pending@vrms.test (bookings/seed.py) + handover@vrms.test (rentals/seed.py)
    Customer: 3,
    Licence: 3,
    LicenceCategory: 5,
    BranchStaff: 1,
    MaintenanceTechnician: 1,
    Administrator: 2,  # the administrator and the branch manager
    BranchManager: 1,
}


def _seed(*args):
    call_command("seed_demo", *args, stdout=StringIO())


def _counts():
    return {model: model.objects.count() for model in EXPECTED}


def test_seed_creates_the_expected_demo_data():
    _seed()
    assert _counts() == EXPECTED
    # Fleet.Audit: 5 branches, 7 users, 5 tariffs and 25 vehicles were audited.
    assert AuditLog.objects.filter(action="Create").count() == 42
    assert AuditLog.objects.verify_chain()


def test_seed_twice_changes_nothing():
    _seed()
    audit_entries = AuditLog.objects.count()
    _seed()
    assert _counts() == EXPECTED
    assert AuditLog.objects.count() == audit_entries


def test_reset_reloads_the_same_data():
    _seed()
    _seed("--reset")
    assert _counts() == EXPECTED
    assert AuditLog.objects.filter(action="Delete").count() == 42
    assert AuditLog.objects.verify_chain()


def test_demo_accounts_match_the_readme():
    _seed()
    for email in [
        "customer@vrms.test",
        "staff@vrms.test",
        "tech@vrms.test",
        "admin@vrms.test",
        "manager@vrms.test",
    ]:
        assert User.objects.get(email=email).check_password("Demo@1234")
    admin = User.objects.get(email="admin@vrms.test")
    assert admin.is_staff and admin.is_superuser
    licence = Customer.objects.get(user__email="customer@vrms.test").licence
    assert licence.status == Licence.Status.VERIFIED
    assert set(licence.categories.values_list("category", flat=True)) == {"Car", "Two-Wheeler"}
    assert User.objects.get(email="manager@vrms.test").administrator.branchmanager.branch


def test_seeded_licences_record_verification_only_when_verified():
    _seed()
    verified = Customer.objects.get(user__email="customer@vrms.test").licence
    assert verified.verified_at is not None
    assert verified.verified_by == User.objects.get(email="staff@vrms.test")
    pending = Licence.objects.get(status=Licence.Status.PENDING_VERIFICATION)
    assert pending.verified_at is None and pending.verified_by is None
    # A re-run repairs a verified licence seeded before verified_at was set.
    Licence.objects.filter(pk=verified.pk).update(verified_at=None)
    _seed()
    verified.refresh_from_db()
    assert verified.verified_at is not None


def test_staff_accounts_have_an_address():
    _seed()
    for email in ["staff@vrms.test", "tech@vrms.test", "manager@vrms.test", "admin@vrms.test"]:
        assert User.objects.get(email=email).address


def test_tariff_deposits_follow_br3():
    _seed()
    assert {
        str(t.security_deposit) for t in Tariff.objects.filter(vehicle_category__vehicle_type="Car")
    } == {"5000.00"}
    assert {
        str(t.security_deposit)
        for t in Tariff.objects.filter(vehicle_category__vehicle_type="Two-Wheeler")
    } == {"2000.00"}


def test_reset_refuses_when_demo_data_is_in_use():
    _seed()
    vehicle = Car.objects.first()
    BookingFactory(
        vehicle=vehicle,
        tariff=Tariff.objects.get(vehicle_category=vehicle.category),
        customer=Customer.objects.get(user__email="customer@vrms.test"),
    )
    with pytest.raises(CommandError):
        _seed("--reset")
    assert _counts() == EXPECTED
