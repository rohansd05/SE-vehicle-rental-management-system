"""DEMO data for Return Vehicle (Module N2), loaded by seed_demo (fictitious).

- return@vrms.test, a demo customer with a verified car licence. Password
  as the other demo accounts.
- MH02DT6001 and MH02DT6002, two demo hatchbacks at Andheri with a 37 L
  tank (BR-12 needs the capacity), each On Rent to that customer in an
  Active one-day booking paid by card:
  - MH02DT6001 is due back two hours after seed_demo runs: return it on time.
  - MH02DT6002 was due back three hours before seed_demo ran, with a child
    seat issued. Return it with 400 km more on the odometer and the tank at
    75%, and the settlement lists the late return (BR-10), the excess
    kilometres (BR-11), the fuel shortfall (BR-12) and the tax; leave the
    child seat unticked to charge for it too.
- Each has a handover condition report (the odometer, a full tank, the
  accessories issued) recorded by staff@vrms.test. It is left unsigned and
  without photographs: a signed report can never be deleted (Handover.Sign),
  so --reset could otherwise never remove it. The photographs side by side
  are shown by returning the handover demo booking (rentals/seed.py) once it
  is handed over.

As in the other demos the bookings pass through the booking state machine
and the payments service with the mock gateway, audited as system actions
(actor None). No invoice or ledger entry is written, so --reset removes
them until the demo returns one (a return writes append-only records).

Idempotent: the cars and the customer are created once; a car gets a new
booking only while it is Available and nothing blocks the period, so a
second run changes nothing and a run after a return makes it ready again.
"""

from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.utils import timezone

from apps.accounts.models import BranchStaff, Customer, Licence, LicenceCategory, User
from apps.bookings.lifecycle import booking_quote
from apps.bookings.models import Booking, BookingAddOn
from apps.bookings.numbering import next_in_sequence
from apps.bookings.states import transition
from apps.core.choices import FuelType, VehicleType
from apps.fleet.models import Branch, Car, Vehicle, VehicleCategory
from apps.fleet.services.status import update_status
from apps.payments import services as payments
from apps.pricing.models import AddOn
from apps.pricing.services import current_tariff

from .models import ConditionReport
from .seed import _audit

BRANCH = "Andheri"
CUSTOMER_EMAIL = "return@vrms.test"
CUSTOMER_NAME = "Demo Customer (return)"
CUSTOMER_MOBILE = "+919800000010"
LICENCE_NUMBER = "MH02 20170045678"
ON_TIME_CAR = "MH02DT6001"
LATE_CAR = "MH02DT6002"
REGISTRATIONS = [ON_TIME_CAR, LATE_CAR]
FUEL_CAPACITY = Decimal("37.00")  # litres

Status = Booking.Status


def _seed_cars(count: Callable[[str, bool], None]) -> dict[str, Car]:
    cars = {}
    for index, (registration, model, colour) in enumerate(
        [(ON_TIME_CAR, "i20", "Blue"), (LATE_CAR, "Grand i10 Nios", "Silver")]
    ):
        car, created = Car.objects.get_or_create(
            registration_no=registration,
            defaults={
                "brand": "Hyundai",
                "model": model,
                "category": VehicleCategory.objects.get(name="Hatchback"),
                "home_branch": Branch.objects.get(branch_name=BRANCH),
                "year": 2025,
                "colour": colour,
                "fuel_type": FuelType.PETROL,
                "chassis_number": f"DEMORETURN000{index + 1}",
                "available_from": date(2026, 1, 1),
                "odometer": 15400 + 2000 * index,
                "last_service_date": date(2026, 9, 1),
                "last_service_odometer": 15000 + 2000 * index,
                "transmission": Car.Transmission.MANUAL,
                "seating_capacity": 5,
                "fuel_capacity": FUEL_CAPACITY,
            },
        )
        count("vehicles", created)
        if created:
            _audit("Create", car)
        cars[registration] = car
    return cars


def _seed_customer(count: Callable[[str, bool], None]) -> Customer:
    from apps.core.management.commands.seed_demo import DEMO_PASSWORD, STAFF

    user = User.objects.filter(email=CUSTOMER_EMAIL).first()
    if user is None:
        user = User.objects.create_user(
            email=CUSTOMER_EMAIL,
            password=DEMO_PASSWORD,
            name=CUSTOMER_NAME,
            mobile_no=CUSTOMER_MOBILE,
            role=User.Role.CUSTOMER,
            address="22 Demo Lane, Andheri (W), Mumbai 400058",
        )
        count("users", True)
        _audit("Create", user)
    customer, created = Customer.objects.get_or_create(
        user=user,
        defaults={
            "date_of_birth": date(1990, 4, 12),
            "emergency_contact_name": "Demo Emergency Contact",
            "emergency_contact_mobile": "+919800000094",
        },
    )
    count("customers", created)
    licence, created = Licence.objects.get_or_create(
        customer=customer,
        defaults={
            "licence_number": LICENCE_NUMBER,
            "issuing_authority": "RTO Mumbai (West)",
            "issue_date": date(2017, 3, 2),
            "expiry_date": date(2037, 4, 11),
            "status": Licence.Status.VERIFIED,
            "verified_by": User.objects.get(email=STAFF.email),
            "verified_at": timezone.make_aware(datetime(2026, 10, 9, 12, 30)),
        },
    )
    count("licences", created)
    _, created = LicenceCategory.objects.get_or_create(licence=licence, category=VehicleType.CAR)
    count("licence categories", created)
    return customer


def _seed_rental(count, car: Car, customer: Customer, due: datetime, *, child_seat: bool) -> None:
    """An Active one-day booking due back at `due`, handed over ten minutes after pickup."""
    pickup = due - timedelta(days=1)
    period = Booking(pickup_datetime=pickup, return_datetime=due).compute_blocked_period()
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
        return_datetime=due,
        terms_accepted_at=pickup - timedelta(days=1),
    )
    accessories = []
    if child_seat:
        seat = AddOn.objects.get(name="Child seat")
        BookingAddOn.objects.create(booking=booking, add_on=seat, daily_rate=seat.daily_rate)
        accessories.append({"name": seat.name, "quantity": 1})
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
        idempotency_key=f"demo-return-{booking.pk}",
        actor=None,
    )
    booking.booking_reference = next_in_sequence(
        Booking, "booking_reference", f"VRMS-{timezone.localdate():%Y%m%d}-", 4
    )
    booking.pickup_code = f"{864200 + booking.pk % 100:06d}"
    booking.confirmed_at = timezone.now()
    transition(
        booking,
        Status.CONFIRMED,
        actor=None,
        reason=f"Demo booking paid, transaction {auth.transaction_id} (seed_demo).",
        update_fields=("booking_reference", "pickup_code", "confirmed_at"),
    )
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
    ConditionReport.objects.create(  # unsigned, so --reset can remove it (see above)
        booking=booking,
        report_type=ConditionReport.ReportType.HANDOVER,
        odometer_reading=car.odometer,
        fuel_level=Decimal("100.00"),
        recorded_by=BranchStaff.objects.get(user__email="staff@vrms.test"),
        recorded_at=booking.handed_over_at,
        accessories=accessories,
    )
    count("bookings", True)


def seed_demo_return_data(count: Callable[[str, bool], None]) -> None:
    """Called by seed_demo after its own data; `count(label, created)` is its counter."""
    cars = _seed_cars(count)
    customer = _seed_customer(count)
    now = timezone.now().replace(second=0, microsecond=0)
    _seed_rental(count, cars[ON_TIME_CAR], customer, now + timedelta(hours=2), child_seat=False)
    _seed_rental(count, cars[LATE_CAR], customer, now - timedelta(hours=3), child_seat=True)


def delete_demo_return_data() -> None:
    """For seed_demo --reset: remove only what seed_demo_return_data() creates.

    Raises ProtectedError, like the rest of the reset, once a demo booking
    has been returned: its signed return report, ledger entries and
    notifications are append-only.
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
