"""DEMO data for Modify / Cancel / Extend and the No-show (Module R2), loaded by seed_demo.

All fictitious:

- changes@vrms.test, a demo customer with a verified licence. Password as
  the other demo accounts.
- MH02DR5001 and MH02DR5002, two demo hatchbacks at Andheri (the same
  category and tariff, so each is the other's UC 4 extension 3a
  alternative).
- On MH02DR5001, two Confirmed bookings paid by card: five days ahead for
  two days (modify it, or cancel it for a 100% refund under BR-8), and nine
  days ahead for one day, so moving the first onto that day shows "not
  free" with the alternatives.
- On MH02DR5002, a Confirmed two-day booking whose pickup was yesterday at
  10:00 IST and that was never handed over: the declare_no_shows Celery Beat
  task marks it No-show within a minute (BR-8: half the rental and the
  deposit refunded). Yesterday, so it never joins today's collections list.
- Extend: hand over the handover demo booking (handover@vrms.test,
  rentals/seed.py) as staff@vrms.test, then sign in as that customer.

As in the payments demo, bookings pass through the booking state machine and
the payments service with the mock gateway, audited as system actions (actor
None), and no invoice is issued, so --reset can remove them until the demo
moves money (a refund or charge writes append-only ledger entries).

Idempotent: the cars and the customer are created once; a booking is added
only when none of the car's bookings blocks its period, and the no-show
booking only once per pickup day.
"""

from collections.abc import Callable
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from apps.accounts.models import Customer, Licence, LicenceCategory, User
from apps.core.choices import FuelType, VehicleType
from apps.fleet.models import Branch, Car, VehicleCategory, VehicleDocument
from apps.payments import services as payments
from apps.payments.models import Payment, RefundRequest
from apps.pricing.services import current_tariff

from .lifecycle import booking_quote
from .models import Booking
from .numbering import next_in_sequence
from .seed import _audit
from .states import transition

BRANCH = "Andheri"
CUSTOMER_EMAIL = "changes@vrms.test"
CUSTOMER_NAME = "Demo Customer (booking changes)"
CUSTOMER_MOBILE = "+919800000009"
LICENCE_NUMBER = "MH02 20160033445"
CHANGE_CAR = "MH02DR5001"
NO_SHOW_CAR = "MH02DR5002"
REGISTRATIONS = [CHANGE_CAR, NO_SHOW_CAR]
PICKUP_TIME = time(10, 0)  # IST

Status = Booking.Status


def _seed_cars(count) -> dict[str, Car]:
    branch = Branch.objects.get(branch_name=BRANCH)
    cars = {}
    for index, registration in enumerate(REGISTRATIONS):
        car, created = Car.objects.get_or_create(
            registration_no=registration,
            defaults={
                "brand": "Tata",
                "model": "Tiago",
                "category": VehicleCategory.objects.get(name="Hatchback"),
                "home_branch": branch,
                "year": 2025,
                "colour": ("Orange", "Grey")[index],
                "fuel_type": FuelType.PETROL,
                "chassis_number": f"DEMOCHANGES0000{index + 1}",
                "available_from": date(2026, 1, 1),
                "odometer": 3100 + 1000 * index,
                "last_service_date": date(2026, 9, 25),
                "last_service_odometer": 3000 + 1000 * index,
                "transmission": Car.Transmission.MANUAL,
                "seating_capacity": 5,
            },
        )
        count("vehicles", created)
        if created:
            _audit("Create", car)
        _, created = VehicleDocument.objects.get_or_create(
            vehicle=car,
            document_type=VehicleDocument.DocumentType.INSURANCE,
            defaults={
                "document_number": f"DEMO-CHG-{index + 1:03d}",
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
            address="22 Demo Lane, Andheri (E), Mumbai 400069",
        )
        count("users", True)
        _audit("Create", user)
    customer, created = Customer.objects.get_or_create(
        user=user,
        defaults={
            "date_of_birth": date(1992, 7, 30),
            "emergency_contact_name": "Demo Emergency Contact",
            "emergency_contact_mobile": "+919800000095",
        },
    )
    count("customers", created)
    licence, created = Licence.objects.get_or_create(
        customer=customer,
        defaults={
            "licence_number": LICENCE_NUMBER,
            "issuing_authority": "RTO Mumbai (West)",
            "issue_date": date(2016, 8, 1),
            "expiry_date": date(2036, 7, 29),
            "status": Licence.Status.VERIFIED,
            "verified_by": User.objects.get(email=STAFF.email),
            "verified_at": timezone.make_aware(datetime(2026, 10, 9, 12, 0)),
        },
    )
    count("licences", created)
    for category in (VehicleType.CAR, VehicleType.TWO_WHEELER):
        _, created = LicenceCategory.objects.get_or_create(licence=licence, category=category)
        count("licence categories", created)
    return customer


def _confirmed(count, car: Car, customer: Customer, pickup: datetime, days: int) -> None:
    """A Confirmed booking paid by the sandbox card, unless the car is booked for the period."""
    return_ = pickup + timedelta(days=days)
    period = Booking(pickup_datetime=pickup, return_datetime=return_).compute_blocked_period()
    if car.bookings.filter(
        status__in=Booking.BLOCKING_STATUSES, blocked_period__overlap=period
    ).exists():
        return
    booking = Booking.objects.create(
        customer=customer,
        vehicle=car,
        pickup_branch=car.home_branch,
        tariff=current_tariff(car.category, timezone.now()),
        pickup_datetime=pickup,
        return_datetime=return_,
        terms_accepted_at=timezone.now(),
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
        idempotency_key=f"demo-changes-{booking.pk}",
        actor=None,
    )
    booking.booking_reference = next_in_sequence(
        Booking, "booking_reference", f"VRMS-{timezone.localdate():%Y%m%d}-", 4
    )
    booking.pickup_code = f"{246800 + booking.pk % 100:06d}"
    booking.confirmed_at = timezone.now()
    transition(
        booking,
        Status.CONFIRMED,
        actor=None,
        reason=f"Demo booking paid, transaction {auth.transaction_id} (seed_demo).",
        update_fields=("booking_reference", "pickup_code", "confirmed_at"),
    )
    count("bookings", True)


def _at(days_ahead: int) -> datetime:
    return timezone.make_aware(
        datetime.combine(timezone.localdate() + timedelta(days=days_ahead), PICKUP_TIME)
    )


def seed_demo_change_data(count: Callable[[str, bool], None]) -> None:
    """Called by seed_demo after its own data; `count(label, created)` is its counter."""
    cars = _seed_cars(count)
    customer = _seed_customer(count)
    _confirmed(count, cars[CHANGE_CAR], customer, _at(5), 2)
    _confirmed(count, cars[CHANGE_CAR], customer, _at(9), 1)
    yesterday = _at(-1)
    if not cars[NO_SHOW_CAR].bookings.filter(pickup_datetime=yesterday).exists():
        _confirmed(count, cars[NO_SHOW_CAR], customer, yesterday, 2)


def delete_demo_change_data() -> None:
    """For seed_demo --reset: remove only what seed_demo_change_data() creates.

    Raises ProtectedError, like the rest of the reset, once the demo has
    moved money or sent a notification about one of these bookings.
    """
    for car in Car.objects.filter(registration_no__in=REGISTRATIONS):
        for booking in car.bookings.all():
            RefundRequest.objects.filter(original_payment__booking=booking).delete()
            Payment.objects.filter(booking=booking, original_payment__isnull=False).delete()
            booking.payments.all().delete()
            booking.delete()
        _audit("Delete", car)
        car.delete()
    Customer.objects.filter(user__email=CUSTOMER_EMAIL).delete()  # the licence cascades
    for user in User.objects.filter(email=CUSTOMER_EMAIL):
        _audit("Delete", user)
        user.delete()
