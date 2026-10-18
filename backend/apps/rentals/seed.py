"""DEMO data for the Handover Vehicle demonstration, loaded by seed_demo (fictitious).

- MH02DH3001, a demo car at Andheri with all four statutory documents of
  SA-3 (insurance, pollution and fitness certificates, road tax), so nothing
  blocks its handover.
- handover@vrms.test, a demo customer of its own with a verified licence,
  so customer@vrms.test keeps an empty history for the Book Vehicle demo.
  Password as the other demo accounts.
- A Confirmed, paid one-week booking of that car by that customer,
  collected at Andheri from five minutes before seed_demo runs, with a
  child seat to issue, so the demo branch staff can hand it over at once
  (Exp 2 use case 7). Handover is refused before the pickup time, and R2's
  no-show task marks a booking not collected two hours after its pickup
  No-show, so a pickup time fixed in the morning broke this demo whenever
  Celery Beat ran. Being a week long, the booking also keeps the car out of
  the Book Vehicle demo searches.
- Module N4 (R4 follow-up): MH02DH3002, a second demo car at Andheri, booked
  by the same customer for a week with doorstep delivery to an Andheri
  address (Book.Deliver.Location), collected from 24 hours and 10 minutes
  after seed_demo runs. It is in the branch's upcoming collections with its
  delivery address, and Celery Beat sends its pickup reminder (Notify.Remind,
  template version 2, naming the address) about ten minutes later.

The booking moves through the booking state machine (Draft, Pending
Payment, Confirmed) and its deposit is authorised through the payments
service with the mock gateway, all audited as system actions (actor None).
No invoice is issued, because invoices are append-only and --reset could
then never remove the booking.

Idempotent: the car, its documents and the customer are created once; a booking is added
only when none of the car's bookings blocks the new period, so a second run
changes nothing while the last booking still holds the car, and a later run
adds a new one once it is over, cancelled or a no-show.
"""

from collections.abc import Callable
from datetime import date, datetime, timedelta

from django.utils import timezone

from apps.accounts.models import Customer, Licence, LicenceCategory, User
from apps.bookings.lifecycle import booking_quote
from apps.bookings.models import Booking, BookingAddOn
from apps.bookings.numbering import next_in_sequence
from apps.bookings.states import transition
from apps.core.audit import entity_type, snapshot
from apps.core.choices import FuelType, VehicleType
from apps.core.models import AuditLog
from apps.fleet.models import Branch, Car, VehicleCategory, VehicleDocument
from apps.payments import services as payments
from apps.pricing.models import AddOn
from apps.pricing.services import current_tariff

BRANCH = "Andheri"
CUSTOMER_EMAIL = "handover@vrms.test"
CUSTOMER_NAME = "Demo Customer (handover)"
CUSTOMER_MOBILE = "+919800000007"
LICENCE_NUMBER = "MH02 20160067890"
VERIFIED_AT = datetime(2026, 10, 9, 11, 30, tzinfo=timezone.get_fixed_timezone(330))
REGISTRATION = "MH02DH3001"
PICKUP_LEAD = timedelta(minutes=5)  # the pickup is this long before seed_demo runs
RENTAL_DAYS = 7
DOCUMENTS_VALID_TO = date(2027, 12, 31)
PICKUP_CODE = "246810"  # fixed, so the demo can find the booking by its pickup code
DELIVERY_REGISTRATION = "MH02DH3002"
DELIVERY_PICKUP_LEAD = timedelta(hours=24, minutes=10)  # after seed_demo runs: reminded soon
DELIVERY_RENTAL_DAYS = 7  # like the handover car: kept out of the Book Vehicle demo searches
DELIVERY_PICKUP_CODE = "975310"
DELIVERY_ADDRESS = "21 Demo Lane, Andheri (W), Mumbai"
DELIVERY_PINCODE = "400053"  # in Andheri's serviceable areas (seed_demo BRANCHES)

Status = Booking.Status


def _audit(action: str, obj) -> None:
    before, after = (snapshot(obj), None) if action == "Delete" else (None, snapshot(obj))
    AuditLog.objects.record(
        actor=None,
        action=action,
        entity_type=entity_type(obj),
        entity_id=obj.pk,
        before=before,
        after=after,
    )


def _seed_car(
    count: Callable[[str, bool], None], registration: str = REGISTRATION, chassis: str = "0001"
) -> Car:
    car, created = Car.objects.get_or_create(
        registration_no=registration,
        defaults={
            "brand": "Tata",
            "model": "Altroz",
            "category": VehicleCategory.objects.get(name="Hatchback"),
            "home_branch": Branch.objects.get(branch_name=BRANCH),
            "year": 2025,
            "colour": "Gold",
            "fuel_type": FuelType.PETROL,
            "chassis_number": f"DEMOHANDOVER{chassis}",
            "available_from": date(2026, 1, 1),
            "odometer": 8200,
            "last_service_date": date(2026, 9, 15),
            "last_service_odometer": 8000,
            "transmission": Car.Transmission.MANUAL,
            "seating_capacity": 5,
        },
    )
    count("vehicles", created)
    if created:
        _audit("Create", car)
    for index, document_type in enumerate(VehicleDocument.DocumentType.values):
        _, created = VehicleDocument.objects.get_or_create(
            vehicle=car,
            document_type=document_type,
            defaults={
                "document_number": f"DEMO-HO-{index + 1:03d}",
                "valid_from": date(2026, 1, 1),
                "expiry_date": DOCUMENTS_VALID_TO,
            },
        )
        count("vehicle documents", created)
    return car


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
            address="16 Demo Lane, Andheri (E), Mumbai 400069",
        )
        count("users", True)
        _audit("Create", user)
    customer, created = Customer.objects.get_or_create(
        user=user,
        defaults={
            "date_of_birth": date(1992, 8, 3),
            "emergency_contact_name": "Demo Emergency Contact",
            "emergency_contact_mobile": "+919800000097",
        },
    )
    count("customers", created)
    licence, created = Licence.objects.get_or_create(
        customer=customer,
        defaults={
            "licence_number": LICENCE_NUMBER,
            "issuing_authority": "RTO Mumbai (West)",
            "issue_date": date(2016, 1, 11),
            "expiry_date": date(2036, 8, 2),
            "status": Licence.Status.VERIFIED,
            "verified_by": User.objects.get(email=STAFF.email),
            "verified_at": VERIFIED_AT,
        },
    )
    count("licences", created)
    _, created = LicenceCategory.objects.get_or_create(licence=licence, category=VehicleType.CAR)
    count("licence categories", created)
    return customer


def _seed_booking(
    count: Callable[[str, bool], None],
    car: Car,
    customer: Customer,
    *,
    lead: timedelta = -PICKUP_LEAD,
    days: int = RENTAL_DAYS,
    add_on: str = "Child seat",
    pickup_code: str = PICKUP_CODE,
    delivery: tuple[str, str] = ("", ""),
) -> None:
    today = timezone.localdate()
    pickup = timezone.now().replace(second=0, microsecond=0) + lead
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
        tariff=current_tariff(car.category, pickup),
        pickup_datetime=pickup,
        return_datetime=return_,
        terms_accepted_at=timezone.now(),
        delivery_address=delivery[0],
        delivery_pincode=delivery[1],
    )
    extra = AddOn.objects.get(name=add_on)
    BookingAddOn.objects.create(booking=booking, add_on=extra, daily_rate=extra.daily_rate)
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
        idempotency_key=f"demo-handover-{booking.pk}",
        actor=None,
    )
    booking.booking_reference = next_in_sequence(
        Booking, "booking_reference", f"VRMS-{today:%Y%m%d}-", 4
    )
    booking.pickup_code = pickup_code
    booking.confirmed_at = timezone.now()
    transition(
        booking,
        Status.CONFIRMED,
        actor=None,
        reason=f"Demo booking paid, transaction {auth.transaction_id} (seed_demo).",
        update_fields=("booking_reference", "pickup_code", "confirmed_at"),
    )
    count("bookings", True)


def seed_demo_handover_data(count: Callable[[str, bool], None]) -> None:
    """Called by seed_demo after its own data; `count(label, created)` is its counter."""
    customer = _seed_customer(count)
    _seed_booking(count, _seed_car(count), customer)
    _seed_booking(
        count,
        _seed_car(count, DELIVERY_REGISTRATION, "0002"),
        customer,
        lead=DELIVERY_PICKUP_LEAD,
        days=DELIVERY_RENTAL_DAYS,
        add_on="Doorstep delivery",
        pickup_code=DELIVERY_PICKUP_CODE,
        delivery=(DELIVERY_ADDRESS, DELIVERY_PINCODE),
    )


def delete_demo_handover_data() -> None:
    """For seed_demo --reset: remove only what seed_demo_handover_data() creates.

    Raises ProtectedError, like the rest of the reset, once a booking has a
    signed condition report (Handover.Sign: it can never be removed).
    """
    for car in Car.objects.filter(registration_no__in=(REGISTRATION, DELIVERY_REGISTRATION)):
        for booking in car.bookings.all():
            booking.payments.all().delete()
            booking.delete()
        _audit("Delete", car)
        car.delete()
    Customer.objects.filter(user__email=CUSTOMER_EMAIL).delete()  # the licence cascades
    for user in User.objects.filter(email=CUSTOMER_EMAIL):
        _audit("Delete", user)
        user.delete()
