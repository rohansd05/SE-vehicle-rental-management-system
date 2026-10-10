"""Condition reports (Exp 3; Handover.Sign; Appendix A)."""

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.core.exceptions import ImmutableRecordError
from apps.rentals.models import ConditionReport
from apps.rentals.tests.factories import ConditionPhotoFactory, ConditionReportFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "factory_class", [ConditionReportFactory, ConditionPhotoFactory], ids=lambda f: f.__name__
)
def test_factory_creates_a_valid_row(factory_class):
    instance = factory_class()
    instance.full_clean()
    assert instance.pk is not None
    assert str(instance)


def test_one_handover_and_one_return_report_per_booking():
    """Booking ◆ ConditionReport (0..2)."""
    handover = ConditionReportFactory()
    ConditionReportFactory(booking=handover.booking, report_type="Return")
    with pytest.raises(IntegrityError), transaction.atomic():
        ConditionReportFactory(booking=handover.booking, report_type="Handover")


@pytest.mark.parametrize("level", [Decimal("-0.01"), Decimal("100.01")])
def test_fuel_level_is_a_percentage(level):
    with pytest.raises(IntegrityError), transaction.atomic():
        ConditionReportFactory(fuel_level=level)


class TestSignedReportIsFinal:
    """Handover.Sign: a signed report cannot subsequently be altered."""

    def test_unsigned_report_can_be_corrected(self):
        report = ConditionReportFactory()
        report.odometer_reading += 1
        report.save()

    def test_signing_an_unsigned_report_is_allowed(self):
        report = ConditionReportFactory()
        report.signature = "rentals/signatures/new.png"
        report.save()
        assert ConditionReport.objects.get(pk=report.pk).signature.name.endswith("new.png")

    def test_signed_report_cannot_be_saved_again(self):
        report = ConditionReport.objects.get(pk=ConditionReportFactory(signed=True).pk)
        report.fuel_level = Decimal("50.00")
        with pytest.raises(ImmutableRecordError):
            report.save()

    def test_report_just_signed_in_memory_cannot_be_changed(self):
        report = ConditionReportFactory()
        report.signature = "rentals/signatures/new.png"
        report.save()
        report.fuel_level = Decimal("10.00")
        with pytest.raises(ImmutableRecordError):
            report.save()

    def test_signed_report_cannot_be_deleted(self):
        report = ConditionReport.objects.get(pk=ConditionReportFactory(signed=True).pk)
        with pytest.raises(ImmutableRecordError):
            report.delete()

    def test_photos_of_a_signed_report_are_frozen(self):
        report = ConditionReportFactory()
        photo = ConditionPhotoFactory(report=report)
        report.signature = "rentals/signatures/new.png"
        report.save()
        with pytest.raises(ImmutableRecordError):
            ConditionPhotoFactory(report=report)
        with pytest.raises(ImmutableRecordError):
            photo.delete()
