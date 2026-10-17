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
from apps.payments import services as payments
from apps.payments.models import Payment
from apps.payments.tests.factories import CardPaymentFactory
from apps.pricing.tests.factories import FuelPriceFactory
from apps.rentals.models import ConditionPhoto, ConditionReport
from apps.rentals.services import ReturnReadings


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
    accessories = factory.LazyFunction(lambda: [{"name": "Child seat", "quantity": 1}])


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


# ─── Return Vehicle (Module N2) ───────────────────────────────────────────


def active_booking(*, cash: bool = False, due_in=timedelta(hours=1), **booking_kwargs) -> Booking:
    """An Active one-day rental handed over at its pickup, due back `due_in` from now.

    Paid through R1's real services (the mock gateway), so the return can
    capture and refund: by card, or with cash=True in cash at the branch. The
    handover report is signed: odometer 12000 km, a full tank, a child seat
    issued. The vehicle is On Rent with a 40 L tank, and petrol is priced.
    """
    now = timezone.now()
    return_at = now + due_in
    booking = BookingFactory(
        status=Booking.Status.ACTIVE,
        pickup_datetime=return_at - timedelta(days=1),
        return_datetime=return_at,
        handed_over_at=return_at - timedelta(days=1),
        cash_on_collection=cash,
        **booking_kwargs,
    )
    vehicle = booking.vehicle
    type(vehicle).objects.filter(pk=vehicle.pk).update(
        status="On Rent", odometer=12000, fuel_capacity=Decimal("40.00")
    )
    booking.vehicle.refresh_from_db()
    amounts = {"rental_amount": booking.total_amount, "deposit_amount": booking.security_deposit}
    if cash:
        staff = BranchStaffFactory(branch=booking.pickup_branch)
        auth = payments.record_cash(
            booking, staff=staff, idempotency_key=f"test-cash-{booking.pk}", **amounts
        )
    else:
        auth = payments.authorize(
            booking,
            payment_token="tok_test",
            idempotency_key=f"test-card-{booking.pk}",
            actor=None,
            **amounts,
        )
    payments.record_booking_ledger(booking, auth, actor=None)
    ConditionReportFactory(
        booking=booking,
        signed=True,
        odometer_reading=12000,
        fuel_level=Decimal("100.00"),
        accessories=[{"name": "Child seat", "quantity": 1}],
    )
    FuelPriceFactory(fuel_type=vehicle.fuel_type, price_per_unit=Decimal("100.00"))
    return booking


def readings(**overrides):
    """services.ReturnReadings for an on-time return with nothing to charge."""
    data = {
        "odometer_reading": 12200,
        "fuel_level": Decimal("100.00"),
        "returned_at": timezone.now() - timedelta(minutes=1),
    }
    data.update(overrides)
    return ReturnReadings(**data)


def return_kwargs(**overrides) -> dict:
    """services.return_vehicle() keyword arguments for that return, settled at zero."""
    data = {
        "readings": readings(),
        "expected_total": Decimal("0.00"),
        "damage_marks": [],
        "photos": [(side, image_file(f"{side}.jpg")) for side in settings.HANDOVER_PHOTO_SIDES],
        "signature": image_file("signature.png", "PNG"),
    }
    data.update(overrides)
    return data
