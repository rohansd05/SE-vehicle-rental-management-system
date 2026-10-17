"""DEMO data for the payments demonstration (Module R1), loaded by seed_demo (fictitious).

- payments@vrms.test, a demo customer with a verified licence and an
  outstanding due of 850.00 (Pay.Dues), so the home screen shows the due
  and "Pay due" clears it (BR-4). Password as the other demo accounts.
- MH02DP4001, a demo hatchback at Andheri, booked by that customer for
  tomorrow 10:00 IST with cash at collection (BR-9): Pending Payment, held
  for the collection, on the demo branch staff's Cash desk.
- MH02DP4002, a demo SUV at Andheri, booked and paid by card ten days ahead
  (two days, 8260.00), with a refund of the rental above the 5000.00
  automatic approval limit waiting in the Administrator's Refunds queue
  (UC 13).

As in the handover demo, the bookings pass through the booking state
machine and the payments service with the mock gateway, all audited as
system actions (actor None), and no invoice or ledger entry is written,
because those are append-only and --reset could then never remove them.

Idempotent: the cars and the customer are created once (the due only with
the customer); a booking is added only when none of the car's bookings
blocks its period, and the refund only with its booking.
"""

from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import Customer, Licence, LicenceCategory, User
from apps.bookings.lifecycle import _choose_cash, booking_quote
from apps.bookings.models import Booking
from apps.bookings.numbering import next_in_sequence
from apps.bookings.seed import _audit
from apps.bookings.states import transition
from apps.core.choices import FuelType, VehicleType
from apps.fleet.models import Branch, Car, VehicleCategory, VehicleDocument
from apps.pricing.services import current_tariff

from . import services
from .models import Payment, RefundRequest

BRANCH = "Andheri"
CUSTOMER_EMAIL = "payments@vrms.test"
CUSTOMER_NAME = "Demo Customer (payments)"
CUSTOMER_MOBILE = "+919800000008"
LICENCE_NUMBER = "MH02 20170011223"
DEMO_DUE = Decimal("850.00")
CASH_CAR = "MH02DP4001"
REFUND_CAR = "MH02DP4002"
REGISTRATIONS = [CASH_CAR, REFUND_CAR]
PICKUP_TIME = time(10, 0)  # IST
REFUND_REASON = "Goodwill refund: a smaller vehicle was supplied (demo)."

Status = Booking.Status

# registration, chassis, model, category, colour
CARS = [
    (CASH_CAR, "DEMOPAYMENTS0001", "Grand i10 Nios", "Hatchback", "Silver"),
    (REFUND_CAR, "DEMOPAYMENTS0002", "Alcazar", "SUV", "Black"),
]


def _seed_cars(count) -> dict[str, Car]:
    branch = Branch.objects.get(branch_name=BRANCH)
    cars = {}
    for index, (registration, chassis, model, category, colour) in enumerate(CARS):
        car, created = Car.objects.get_or_create(
            registration_no=registration,
            defaults={
                "brand": "Hyundai",
                "model": model,
                "category": VehicleCategory.objects.get(name=category),
                "home_branch": branch,
                "year": 2025,
                "colour": colour,
                "fuel_type": FuelType.PETROL,
                "chassis_number": chassis,
                "available_from": date(2026, 1, 1),
                "odometer": 4100 + 1000 * index,
                "last_service_date": date(2026, 9, 20),
                "last_service_odometer": 4000 + 1000 * index,
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
                "document_number": f"DEMO-PAY-{index + 1:03d}",
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
            address="18 Demo Lane, Andheri (E), Mumbai 400069",
        )
        count("users", True)
        _audit("Create", user)
    customer, created = Customer.objects.get_or_create(
        user=user,
        defaults={
            "date_of_birth": date(1994, 2, 21),
            "emergency_contact_name": "Demo Emergency Contact",
            "emergency_contact_mobile": "+919800000096",
        },
    )
    count("customers", created)
    if created:  # Pay.Dues: left over from an earlier (fictitious) rental
        services.record_due(
            customer, DEMO_DUE, "Damage above the deposit on an earlier rental (demo)."
        )
    licence, created = Licence.objects.get_or_create(
        customer=customer,
        defaults={
            "licence_number": LICENCE_NUMBER,
            "issuing_authority": "RTO Mumbai (West)",
            "issue_date": date(2017, 3, 9),
            "expiry_date": date(2037, 2, 20),
            "status": Licence.Status.VERIFIED,
            "verified_by": User.objects.get(email=STAFF.email),
            "verified_at": timezone.make_aware(datetime(2026, 10, 9, 11, 30)),
        },
    )
    count("licences", created)
    for category in (VehicleType.CAR, VehicleType.TWO_WHEELER):
        _, created = LicenceCategory.objects.get_or_create(licence=licence, category=category)
        count("licence categories", created)
    return customer


def _held(car: Car, customer: Customer, pickup: datetime, days: int) -> Booking | None:
    """A Pending Payment booking, or None when the car is already booked for the period."""
    return_ = pickup + timedelta(days=days)
    period = Booking(pickup_datetime=pickup, return_datetime=return_).compute_blocked_period()
    if car.bookings.filter(
        status__in=Booking.BLOCKING_STATUSES, blocked_period__overlap=period
    ).exists():
        return None
    booking = Booking.objects.create(
        customer=customer,
        vehicle=car,
        pickup_branch=car.home_branch,
        tariff=current_tariff(car.category, pickup),
        pickup_datetime=pickup,
        return_datetime=return_,
        terms_accepted_at=timezone.now(),
    )
    priced = booking_quote(booking)
    booking.total_amount = priced.total_payable
    booking.security_deposit = priced.security_deposit
    booking.hold_expires_at = timezone.now() + settings.PAYMENT_HOLD_DURATION
    transition(
        booking,
        Status.PENDING_PAYMENT,
        actor=None,
        reason="Demo booking (seed_demo).",
        update_fields=("total_amount", "security_deposit", "hold_expires_at"),
    )
    return booking


def _at(day: date) -> datetime:
    return timezone.make_aware(datetime.combine(day, PICKUP_TIME))


def _seed_cash_booking(count, car: Car, customer: Customer) -> None:
    booking = _held(car, customer, _at(timezone.localdate() + timedelta(days=1)), 1)
    if booking is None:
        return
    _choose_cash(booking, actor=None, request=None)  # BR-9: held for the collection, audited
    count("bookings", True)


def _seed_refund(count, car: Car, customer: Customer) -> None:
    booking = _held(car, customer, _at(timezone.localdate() + timedelta(days=10)), 2)
    if booking is None:
        return
    auth = services.authorize(
        booking,
        rental_amount=booking.total_amount,
        deposit_amount=booking.security_deposit,
        payment_token="tok_demo",
        idempotency_key=f"demo-payments-{booking.pk}",
        actor=None,
    )
    booking.booking_reference = next_in_sequence(
        Booking, "booking_reference", f"VRMS-{timezone.localdate():%Y%m%d}-", 4
    )
    booking.pickup_code = "135790"
    booking.confirmed_at = timezone.now()
    booking.hold_expires_at = None
    transition(
        booking,
        Status.CONFIRMED,
        actor=None,
        reason=f"Demo booking paid, transaction {auth.transaction_id} (seed_demo).",
        update_fields=("booking_reference", "pickup_code", "confirmed_at", "hold_expires_at"),
    )
    count("bookings", True)
    refund = services.refund_payment(auth.rental, auth.rental.amount, REFUND_REASON, None)
    count("refunds", refund.status == RefundRequest.Status.PENDING_APPROVAL)


def seed_demo_payment_data(count: Callable[[str, bool], None]) -> None:
    """Called by seed_demo after its own data; `count(label, created)` is its counter."""
    cars = _seed_cars(count)
    customer = _seed_customer(count)
    _seed_cash_booking(count, cars[CASH_CAR], customer)
    _seed_refund(count, cars[REFUND_CAR], customer)


def delete_demo_payment_data() -> None:
    """For seed_demo --reset: remove only what seed_demo_payment_data() creates.

    Raises ProtectedError, like the rest of the reset, once the demo has
    issued a refund, recorded cash or paid a booking: their invoices and
    ledger entries are append-only.
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
