"""Fleet models (Exp 3; Fleet.Add; Appendix A)."""

from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from apps.fleet.models import Vehicle, VehicleDocument
from apps.fleet.tests.factories import (
    BranchFactory,
    BranchServiceableAreaFactory,
    CarFactory,
    TwoWheelerFactory,
    VehicleCategoryFactory,
    VehicleDocumentFactory,
    VehicleFactory,
    VehiclePhotoFactory,
)

pytestmark = pytest.mark.django_db

FACTORIES = [
    BranchFactory,
    BranchServiceableAreaFactory,
    VehicleCategoryFactory,
    VehicleFactory,
    CarFactory,
    TwoWheelerFactory,
    VehicleDocumentFactory,
    VehiclePhotoFactory,
]


@pytest.mark.parametrize("factory_class", FACTORIES, ids=lambda f: f.__name__)
def test_factory_creates_a_valid_row(factory_class):
    instance = factory_class()
    instance.full_clean()
    assert instance.pk is not None
    assert str(instance)


def test_vehicle_status_values_match_the_handoff():
    assert Vehicle.Status.values == [
        "Available",
        "On Rent",
        "Under Maintenance",
        "Unsafe",
        "Retired",
    ]


def test_cars_and_two_wheelers_share_the_vehicle_table():
    car = CarFactory()
    bike = TwoWheelerFactory()
    assert set(Vehicle.objects.values_list("pk", flat=True)) == {car.pk, bike.pk}
    assert Vehicle.objects.get(pk=car.pk).car.seating_capacity == 5
    assert bike.vehicle_type == "Two-Wheeler"
    assert car.vehicle_type == "Car"


def test_registration_and_chassis_numbers_are_unique():
    car = CarFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        CarFactory(registration_no=car.registration_no)
    with pytest.raises(IntegrityError), transaction.atomic():
        CarFactory(chassis_number=car.chassis_number)


def test_branch_with_vehicles_cannot_be_deleted():
    """Branch ◇ Vehicle: PROTECT, a vehicle is reassigned, never orphaned."""
    car = CarFactory()
    with pytest.raises(ProtectedError):
        car.home_branch.delete()


def test_category_in_use_cannot_be_deleted():
    car = CarFactory()
    with pytest.raises(ProtectedError):
        car.category.delete()


def test_serviceable_areas_are_rows_of_the_branch():
    branch = BranchFactory()
    BranchServiceableAreaFactory(branch=branch, pincode="400050", locality="Bandra West")
    BranchServiceableAreaFactory(branch=branch, pincode="400051", locality="Bandra East")
    assert sorted(branch.serviceable_areas.values_list("pincode", flat=True)) == [
        "400050",
        "400051",
    ]
    with pytest.raises(IntegrityError), transaction.atomic():
        BranchServiceableAreaFactory(branch=branch, pincode="400050", locality="Bandra West")


def test_pincode_must_be_six_digits():
    area = BranchServiceableAreaFactory.build(branch=BranchFactory(), pincode="4000")
    with pytest.raises(ValidationError):
        area.full_clean()


def test_last_service_odometer_cannot_exceed_the_odometer():
    with pytest.raises(IntegrityError), transaction.atomic():
        CarFactory(odometer=1000, last_service_odometer=1500)


def test_document_cannot_expire_before_it_starts():
    with pytest.raises(IntegrityError), transaction.atomic():
        VehicleDocumentFactory(valid_from=date(2026, 5, 1), expiry_date=date(2026, 4, 1))


def test_document_types_are_the_sa3_statutory_documents():
    assert VehicleDocument.DocumentType.values == [
        "Insurance",
        "Pollution Certificate",
        "Fitness Certificate",
        "Road Tax",
    ]
