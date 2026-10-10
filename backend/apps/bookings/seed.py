"""DEMO data for the Book Vehicle demonstration, loaded by seed_demo (fictitious).

- Four more vehicles at Andheri, all Available, so the demo customer and the
  demo branch staff (both Andheri) have something to search and book: the
  maintenance demo jobs (apps/maintenance/seed.py) take three of the four
  original Andheri vehicles out of service. One car and one two-wheeler of
  each kind: Hatchback, SUV, Scooter, Motorcycle (the seed_demo categories,
  with their tariffs).
- pending@vrms.test, a second demo customer whose licence is Pending
  Verification, to show the "licence not verified" alternative flow of Exp 4
  sequence 1 (Book.Eligible.No). Password as the other demo accounts.

Idempotent: a vehicle or account is created only if its registration number
or e-mail address is new, so a second run changes nothing and never touches
the maintenance demo data. Every creation is audited as a system action
(actor None), like the rest of seed_demo, so --reset can remove it again.
"""

from collections.abc import Callable
from datetime import date

from apps.accounts.models import Customer, Licence, LicenceCategory, User
from apps.core.audit import entity_type, snapshot
from apps.core.choices import FuelType, VehicleType
from apps.core.models import AuditLog
from apps.fleet.models import Branch, Car, TwoWheeler, Vehicle, VehicleCategory, VehicleDocument

BRANCH = "Andheri"
# (registration, chassis, brand, model, category, fuel, transmission or engine cc, seats, colour)
DEMO_CARS = [
    (
        "MH02DB2001",
        "DEMOBOOKING00001",
        "Maruti Suzuki",
        "Baleno",
        "Hatchback",
        FuelType.PETROL,
        "Manual",
        5,
        "Blue",
    ),
    (
        "MH02DB2002",
        "DEMOBOOKING00002",
        "Hyundai",
        "Venue",
        "SUV",
        FuelType.PETROL,
        "Automatic",
        5,
        "White",
    ),
]
DEMO_TWO_WHEELERS = [
    (
        "MH02DB2003",
        "DEMOBOOKING00003",
        "Honda",
        "Dio",
        "Scooter",
        FuelType.PETROL,
        110,
        None,
        "Red",
    ),
    (
        "MH02DB2004",
        "DEMOBOOKING00004",
        "Bajaj",
        "Platina 110",
        "Motorcycle",
        FuelType.PETROL,
        115,
        None,
        "Black",
    ),
]
DEMO_REGISTRATIONS = [spec[0] for spec in DEMO_CARS + DEMO_TWO_WHEELERS]

PENDING_EMAIL = "pending@vrms.test"
PENDING_NAME = "Demo Customer (licence pending)"
PENDING_MOBILE = "+919800000006"
PENDING_LICENCE = "MH02 20180054321"


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


def _seed_vehicles(count: Callable[[str, bool], None]) -> None:
    branch = Branch.objects.get(branch_name=BRANCH)
    specs = [(Car, spec) for spec in DEMO_CARS] + [(TwoWheeler, spec) for spec in DEMO_TWO_WHEELERS]
    for index, (model_class, spec) in enumerate(specs):
        registration, chassis, brand, model, category, fuel, detail, seats, colour = spec
        defaults = {
            "brand": brand,
            "model": model,
            "category": VehicleCategory.objects.get(name=category),
            "home_branch": branch,
            "year": 2025,
            "colour": colour,
            "fuel_type": fuel,
            "chassis_number": chassis,
            "available_from": date(2026, 1, 1),
            "odometer": 2500 + 1000 * index,
            "last_service_date": date(2026, 9, 1),
            "last_service_odometer": 2000 + 1000 * index,
        }
        if model_class is Car:
            defaults.update(transmission=detail, seating_capacity=seats)
        else:
            defaults.update(engine_cc=detail)
        vehicle, created = model_class.objects.get_or_create(
            registration_no=registration, defaults=defaults
        )
        count("vehicles", created)
        if created:
            _audit("Create", vehicle)
        _, created = VehicleDocument.objects.get_or_create(
            vehicle=vehicle,
            document_type=VehicleDocument.DocumentType.INSURANCE,
            defaults={
                "document_number": f"DEMO-POL-B{index + 1:04d}",
                "valid_from": date(2026, 1, 1),
                "expiry_date": date(2026, 12, 31),
            },
        )
        count("vehicle documents", created)


def _seed_pending_customer(count: Callable[[str, bool], None], password: str) -> None:
    user = User.objects.filter(email=PENDING_EMAIL).first()
    if user is None:
        user = User.objects.create_user(
            email=PENDING_EMAIL,
            password=password,
            name=PENDING_NAME,
            mobile_no=PENDING_MOBILE,
            role=User.Role.CUSTOMER,
            address="14 Demo Lane, Andheri (E), Mumbai 400069",
        )
        count("users", True)
        _audit("Create", user)
    customer, created = Customer.objects.get_or_create(
        user=user,
        defaults={
            "date_of_birth": date(1998, 3, 14),
            "emergency_contact_name": "Demo Emergency Contact",
            "emergency_contact_mobile": "+919800000098",
        },
    )
    count("customers", created)
    licence, created = Licence.objects.get_or_create(
        customer=customer,
        defaults={
            "licence_number": PENDING_LICENCE,
            "issuing_authority": "RTO Mumbai (West)",
            "issue_date": date(2018, 4, 2),
            "expiry_date": date(2038, 3, 13),
            "status": Licence.Status.PENDING_VERIFICATION,
        },
    )
    count("licences", created)
    for category in (VehicleType.CAR, VehicleType.TWO_WHEELER):
        _, created = LicenceCategory.objects.get_or_create(licence=licence, category=category)
        count("licence categories", created)


def seed_demo_booking_data(count: Callable[[str, bool], None]) -> None:
    """Called by seed_demo after its own data; `count(label, created)` is its counter."""
    from apps.core.management.commands.seed_demo import DEMO_PASSWORD

    _seed_vehicles(count)
    _seed_pending_customer(count, DEMO_PASSWORD)


def delete_demo_booking_data() -> None:
    """For seed_demo --reset: remove only what seed_demo_booking_data() creates.

    Raises ProtectedError, like the rest of the reset, if a demo booking or
    payment still refers to these vehicles or this customer.
    """
    for vehicle in Vehicle.objects.filter(registration_no__in=DEMO_REGISTRATIONS):
        _audit("Delete", vehicle)
        vehicle.delete()
    Customer.objects.filter(user__email=PENDING_EMAIL).delete()  # the licence cascades
    for user in User.objects.filter(email=PENDING_EMAIL):
        _audit("Delete", user)
        user.delete()
