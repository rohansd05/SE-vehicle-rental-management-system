"""Load DEMO data for development and the project demonstration.

Everything created here is fictitious demo data: names, rates, prices,
registration numbers and documents are illustrative, not real records and
not business rules. The security deposits come from the BR-3 settings.
Running the command again changes nothing (idempotent); --reset removes the
demo data first and loads it again.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import ProtectedError

from apps.accounts.models import (
    Administrator,
    BranchManager,
    BranchStaff,
    Customer,
    Licence,
    LicenceCategory,
    MaintenanceTechnician,
    User,
)
from apps.core.audit import entity_type, snapshot
from apps.core.choices import FuelType, VehicleType
from apps.core.models import AuditLog
from apps.fleet.models import (
    Branch,
    BranchServiceableArea,
    Car,
    TwoWheeler,
    Vehicle,
    VehicleCategory,
    VehicleDocument,
)
from apps.pricing.models import AddOn, DiscountCode, FuelPrice, Tariff

DEMO_PASSWORD = "Demo@1234"
IST = ZoneInfo("Asia/Kolkata")
DEMO_EFFECTIVE_FROM = datetime(2026, 1, 1, tzinfo=IST)

BRANCHES = {
    "Andheri": (
        "Ground floor, Link Road, Andheri (W), Mumbai 400053",
        [("400053", "Andheri West"), ("400058", "Andheri West"), ("400061", "Versova")],
    ),
    "Bandra": (
        "Hill Road, Bandra (W), Mumbai 400050",
        [("400050", "Bandra West"), ("400051", "Bandra East")],
    ),
    "Powai": (
        "Hiranandani Gardens, Powai, Mumbai 400076",
        [("400076", "Powai"), ("400072", "Saki Naka")],
    ),
    "Thane": (
        "Ghodbunder Road, Thane (W) 400601",
        [("400601", "Thane West"), ("400602", "Thane West"), ("400604", "Wagle Estate")],
    ),
    "Vashi": (
        "Sector 17, Vashi, Navi Mumbai 400703",
        [("400703", "Vashi"), ("400705", "Sanpada")],
    ),
}
BRANCH_RTO = {
    "Andheri": "MH02",
    "Bandra": "MH02",
    "Powai": "MH03",
    "Thane": "MH04",
    "Vashi": "MH43",
}

# name: (vehicle type, hourly, daily, weekly, free km per day, excess km rate)
CATEGORIES = {
    "Hatchback": (VehicleType.CAR, "150", "1800", "11000", 250, "10"),
    "Sedan": (VehicleType.CAR, "200", "2400", "15000", 250, "12"),
    "SUV": (VehicleType.CAR, "300", "3500", "22000", 300, "15"),
    "Scooter": (VehicleType.TWO_WHEELER, "60", "600", "3600", 120, "4"),
    "Motorcycle": (VehicleType.TWO_WHEELER, "80", "800", "4800", 150, "5"),
}

# Book.Addons: helmet, child seat, luggage carrier, named driver, doorstep delivery.
ADD_ONS = [
    ("Additional helmet", "50", VehicleType.TWO_WHEELER),
    ("Child seat", "150", VehicleType.CAR),
    ("Luggage carrier", "100", ""),
    ("Additional named driver", "200", VehicleType.CAR),
    ("Doorstep delivery", "300", ""),
]

# D17: one percent and one fixed demo code (code, type, value).
DISCOUNT_CODES = [
    ("WELCOME10", DiscountCode.DiscountType.PERCENT, "10.00"),
    ("FLAT500", DiscountCode.DiscountType.FIXED, "500.00"),
]
DEMO_DISCOUNT_VALID_TO = datetime(2026, 12, 31, 23, 59, tzinfo=IST)

FUEL_PRICES = {
    FuelType.PETROL: "104.21",
    FuelType.DIESEL: "92.15",
    FuelType.CNG: "77.00",
    FuelType.ELECTRIC: "12.00",
}

# (brand, model, category, fuel, transmission, seats, colour)
CARS = [
    ("Maruti Suzuki", "Swift", "Hatchback", FuelType.PETROL, "Manual", 5, "Red"),
    ("Hyundai", "i20", "Hatchback", FuelType.PETROL, "Manual", 5, "White"),
    ("Tata", "Tiago EV", "Hatchback", FuelType.ELECTRIC, "Automatic", 5, "Teal"),
    ("Honda", "City", "Sedan", FuelType.PETROL, "Automatic", 5, "Silver"),
    ("Hyundai", "Verna", "Sedan", FuelType.PETROL, "Manual", 5, "Grey"),
    ("Maruti Suzuki", "Dzire", "Sedan", FuelType.CNG, "Manual", 5, "White"),
    ("Mahindra", "XUV700", "SUV", FuelType.DIESEL, "Automatic", 7, "Black"),
    ("Tata", "Nexon", "SUV", FuelType.PETROL, "Manual", 5, "Blue"),
    ("Hyundai", "Creta", "SUV", FuelType.DIESEL, "Automatic", 5, "White"),
    ("Kia", "Seltos", "SUV", FuelType.PETROL, "Automatic", 5, "Red"),
    ("Toyota", "Innova Crysta", "SUV", FuelType.DIESEL, "Manual", 7, "Silver"),
    ("Mahindra", "Thar", "SUV", FuelType.DIESEL, "Manual", 4, "Green"),
]
# (brand, model, category, engine cc, colour)
TWO_WHEELERS = [
    ("Honda", "Activa 6G", "Scooter", 110, "Grey"),
    ("TVS", "Jupiter", "Scooter", 110, "Blue"),
    ("Suzuki", "Access 125", "Scooter", 125, "White"),
    ("TVS", "Ntorq 125", "Scooter", 124, "Red"),
    ("Royal Enfield", "Classic 350", "Motorcycle", 349, "Black"),
    ("Bajaj", "Pulsar 150", "Motorcycle", 149, "Blue"),
    ("Honda", "Shine", "Motorcycle", 124, "Black"),
    ("Yamaha", "FZ-S", "Motorcycle", 149, "Grey"),
]


@dataclass(frozen=True)
class DemoAccount:
    email: str
    name: str
    mobile_no: str
    role: str


ADMIN = DemoAccount(
    "admin@vrms.test", "Demo Administrator", "+919800000004", User.Role.ADMINISTRATOR
)
CUSTOMER = DemoAccount("customer@vrms.test", "Demo Customer", "+919800000001", User.Role.CUSTOMER)
STAFF = DemoAccount("staff@vrms.test", "Demo Branch Staff", "+919800000002", User.Role.BRANCH_STAFF)
TECH = DemoAccount(
    "tech@vrms.test", "Demo Technician", "+919800000003", User.Role.MAINTENANCE_TECHNICIAN
)
MANAGER = DemoAccount(
    "manager@vrms.test", "Demo Branch Manager", "+919800000005", User.Role.BRANCH_MANAGER
)
DEMO_ACCOUNTS = [ADMIN, CUSTOMER, STAFF, TECH, MANAGER]


def demo_registrations() -> list[str]:
    branch_names = list(BRANCHES)
    registrations = []
    for index in range(len(CARS) + len(TWO_WHEELERS)):
        branch = branch_names[index % len(branch_names)]
        registrations.append(f"{BRANCH_RTO[branch]}DM{1001 + index}")
    return registrations


class Command(BaseCommand):
    help = (
        "Load DEMO data (fictitious, for development and demonstration only): 5 Mumbai-area "
        "branches, vehicle categories with current tariffs, add-ons, 2 discount codes, fuel "
        "prices, 20 vehicles "
        "with a document each, and the README demo accounts (password Demo@1234). "
        "Idempotent; --reset removes the demo data and loads it again."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete the demo data first (only data this command creates), then reload it.",
        )

    def handle(self, *args, **options):
        self.created: dict[str, int] = {}
        with transaction.atomic():
            if options["reset"]:
                self._reset()
            self._seed()
        created = ", ".join(f"{n} {label}" for label, n in self.created.items()) or "nothing"
        self.stdout.write(self.style.SUCCESS(f"Demo data ready. Created: {created}."))
        self.stdout.write(f"Demo accounts use the password {DEMO_PASSWORD}: ")
        self.stdout.write("  " + ", ".join(account.email for account in DEMO_ACCOUNTS))

    # ─── Seeding ──────────────────────────────────────────────────────────

    def _count(self, label: str, created: bool) -> None:
        if created:
            self.created[label] = self.created.get(label, 0) + 1

    def _audit_create(self, obj) -> None:
        """Fleet.Audit: demo vehicles, tariffs, branches and users are audited too."""
        AuditLog.objects.record(
            actor=None,
            action="Create",
            entity_type=entity_type(obj),
            entity_id=obj.pk,
            after=snapshot(obj),
        )

    def _seed(self) -> None:
        branches = self._seed_branches()
        users = self._seed_accounts(branches)
        administrator = users[ADMIN.email].administrator
        categories = self._seed_categories_and_tariffs(administrator)
        self._seed_add_ons()
        self._seed_discount_codes()
        self._seed_fuel_prices(administrator)
        self._seed_vehicles(branches, categories)

    def _seed_branches(self) -> dict[str, Branch]:
        branches = {}
        for name, (address, areas) in BRANCHES.items():
            branch, created = Branch.objects.get_or_create(
                branch_name=name, defaults={"address": address}
            )
            self._count("branches", created)
            if created:
                self._audit_create(branch)
            for pincode, locality in areas:
                _, area_created = BranchServiceableArea.objects.get_or_create(
                    branch=branch, pincode=pincode, locality=locality
                )
                self._count("serviceable areas", area_created)
            branches[name] = branch
        return branches

    def _user(self, account: DemoAccount, **extra) -> User:
        user = User.objects.filter(email=account.email).first()
        if user is None:
            user = User.objects.create_user(
                email=account.email,
                password=DEMO_PASSWORD,
                name=account.name,
                mobile_no=account.mobile_no,
                role=account.role,
                **extra,
            )
            self._count("users", True)
            self._audit_create(user)
        return user

    def _seed_accounts(self, branches: dict[str, Branch]) -> dict[str, User]:
        admin_user = self._user(ADMIN, is_staff=True, is_superuser=True)
        _, created = Administrator.objects.get_or_create(user=admin_user)
        self._count("administrators", created)

        customer_user = self._user(CUSTOMER, address="12 Demo Lane, Andheri (E), Mumbai 400069")
        customer, created = Customer.objects.get_or_create(
            user=customer_user,
            defaults={
                "date_of_birth": date(1995, 5, 20),
                "emergency_contact_name": "Demo Emergency Contact",
                "emergency_contact_mobile": "+919800000099",
            },
        )
        self._count("customers", created)
        licence, created = Licence.objects.get_or_create(
            customer=customer,
            defaults={
                "licence_number": "MH02 20150012345",
                "issuing_authority": "RTO Mumbai (West)",
                "issue_date": date(2015, 6, 1),
                "expiry_date": date(2035, 5, 19),
                "status": Licence.Status.VERIFIED,
                "verified_by": admin_user,
            },
        )
        self._count("licences", created)
        for category in (VehicleType.CAR, VehicleType.TWO_WHEELER):
            _, created = LicenceCategory.objects.get_or_create(licence=licence, category=category)
            self._count("licence categories", created)

        staff_user = self._user(STAFF)
        _, created = BranchStaff.objects.get_or_create(
            user=staff_user, defaults={"branch": branches["Andheri"]}
        )
        self._count("branch staff", created)

        tech_user = self._user(TECH)
        _, created = MaintenanceTechnician.objects.get_or_create(
            user=tech_user, defaults={"workshop": "Agency workshop, Andheri"}
        )
        self._count("technicians", created)

        manager_user = self._user(MANAGER)
        _, created = BranchManager.objects.get_or_create(
            user=manager_user, defaults={"branch": branches["Andheri"]}
        )
        self._count("branch managers", created)

        return {account.email: User.objects.get(email=account.email) for account in DEMO_ACCOUNTS}

    def _seed_categories_and_tariffs(self, administrator) -> dict[str, VehicleCategory]:
        categories = {}
        for name, (vehicle_type, hourly, daily, weekly, free_km, excess) in CATEGORIES.items():
            category, created = VehicleCategory.objects.get_or_create(
                name=name, defaults={"vehicle_type": vehicle_type}
            )
            self._count("vehicle categories", created)
            deposit = (
                settings.SECURITY_DEPOSIT_CAR
                if vehicle_type == VehicleType.CAR
                else settings.SECURITY_DEPOSIT_TWO_WHEELER
            )
            tariff, created = Tariff.objects.get_or_create(
                vehicle_category=category,
                effective_from=DEMO_EFFECTIVE_FROM,
                defaults={
                    "hourly_rate": Decimal(hourly),
                    "daily_rate": Decimal(daily),
                    "weekly_rate": Decimal(weekly),
                    "security_deposit": deposit,
                    "free_km_allowance": free_km,
                    "excess_km_rate": Decimal(excess),
                    "defined_by": administrator,
                },
            )
            self._count("tariffs", created)
            if created:
                self._audit_create(tariff)
            categories[name] = category
        return categories

    def _seed_add_ons(self) -> None:
        for name, rate, vehicle_type in ADD_ONS:
            _, created = AddOn.objects.get_or_create(
                name=name, defaults={"daily_rate": Decimal(rate), "vehicle_type": vehicle_type}
            )
            self._count("add-ons", created)

    def _seed_discount_codes(self) -> None:
        for code, discount_type, value in DISCOUNT_CODES:
            _, created = DiscountCode.objects.get_or_create(
                code=code,
                defaults={
                    "discount_type": discount_type,
                    "value": Decimal(value),
                    "valid_from": DEMO_EFFECTIVE_FROM,
                    "valid_to": DEMO_DISCOUNT_VALID_TO,
                },
            )
            self._count("discount codes", created)

    def _seed_fuel_prices(self, administrator) -> None:
        for fuel_type, price in FUEL_PRICES.items():
            _, created = FuelPrice.objects.get_or_create(
                fuel_type=fuel_type,
                effective_from=DEMO_EFFECTIVE_FROM,
                defaults={"price_per_unit": Decimal(price), "defined_by": administrator},
            )
            self._count("fuel prices", created)

    def _seed_vehicles(self, branches, categories) -> None:
        branch_names = list(branches)
        registrations = demo_registrations()
        today = date.today()
        specs = [("car", spec) for spec in CARS] + [("two-wheeler", spec) for spec in TWO_WHEELERS]
        for index, (kind, spec) in enumerate(specs):
            registration = registrations[index]
            common = {
                "home_branch": branches[branch_names[index % len(branch_names)]],
                "year": 2022 + index % 4,
                "chassis_number": f"DEMOCHASSIS{index + 1:06d}",
                "available_from": date(2026, 1, 1),
                "odometer": 4000 + 1500 * index,
                "last_service_date": today - timedelta(days=30 + 7 * index),
                "last_service_odometer": 3000 + 1500 * index,
            }
            if kind == "car":
                brand, model, category, fuel, transmission, seats, colour = spec
                vehicle, created = Car.objects.get_or_create(
                    registration_no=registration,
                    defaults={
                        **common,
                        "brand": brand,
                        "model": model,
                        "category": categories[category],
                        "fuel_type": fuel,
                        "colour": colour,
                        "transmission": transmission,
                        "seating_capacity": seats,
                    },
                )
            else:
                brand, model, category, engine_cc, colour = spec
                vehicle, created = TwoWheeler.objects.get_or_create(
                    registration_no=registration,
                    defaults={
                        **common,
                        "brand": brand,
                        "model": model,
                        "category": categories[category],
                        "fuel_type": FuelType.PETROL,
                        "colour": colour,
                        "engine_cc": engine_cc,
                    },
                )
            self._count("vehicles", created)
            if created:
                self._audit_create(vehicle)
            _, created = VehicleDocument.objects.get_or_create(
                vehicle=vehicle,
                document_type=VehicleDocument.DocumentType.INSURANCE,
                defaults={
                    "document_number": f"DEMO-POL-{index + 1:05d}",
                    "valid_from": date(2026, 1, 1),
                    "expiry_date": date(2026, 12, 31),
                },
            )
            self._count("vehicle documents", created)

    # ─── Reset ────────────────────────────────────────────────────────────

    def _audit_delete(self, obj) -> None:
        AuditLog.objects.record(
            actor=None,
            action="Delete",
            entity_type=entity_type(obj),
            entity_id=obj.pk,
            before=snapshot(obj),
        )

    def _delete_audited(self, queryset) -> None:
        for obj in queryset:
            self._audit_delete(obj)
        queryset.delete()

    def _reset(self) -> None:
        """Remove only what _seed() creates. Other data is never touched."""
        demo_emails = [account.email for account in DEMO_ACCOUNTS]
        try:
            self._delete_audited(Tariff.objects.filter(vehicle_category__name__in=CATEGORIES))
            FuelPrice.objects.filter(effective_from=DEMO_EFFECTIVE_FROM).delete()
            self._delete_audited(Vehicle.objects.filter(registration_no__in=demo_registrations()))
            # The licence (deleted with its customer) protects the admin who verified it.
            Customer.objects.filter(user__email__in=demo_emails).delete()
            self._delete_audited(User.objects.filter(email__in=demo_emails))
            AddOn.objects.filter(name__in=[name for name, _, _ in ADD_ONS]).delete()
            DiscountCode.objects.filter(code__in=[code for code, _, _ in DISCOUNT_CODES]).delete()
            VehicleCategory.objects.filter(name__in=CATEGORIES).delete()
            self._delete_audited(Branch.objects.filter(branch_name__in=BRANCHES))
        except ProtectedError as exc:
            raise CommandError(
                "Demo data is referenced by other records (for example bookings, payments or "
                "audit entries made through the admin), so it cannot be removed safely. "
                f"Nothing was deleted. Details: {exc.args[0]}"
            ) from exc
        self.stdout.write("Removed the existing demo data.")
