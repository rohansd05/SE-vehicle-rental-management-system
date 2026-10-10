"""factory-boy factories for pricing."""

from datetime import timedelta
from decimal import Decimal

import factory
from django.utils import timezone

from apps.accounts.tests.factories import AdministratorFactory
from apps.core.choices import FuelType
from apps.fleet.tests.factories import VehicleCategoryFactory
from apps.pricing.models import AddOn, DiscountCode, FuelPrice, Tariff


class TariffFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tariff

    vehicle_category = factory.SubFactory(VehicleCategoryFactory)
    hourly_rate = Decimal("150.00")
    daily_rate = Decimal("1800.00")
    weekly_rate = Decimal("11000.00")
    security_deposit = Decimal("5000.00")
    free_km_allowance = 250
    excess_km_rate = Decimal("12.00")
    effective_from = factory.LazyFunction(lambda: timezone.now() - timedelta(days=30))
    defined_by = factory.SubFactory(AdministratorFactory)


class AddOnFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AddOn
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Add-on {n}")
    daily_rate = Decimal("100.00")


class FuelPriceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = FuelPrice

    fuel_type = FuelType.PETROL
    price_per_unit = Decimal("104.21")
    effective_from = factory.Sequence(
        lambda n: timezone.now() - timedelta(days=30) + timedelta(minutes=n)
    )
    defined_by = factory.SubFactory(AdministratorFactory)


class DiscountCodeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DiscountCode

    code = factory.Sequence(lambda n: f"SAVE{n:04d}")
    discount_type = DiscountCode.DiscountType.PERCENT
    value = Decimal("10.00")
    valid_from = factory.LazyFunction(lambda: timezone.now() - timedelta(days=1))
    valid_to = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))
