"""Accounts profiles, licence and OTP models (Exp 3; Appendix A; SE-7)."""

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import Licence, OneTimePassword
from apps.accounts.tests.factories import (
    AdministratorFactory,
    CustomerFactory,
    LicenceCategoryFactory,
    LicenceFactory,
    MaintenanceTechnicianFactory,
    OneTimePasswordFactory,
)
from apps.core.choices import VehicleType

pytestmark = pytest.mark.django_db

FACTORIES = [
    CustomerFactory,
    MaintenanceTechnicianFactory,
    AdministratorFactory,
    LicenceFactory,
    LicenceCategoryFactory,
    OneTimePasswordFactory,
]


@pytest.mark.parametrize("factory_class", FACTORIES, ids=lambda f: f.__name__)
def test_factory_creates_a_valid_row(factory_class):
    instance = factory_class()
    instance.full_clean()
    assert instance.pk is not None
    assert str(instance)


def test_profiles_use_the_class_diagram_identifiers():
    assert CustomerFactory().customer_id
    assert MaintenanceTechnicianFactory().technician_id
    assert AdministratorFactory().admin_id


def test_customer_profile_is_reachable_from_user():
    customer = CustomerFactory()
    assert customer.user.customer == customer


def test_outstanding_due_cannot_be_negative():
    customer = CustomerFactory()
    customer.outstanding_due = Decimal("-1.00")
    with pytest.raises(IntegrityError), transaction.atomic():
        customer.save()


def test_licence_status_values_match_the_handoff():
    assert Licence.Status.values == [
        "Not Submitted",
        "Pending Verification",
        "Verified",
        "Rejected",
        "Expired",
    ]


def test_licence_numbers_are_unique_but_blank_numbers_are_allowed():
    LicenceFactory(licence_number="", status=Licence.Status.NOT_SUBMITTED)
    LicenceFactory(licence_number="", status=Licence.Status.NOT_SUBMITTED)
    LicenceFactory(licence_number="MH01 20200000001")
    with pytest.raises(IntegrityError), transaction.atomic():
        LicenceFactory(licence_number="MH01 20200000001")


def test_licence_has_many_categories_without_duplicates():
    licence = LicenceFactory()
    LicenceCategoryFactory(licence=licence, category=VehicleType.CAR)
    LicenceCategoryFactory(licence=licence, category=VehicleType.TWO_WHEELER)
    assert set(licence.categories.values_list("category", flat=True)) == {
        "Car",
        "Two-Wheeler",
    }
    with pytest.raises(IntegrityError), transaction.atomic():
        LicenceCategoryFactory(licence=licence, category=VehicleType.CAR)


def test_licence_is_deleted_with_its_customer():
    """Customer ◆ Licence is a composition (Exp 3)."""
    licence = LicenceFactory()
    licence.customer.delete()
    assert not Licence.objects.filter(pk=licence.pk).exists()


def test_otp_stores_only_a_hash_of_the_code():
    otp = OneTimePasswordFactory()
    field_names = {f.name for f in OneTimePassword._meta.get_fields()}
    assert "code" not in field_names
    assert otp.code_hash != "123456"
    assert otp.code_hash.startswith("bcrypt_sha256$")
