"""factory-boy factories for rentals."""

import io
from datetime import timedelta
from decimal import Decimal

import factory
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from apps.accounts.tests.factories import (
    BranchStaffFactory,
    CustomerFactory,
    LicenceCategoryFactory,
    LicenceFactory,
)
from apps.bookings.models import Booking
from apps.bookings.tests.factories import BookingFactory
from apps.core.choices import VehicleType
from apps.fleet.tests.factories import VehicleDocumentFactory
from apps.payments.models import Payment
from apps.payments.tests.factories import CardPaymentFactory
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


def ready_booking(**booking_kwargs) -> Booking:
    """A Confirmed, paid booking whose pickup time has come and nothing blocks its handover.

    The customer holds a verified car and two-wheeler licence (BR-2, BR-3),
    the vehicle every SA-3 document for the whole period, and the deposit
    authorisation succeeded.
    """
    customer = CustomerFactory()
    licence = LicenceFactory(customer=customer)
    for category in (VehicleType.CAR, VehicleType.TWO_WHEELER):
        LicenceCategoryFactory(licence=licence, category=category)
    now = timezone.now()
    booking = BookingFactory(
        customer=customer,
        pickup_datetime=now - timedelta(hours=1),
        return_datetime=now + timedelta(days=1),
        **booking_kwargs,
    )
    for document_type in settings.HANDOVER_REQUIRED_DOCUMENTS:
        VehicleDocumentFactory(vehicle=booking.vehicle, document_type=document_type)
    CardPaymentFactory(
        booking=booking,
        purpose=Payment.Purpose.SECURITY_DEPOSIT,
        amount=booking.security_deposit,
    )
    return booking


def image_file(name="photo.jpg", fmt="JPEG", size=(32, 24)) -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format=fmt)
    content_type = "image/png" if fmt == "PNG" else "image/jpeg"
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)


def checklist(**overrides) -> dict:
    """services.capture_report() keyword arguments for a complete handover."""
    data = {
        "odometer_reading": 15000,
        "fuel_level": Decimal("75.00"),
        "accessories": [{"name": "Child seat", "quantity": 1}],
        "damage_marks": [{"x": 20, "y": 80, "note": "Scratch on the rear bumper"}],
        "photos": [(side, image_file(f"{side}.jpg")) for side in settings.HANDOVER_PHOTO_SIDES],
        "signature": image_file("signature.png", "PNG"),
    }
    data.update(overrides)
    return data
