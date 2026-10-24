"""DEMO data for the Exp 10 Maintenance scenarios, loaded by seed_maintenance_scenarios.

Run after `seed_demo`. Four fictitious Powai vehicles at the BR-15 boundaries,
each with valid documents and the four catalogue photos, so they show in search:

- MH03DX9001, Sedan (TC-M4): serviced at 20,000 km 30 days before the seed,
  odometer exactly 25,000 km. Due, so search leaves it out and its page shows
  "Not bookable: service overdue" (SA-2).
- MH03DX9002, Sedan (TC-M5): the same at 24,999 km. Not due, bookable.
- MH03DX9003, Scooter (TC-M1): serviced at 3,000 km, odometer 6,000 km.
  Due at the two-wheeler interval of 3,000 km.
- MH03DX9004, Sedan (TC-M2, TC-M3): serviced at 30,000 km on 31 Aug 2026,
  odometer 31,000 km, so the next service is due at 35,000 km or 28 Feb 2027.
  One Reported Corrective job, so its job page shows "Next service due".

No Preventive job is seeded: raise_due_preventive_jobs() (Celery Beat) raises
them for 9001 and 9003. Audited as system actions (actor None). Idempotent:
vehicles, documents and the job are created once.
"""

from collections.abc import Callable
from datetime import date, timedelta

from django.utils import timezone

from apps.accounts.models import User
from apps.core.choices import FuelType
from apps.core.management.commands.seed_demo import ADMIN, demo_fuel_capacity
from apps.fleet.models import Branch, Car, TwoWheeler, VehicleCategory, VehicleDocument
from apps.fleet.seed import seed_demo_photos

from .models import MaintenanceJob
from .seed_n3 import _audit

BRANCH = "Powai"
OVERDUE, NOT_DUE, SCOOTER_DUE, NEXT_DUE = "MH03DX9001", "MH03DX9002", "MH03DX9003", "MH03DX9004"
REGISTRATIONS = [OVERDUE, NOT_DUE, SCOOTER_DUE, NEXT_DUE]
JOB_PROBLEM = "[Demo] Exp 10 scenario: check the next service due."

Count = Callable[[str, bool], None]


def _vehicles() -> list[tuple]:
    """(registration, model class, category, brand, model, colour, last service km,
    last service date, odometer, type-specific fields)."""
    month_ago = timezone.localdate() - timedelta(days=30)
    sedan = {"transmission": Car.Transmission.MANUAL, "seating_capacity": 5}
    return [
        (OVERDUE, Car, "Sedan", "Skoda", "Slavia", "Grey", 20000, month_ago, 25000, sedan),
        (NOT_DUE, Car, "Sedan", "Volkswagen", "Virtus", "White", 20000, month_ago, 24999, sedan),
        (
            SCOOTER_DUE,
            TwoWheeler,
            "Scooter",
            "Yamaha",
            "Fascino 125",
            "Blue",
            3000,
            month_ago,
            6000,
            {"engine_cc": 125},
        ),
        (
            NEXT_DUE,
            Car,
            "Sedan",
            "Hyundai",
            "Aura",
            "Silver",
            30000,
            date(2026, 8, 31),
            31000,
            sedan,
        ),
    ]


def _seed_vehicles(count: Count) -> dict[str, object]:
    branch = Branch.objects.get(branch_name=BRANCH)
    vehicles = {}
    for index, spec in enumerate(_vehicles()):
        registration, model_class, category, brand, model, colour, km, day, odometer, extra = spec
        vehicle, created = model_class.objects.get_or_create(
            registration_no=registration,
            defaults={
                "brand": brand,
                "model": model,
                "category": VehicleCategory.objects.get(name=category),
                "home_branch": branch,
                "year": 2024,
                "colour": colour,
                "fuel_type": FuelType.PETROL,
                "fuel_capacity": demo_fuel_capacity(category, FuelType.PETROL),
                "chassis_number": f"DEMOEXP10M000{index + 1}",
                "available_from": date(2026, 1, 1),
                "odometer": odometer,
                "last_service_date": day,
                "last_service_odometer": km,
                **extra,
            },
        )
        count("vehicles", created)
        if created:
            _audit("Create", vehicle)
        for document_type in VehicleDocument.DocumentType.values:
            _, created = VehicleDocument.objects.get_or_create(
                vehicle=vehicle,
                document_type=document_type,
                defaults={
                    "document_number": f"DEMO-M{index + 1}-{document_type[:3].upper()}",
                    "valid_from": date(2026, 1, 1),
                    "expiry_date": date(2027, 12, 31),
                },
            )
            count("vehicle documents", created)
        vehicles[registration] = vehicle
    return vehicles


def _seed_job(count: Count, vehicle) -> None:
    """Maint.Create as an Administrator reports it; reporting leaves the status alone."""
    if MaintenanceJob.objects.filter(vehicle=vehicle, reported_problem=JOB_PROBLEM).exists():
        count("maintenance jobs", False)
        return
    job = MaintenanceJob.objects.create(
        vehicle=vehicle,
        job_type=MaintenanceJob.JobType.CORRECTIVE,
        severity=MaintenanceJob.Severity.LOW,
        reported_problem=JOB_PROBLEM,
        reported_by=User.objects.get(email=ADMIN.email),
        status=MaintenanceJob.Status.REPORTED,
    )
    count("maintenance jobs", True)
    _audit("Create", job)


def seed_maintenance_scenarios(count: Count) -> None:
    """`count(label, created)` counts what is created, as in seed_demo."""
    vehicles = _seed_vehicles(count)
    _seed_job(count, vehicles[NEXT_DUE])
    seed_demo_photos(count)  # the four catalogue photos of the new vehicles
