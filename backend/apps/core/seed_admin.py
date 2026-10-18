"""DEMO data for the blacklist (Exp 2 use case 12 extension 2a; Module N3), loaded by
seed_demo (fictitious data, not business rules).

- blacklist@vrms.test, "Demo Customer (blacklist)", with a verified car licence
  (password as the other demo accounts). Not blacklisted: the Administrator
  blacklists them on /app/users with a reason.
- MH02DB8001, Confirmed for a two-day rental three days ahead, paid by card
  (the mock gateway): the blacklist screen lists it with a Cancel action,
  which goes through R2's cancellation (BR-8 refund).
- MH02DB8002, On Rent to them in an Active three-day rental due back two days
  after seeding: listed as "return pending", with no cancel action.

As in the other demos the bookings pass through the booking state machine and
the payments service, audited as system actions; the handover report of the
Active rental is unsigned (as in N2's demo), so --reset can remove it all
until a booking is cancelled or returned (refunds and returns are append-only).
"""

from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.utils import timezone

from apps.accounts.models import BranchStaff, Customer, Licence, LicenceCategory, User
from apps.bookings.lifecycle import booking_quote
from apps.bookings.models import Booking
from apps.bookings.numbering import next_in_sequence
from apps.bookings.states import transition
from apps.core.choices import FuelType, VehicleType
from apps.fleet.models import Branch, Car, Vehicle, VehicleCategory, VehicleDocument
from apps.fleet.services.status import update_status
from apps.payments import services as payments
from apps.pricing.services import current_tariff
from apps.rentals.models import ConditionReport
from apps.rentals.seed import _audit

BRANCH = "Andheri"
CUSTOMER_EMAIL = "blacklist@vrms.test"
CUSTOMER_NAME = "Demo Customer (blacklist)"
CUSTOMER_MOBILE = "+919800000012"
LICENCE_NUMBER = "MH02 20190011223"
CONFIRMED_CAR = "MH02DB8001"
ACTIVE_CAR = "MH02DB8002"
REGISTRATIONS = [CONFIRMED_CAR, ACTIVE_CAR]

Status = Booking.Status


def _seed_cars(count) -> dict[str, Car]:
    cars = {}
    for index, registration in enumerate(REGISTRATIONS):
        car, created = Car.objects.get_or_create(
            registration_no=registration,
            defaults={
                "brand": "Honda",
                "model": ("Amaze", "Jazz")[index],
                "category": VehicleCategory.objects.get(name="Hatchback"),
                "home_branch": Branch.objects.get(branch_name=BRANCH),
                "year": 2025,
                "colour": ("White", "Red")[index],
                "fuel_type": FuelType.PETROL,
                "chassis_number": f"DEMOBLACKLIST00{index + 1}",
                "available_from": date(2026, 1, 1),
                "odometer": 9100 + 1000 * index,
                "last_service_date": date(2026, 9, 10),
                "last_service_odometer": 9000 + 1000 * index,
                "transmission": Car.Transmission.MANUAL,
                "seating_capacity": 5,
                "fuel_capacity": Decimal("35.00"),
            },
        )
        count("vehicles", created)
        if created:
            _audit("Create", car)
        _, created = VehicleDocument.objects.get_or_create(
            vehicle=car,
            document_type=VehicleDocument.DocumentType.INSURANCE,
            defaults={
                "document_number": f"DEMO-BL-{index + 1:03d}",
                "valid_from": date(2026, 1, 1),
                "expiry_date": date(2027, 12, 31),
            },
        )
        count("vehicle documents", created)
        cars[registration] = car
    return cars


def _seed_customer(count) -> Customer:
    from apps.core.management.commands.seed_demo import DEMO_PASSWORD, STAFF

    user = User.objects.filter(email=CUSTOMER_EMAIL).first()
    if user is None:
        user = User.objects.create_user(
            email=CUSTOMER_EMAIL,
            password=DEMO_PASSWORD,
            name=CUSTOMER_NAME,
            mobile_no=CUSTOMER_MOBILE,
            role=User.Role.CUSTOMER,
            address="31 Demo Lane, Andheri (E), Mumbai 400069",
        )
        count("users", True)
        _audit("Create", user)
    customer, created = Customer.objects.get_or_create(
        user=user,
        defaults={
            "date_of_birth": date(1991, 2, 14),
            "emergency_contact_name": "Demo Emergency Contact",
            "emergency_contact_mobile": "+919800000093",
        },
    )
    count("customers", created)
    licence, created = Licence.objects.get_or_create(
        customer=customer,
        defaults={
            "licence_number": LICENCE_NUMBER,
            "issuing_authority": "RTO Mumbai (West)",
            "issue_date": date(2019, 5, 2),
            "expiry_date": date(2039, 2, 13),
            "status": Licence.Status.VERIFIED,
            "verified_by": User.objects.get(email=STAFF.email),
            "verified_at": timezone.make_aware(datetime(2026, 10, 9, 13, 0)),
        },
    )
    count("licences", created)
    _, created = LicenceCategory.objects.get_or_create(licence=licence, category=VehicleType.CAR)
    count("licence categories", created)
    return customer


def _seed_booking(count, car: Car, customer: Customer, pickup, return_, *, active: bool) -> None:
    """Draft -> Pending Payment -> Confirmed (paid by card); with `active`, handed over at
    the pickup too: Active, the car On Rent, and an unsigned handover report."""
    period = Booking(pickup_datetime=pickup, return_datetime=return_).compute_blocked_period()
    car.refresh_from_db()
    if (
        car.status != Vehicle.Status.AVAILABLE
        or car.bookings.filter(
            status__in=Booking.BLOCKING_STATUSES, blocked_period__overlap=period
        ).exists()
    ):
        return
    booking = Booking.objects.create(
        customer=customer,
        vehicle=car,
        pickup_branch=car.home_branch,
        tariff=current_tariff(car.category, pickup),
        pickup_datetime=pickup,
        return_datetime=return_,
        terms_accepted_at=min(pickup, timezone.now()) - timedelta(hours=1),
    )
    priced = booking_quote(booking)
    booking.total_amount = priced.total_payable
    booking.security_deposit = priced.security_deposit
    transition(
        booking,
        Status.PENDING_PAYMENT,
        actor=None,
        reason="Demo booking (seed_demo).",
        update_fields=("total_amount", "security_deposit"),
    )
    auth = payments.authorize(
        booking,
        rental_amount=priced.total_payable,
        deposit_amount=priced.security_deposit,
        payment_token="tok_demo",
        idempotency_key=f"demo-blacklist-{booking.pk}",
        actor=None,
    )
    booking.booking_reference = next_in_sequence(
        Booking, "booking_reference", f"VRMS-{timezone.localdate():%Y%m%d}-", 4
    )
    booking.pickup_code = f"{975300 + booking.pk % 100:06d}"
    booking.confirmed_at = timezone.now()
    transition(
        booking,
        Status.CONFIRMED,
        actor=None,
        reason=f"Demo booking paid, transaction {auth.transaction_id} (seed_demo).",
        update_fields=("booking_reference", "pickup_code", "confirmed_at"),
    )
    count("bookings", True)
    if not active:
        return
    booking.handed_over_at = pickup + timedelta(minutes=10)
    transition(
        booking,
        Status.ACTIVE,
        actor=None,
        reason="Demo rental handed over (seed_demo).",
        update_fields=("handed_over_at",),
    )
    update_status(
        car,
        Vehicle.Status.ON_RENT,
        actor=None,
        reason=f"Demo rental {booking.booking_reference} (seed_demo).",
    )
    ConditionReport.objects.create(  # unsigned, so --reset can remove it
        booking=booking,
        report_type=ConditionReport.ReportType.HANDOVER,
        odometer_reading=car.odometer,
        fuel_level=Decimal("100.00"),
        recorded_by=BranchStaff.objects.get(user__email="staff@vrms.test"),
        recorded_at=booking.handed_over_at,
        accessories=[],
    )


def seed_demo_blacklist_data(count: Callable[[str, bool], None]) -> None:
    """Called by seed_demo after its own data; `count(label, created)` is its counter."""
    cars = _seed_cars(count)
    customer = _seed_customer(count)
    ahead = (timezone.localtime() + timedelta(days=3)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    _seed_booking(
        count, cars[CONFIRMED_CAR], customer, ahead, ahead + timedelta(days=2), active=False
    )
    now = timezone.now().replace(second=0, microsecond=0)
    _seed_booking(
        count,
        cars[ACTIVE_CAR],
        customer,
        now - timedelta(days=1),
        now + timedelta(days=2),  # not due back today, so N2's return list keeps its two
        active=True,
    )


def delete_demo_blacklist_data() -> None:
    """For seed_demo --reset: remove only what seed_demo_blacklist_data() creates.

    Raises ProtectedError, like the rest of the reset, once a demo booking has been
    cancelled or returned: refunds, ledger entries and signed reports are append-only.
    """
    for car in Car.objects.filter(registration_no__in=REGISTRATIONS):
        for booking in car.bookings.all():
            booking.condition_reports.filter(signature="").delete()
            booking.payments.all().delete()
            booking.delete()
        _audit("Delete", car)
        car.delete()
    Customer.objects.filter(user__email=CUSTOMER_EMAIL).delete()  # the licence cascades
    for user in User.objects.filter(email=CUSTOMER_EMAIL):
        _audit("Delete", user)
        user.delete()
