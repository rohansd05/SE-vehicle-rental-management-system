"""DEMO data for the Exp 8 / Exp 10 Booking scenarios, loaded by seed_booking_scenarios.

Run after `seed_demo` (and `seed_demo --reports`). All fictitious, password as
the other demo accounts, each customer with a verified licence for Car and
Two-Wheeler valid to 2036:

- refunds@vrms.test (BR-8, Exp 10 TC-B1 to TC-B3): MH02DX8001 to MH02DX8003,
  three demo hatchbacks at Andheri, each with one Confirmed one-day booking
  paid by the sandbox card, collected 72, 30 and 6 hours after the seed
  (rounded up to the next 15 minutes). Cancelling them quotes 100%, 75% and
  50% of the rental, and the whole deposit, while the notice stays in its slab.
- young@vrms.test (BR-2, Exp 10 TC-B5): 20 at the seed, 21 seven days later,
  so a car collected before that birthday is refused (under_age); a
  two-wheeler, or a car collected on or after it, is allowed.
- lockout@vrms.test (Exp 8 R7, SE-8): a plain customer for the five failed
  sign-ins, so no other demo account is locked.

Bookings go through seed_changes._confirmed() (state machine, mock gateway,
audited as system actions); every creation is audited with actor None.
Idempotent: accounts and cars are created once, and a booking only while its
car has none blocking the period.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from django.utils import timezone

from apps.accounts.models import Customer, Licence, LicenceCategory, User
from apps.core.choices import FuelType, VehicleType
from apps.core.management.commands.seed_demo import DEMO_PASSWORD, STAFF, demo_fuel_capacity
from apps.fleet.models import Branch, Car, VehicleCategory, VehicleDocument
from apps.fleet.seed import seed_demo_photos

from .seed import _audit
from .seed_changes import _confirmed

BRANCH = "Andheri"
REFUNDS_EMAIL = "refunds@vrms.test"
YOUNG_EMAIL = "young@vrms.test"
LOCKOUT_EMAIL = "lockout@vrms.test"
EMAILS = [REFUNDS_EMAIL, YOUNG_EMAIL, LOCKOUT_EMAIL]
REGISTRATIONS = ["MH02DX8001", "MH02DX8002", "MH02DX8003"]
NOTICE_HOURS = [72, 30, 6]  # BR-8 slabs: at least 48 h, at least 12 h, under 12 h
YOUNG_BIRTHDAY_IN = timedelta(days=7)
LICENCE_EXPIRY = date(2036, 6, 30)
STEP = timedelta(minutes=15)

Count = Callable[[str, bool], None]


def _seed_cars(count: Count) -> list[Car]:
    branch = Branch.objects.get(branch_name=BRANCH)
    category = VehicleCategory.objects.get(name="Hatchback")
    cars = []
    for index, registration in enumerate(REGISTRATIONS):
        car, created = Car.objects.get_or_create(
            registration_no=registration,
            defaults={
                "brand": "Maruti Suzuki",
                "model": "Wagon R",
                "category": category,
                "home_branch": branch,
                "year": 2025,
                "colour": ("White", "Silver", "Blue")[index],
                "fuel_type": FuelType.PETROL,
                "fuel_capacity": demo_fuel_capacity(category.name, FuelType.PETROL),
                "chassis_number": f"DEMOSCENARIO000{index + 1}",
                "available_from": date(2026, 1, 1),
                "odometer": 2100 + 1000 * index,
                "last_service_date": date(2026, 9, 25),
                "last_service_odometer": 2000 + 1000 * index,
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
                "document_number": f"DEMO-SCN-{index + 1:03d}",
                "valid_from": date(2026, 1, 1),
                "expiry_date": date(2027, 12, 31),
            },
        )
        count("vehicle documents", created)
        cars.append(car)
    return cars


def _seed_customer(
    count: Count, email: str, name: str, index: int, born: date, licence_issued: date
) -> Customer:
    user = User.objects.filter(email=email).first()
    if user is None:
        user = User.objects.create_user(
            email=email,
            password=DEMO_PASSWORD,
            name=name,
            mobile_no=f"+9198000000{21 + index}",
            role=User.Role.CUSTOMER,
            address=f"{31 + index} Demo Lane, Andheri (E), Mumbai 400069",
        )
        count("users", True)
        _audit("Create", user)
    customer, created = Customer.objects.get_or_create(
        user=user,
        defaults={
            "date_of_birth": born,
            "emergency_contact_name": "Demo Emergency Contact",
            "emergency_contact_mobile": f"+9198000000{81 + index}",
        },
    )
    count("customers", created)
    licence, created = Licence.objects.get_or_create(
        customer=customer,
        defaults={
            "licence_number": f"MH02 {licence_issued.year}007100{index + 1}",
            "issuing_authority": "RTO Mumbai (West)",
            "issue_date": licence_issued,
            "expiry_date": LICENCE_EXPIRY,
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


def _twenty_one_years_before(day: date) -> date:
    if (day.month, day.day) == (2, 29):  # 21 years earlier is never a leap year
        return date(day.year - 21, 3, 1)
    return day.replace(year=day.year - 21)


def pickup_in(hours: int) -> datetime:
    """Now plus `hours`, rounded up to the next 15 minutes."""
    at = timezone.now() + timedelta(hours=hours)
    return at + (datetime(2000, 1, 1, tzinfo=UTC) - at) % STEP


def seed_booking_scenarios(count: Count) -> None:
    """`count(label, created)` counts what is created, as in seed_demo."""
    birthday = timezone.localdate() + YOUNG_BIRTHDAY_IN
    refunds = _seed_customer(
        count, REFUNDS_EMAIL, "Demo Customer (refunds)", 0, date(1993, 3, 14), date(2012, 5, 2)
    )
    _seed_customer(
        count,
        YOUNG_EMAIL,
        "Demo Customer (under 21)",
        1,
        _twenty_one_years_before(birthday),
        date(2025, 11, 3),
    )
    _seed_customer(
        count, LOCKOUT_EMAIL, "Demo Customer (lockout)", 2, date(1990, 9, 8), date(2010, 1, 11)
    )
    for car, hours in zip(_seed_cars(count), NOTICE_HOURS, strict=True):
        _confirmed(count, car, refunds, pickup_in(hours), 1)
    seed_demo_photos(count)  # the four catalogue photos of the new cars
