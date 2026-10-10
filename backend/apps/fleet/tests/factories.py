"""factory-boy factories for fleet."""

from datetime import date, timedelta

import factory

from apps.core.choices import FuelType, VehicleType
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


class BranchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Branch
        django_get_or_create = ("branch_name",)

    branch_name = factory.Sequence(lambda n: f"Branch {n}")
    address = factory.Faker("address")


class BranchServiceableAreaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BranchServiceableArea

    branch = factory.SubFactory(BranchFactory)
    pincode = factory.Sequence(lambda n: f"{400001 + n:06d}")
    locality = factory.Sequence(lambda n: f"Locality {n}")


class VehicleCategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VehicleCategory
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Category {n}")
    vehicle_type = VehicleType.CAR


class _VehicleFields(factory.django.DjangoModelFactory):
    registration_no = factory.Sequence(lambda n: f"MH01AB{n:04d}")
    brand = "Maruti Suzuki"
    model = "Swift"
    odometer = 12000
    category = factory.SubFactory(VehicleCategoryFactory)
    home_branch = factory.SubFactory(BranchFactory)
    year = 2023
    colour = "White"
    fuel_type = FuelType.PETROL
    chassis_number = factory.Sequence(lambda n: f"MA3CHASSIS{n:07d}")
    available_from = factory.LazyFunction(lambda: date.today() - timedelta(days=30))


class VehicleFactory(_VehicleFields):
    class Meta:
        model = Vehicle


class CarFactory(_VehicleFields):
    class Meta:
        model = Car

    seating_capacity = 5
    transmission = Car.Transmission.MANUAL


class TwoWheelerFactory(_VehicleFields):
    class Meta:
        model = TwoWheeler

    brand = "Honda"
    model = "Activa 6G"
    odometer = 4000
    category = factory.SubFactory(
        VehicleCategoryFactory, name="Scooter", vehicle_type=VehicleType.TWO_WHEELER
    )
    engine_cc = 110


class VehicleDocumentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VehicleDocument

    vehicle = factory.SubFactory(CarFactory)
    document_type = VehicleDocument.DocumentType.INSURANCE
    document_number = factory.Sequence(lambda n: f"POL{n:08d}")
    valid_from = factory.LazyFunction(lambda: date.today() - timedelta(days=100))
    expiry_date = factory.LazyFunction(lambda: date.today() + timedelta(days=265))


class VehiclePhotoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VehiclePhoto

    vehicle = factory.SubFactory(CarFactory)
    image = factory.Sequence(lambda n: f"vehicles/photos/photo-{n}.jpg")
    position = factory.Sequence(int)
