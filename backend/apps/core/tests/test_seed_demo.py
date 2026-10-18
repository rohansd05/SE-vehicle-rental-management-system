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
    VehiclePhoto,
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
    # + the cash and refund demo cars (payments/seed.py)
    # + the two booking-changes cars (bookings/seed_changes.py)
    # + the two return demo cars (rentals/seed_return.py)
    # + the service-due car (maintenance/seed_n3.py) and the two blacklist cars (core/seed_admin.py)
    Vehicle: 34,
    Car: 24,
    TwoWheeler: 10,
    # one each, and the four of the handover car and of the service-due car (SA-3)
    VehicleDocument: 38,
    # Module R4 (fleet/seed.py): four photographs of every one of the 34 demo vehicles
    VehiclePhoto: 136,
    # 5 + pending@ (bookings/seed.py) + handover@ (rentals/seed.py) + payments@ (payments/seed.py)
    # + changes@ (bookings/seed_changes.py) + return@ (rentals/seed_return.py)
    # + tech2@ (maintenance/seed_n3.py) + blacklist@ (core/seed_admin.py)
    User: 12,
    Customer: 7,
    Licence: 7,
    LicenceCategory: 11,
    BranchStaff: 1,
    MaintenanceTechnician: 2,
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
    # Fleet.Audit: 5 branches, 12 users, 5 tariffs and 34 vehicles were audited.
    assert AuditLog.objects.filter(action="Create").count() == 56
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
    assert AuditLog.objects.filter(action="Delete").count() == 56
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


def test_every_demo_vehicle_has_its_fuel_capacity():
    """BR-12 (N2-P3): N2's fuel shortfall can be charged on any demo vehicle."""
    _seed()
    assert not Vehicle.objects.filter(fuel_capacity__isnull=True).exists()
    assert str(Car.objects.get(model="Tiago EV").fuel_capacity) == "24.00"  # kWh
    assert str(Car.objects.get(model="Dzire").fuel_capacity) == "12.00"  # kg of CNG


def test_fuel_capacity_is_filled_on_vehicles_seeded_before_it_was_set():
    _seed()
    Vehicle.objects.filter(registration_no="MH02DH3001").update(fuel_capacity=None)
    _seed()
    assert str(Vehicle.objects.get(registration_no="MH02DH3001").fuel_capacity) == "37.00"
    entry = AuditLog.objects.filter(action="Update", entity_type="fleet.Vehicle").last()
    assert entry.after["fuel_capacity"] == "37.00"
