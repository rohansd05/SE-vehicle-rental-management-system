"""Pricing models (Exp 3 Tariff; Fleet.Tariff; BR-7, BR-12, BR-13)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.exceptions import ImmutableRecordError
from apps.pricing.models import Tariff
from apps.pricing.tests.factories import AddOnFactory, FuelPriceFactory, TariffFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "factory_class", [TariffFactory, AddOnFactory, FuelPriceFactory], ids=lambda f: f.__name__
)
def test_factory_creates_a_valid_row(factory_class):
    instance = factory_class()
    instance.full_clean()
    assert instance.pk is not None
    assert str(instance)


class TestTariffImmutability:
    """BR-13: a tariff in effect is never edited; a change is a new row."""

    def test_tariff_in_effect_cannot_be_edited(self):
        tariff = Tariff.objects.get(pk=TariffFactory().pk)
        tariff.daily_rate = Decimal("1.00")
        with pytest.raises(ImmutableRecordError):
            tariff.save()

    def test_tariff_in_effect_cannot_be_moved_into_the_future(self):
        tariff = TariffFactory()
        tariff.effective_from = timezone.now() + timedelta(days=10)
        with pytest.raises(ImmutableRecordError):
            tariff.save()

    def test_tariff_in_effect_cannot_be_deleted(self):
        with pytest.raises(ImmutableRecordError):
            TariffFactory().delete()

    def test_future_tariff_can_still_be_corrected(self):
        tariff = TariffFactory(effective_from=timezone.now() + timedelta(days=7))
        tariff.daily_rate = Decimal("1900.00")
        tariff.save()
        assert Tariff.objects.get(pk=tariff.pk).daily_rate == Decimal("1900.00")

    def test_a_change_is_a_new_row_and_history_is_kept(self):
        old = TariffFactory()
        new = TariffFactory(
            vehicle_category=old.vehicle_category,
            daily_rate=Decimal("2000.00"),
            effective_from=timezone.now(),
        )
        history = Tariff.objects.filter(vehicle_category=old.vehicle_category)
        assert list(history) == [new, old]
        assert history.latest() == new

    def test_one_tariff_per_category_and_start(self):
        tariff = TariffFactory()
        with pytest.raises(IntegrityError), transaction.atomic():
            TariffFactory(
                vehicle_category=tariff.vehicle_category, effective_from=tariff.effective_from
            )


def test_amounts_cannot_be_negative():
    with pytest.raises(IntegrityError), transaction.atomic():
        TariffFactory(hourly_rate=Decimal("-1.00"))
    with pytest.raises(IntegrityError), transaction.atomic():
        AddOnFactory(daily_rate=Decimal("-1.00"))
