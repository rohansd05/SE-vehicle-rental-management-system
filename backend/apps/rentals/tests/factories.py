"""factory-boy factories for rentals."""

from decimal import Decimal

import factory
from django.utils import timezone

from apps.accounts.tests.factories import BranchStaffFactory
from apps.bookings.models import Booking
from apps.bookings.tests.factories import BookingFactory
from apps.rentals.models import ConditionPhoto, ConditionReport


class ConditionReportFactory(factory.django.DjangoModelFactory):
    """An unsigned handover report; use signed=True for a signed one."""

    class Meta:
        model = ConditionReport

    class Params:
        signed = factory.Trait(
            signature=factory.Sequence(lambda n: f"rentals/signatures/sig-{n}.png"),
            signed_at=factory.LazyFunction(timezone.now),
        )

    booking = factory.SubFactory(BookingFactory, status=Booking.Status.ACTIVE)
    report_type = ConditionReport.ReportType.HANDOVER
    odometer_reading = factory.SelfAttribute("booking.vehicle.odometer")
    fuel_level = Decimal("100.00")
    recorded_by = factory.SubFactory(
        BranchStaffFactory, branch=factory.SelfAttribute("..booking.pickup_branch")
    )
    accessories = factory.LazyFunction(lambda: ["Spare wheel", "Jack"])


class ConditionPhotoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ConditionPhoto

    report = factory.SubFactory(ConditionReportFactory)
    image = factory.Sequence(lambda n: f"rentals/photos/photo-{n}.jpg")
    caption = "Front"
