"""DEMO data for Module N3 maintenance, loaded by seed_demo (fictitious data).

- MH02DN7001, a Bandra hatchback whose odometer has passed its BR-15 service
  distance: the fleet and maintenance screens show its service overdue, SA-2
  refuses its handover, and the daily Beat task (it runs as soon as Celery
  Beat starts) raises its Preventive job through raise_preventive_job_if_due(),
  pre-filled with the due point (UC 9 extension 2a), with the service-due
  alert (Send Maintenance Alert). Its insurance expires ten days after
  seeding, for the daily document expiry alert. No job is seeded: the demo
  keeps exactly jobs 1 to 3 (maintenance/seed.py).
- tech2@vrms.test, a second demo technician (password as the other demo
  accounts), authorised to clear an Unsafe flag (BR-16): report a fault with
  "flag as Unsafe", schedule it to them, and they clear the flag as they close
  the job. tech@vrms.test stays unauthorised, so jobs 1 to 3 behave as before.

Audited as system actions (actor None). Idempotent: everything is created once.
"""

from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from apps.accounts.models import MaintenanceTechnician, User
from apps.core.audit import entity_type, snapshot
from apps.core.choices import FuelType
from apps.core.models import AuditLog
from apps.fleet.models import Branch, Car, VehicleCategory, VehicleDocument
from apps.notifications.models import Notification

from .models import MaintenanceJob, UnsafeClearanceAuthorisation

BRANCH = "Bandra"
SERVICE_DUE_CAR = "MH02DN7001"
TECH2 = ("tech2@vrms.test", "Demo Technician (authorised)", "+919800000011")


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


def _service_due_car(count) -> Car:
    car, created = Car.objects.get_or_create(
        registration_no=SERVICE_DUE_CAR,
        defaults={
            "brand": "Maruti Suzuki",
            "model": "Baleno",
            "category": VehicleCategory.objects.get(name="Hatchback"),
            "home_branch": Branch.objects.get(branch_name=BRANCH),
            "year": 2024,
            "colour": "Blue",
            "fuel_type": FuelType.PETROL,
            "chassis_number": "DEMOMAINT0001",
            "available_from": date(2026, 1, 1),
            "odometer": 25120,  # BR-15: serviced at 20,100 km, so due at 25,100 km
            "last_service_date": timezone.localdate() - timedelta(days=60),
            "last_service_odometer": 20100,
            "transmission": Car.Transmission.MANUAL,
            "seating_capacity": 5,
            "fuel_capacity": Decimal("37.00"),
        },
    )
    count("vehicles", created)
    if created:
        _audit("Create", car)
    today = timezone.localdate()
    for document_type in VehicleDocument.DocumentType.values:
        expiry = today + timedelta(days=10) if document_type == "Insurance" else date(2027, 12, 31)
        _, created = VehicleDocument.objects.get_or_create(
            vehicle=car,
            document_type=document_type,
            defaults={
                "document_number": f"DEMO-N3-{document_type[:3].upper()}",
                "valid_from": date(2026, 1, 1),
                "expiry_date": expiry,
            },
        )
        count("vehicle documents", created)
    return car


def _authorised_technician(count) -> MaintenanceTechnician:
    from apps.core.management.commands.seed_demo import ADMIN, DEMO_PASSWORD

    email, name, mobile = TECH2
    user = User.objects.filter(email=email).first()
    if user is None:
        user = User.objects.create_user(
            email=email,
            password=DEMO_PASSWORD,
            name=name,
            mobile_no=mobile,
            role=User.Role.MAINTENANCE_TECHNICIAN,
            address="Ground floor, Link Road, Andheri (W), Mumbai 400053",
        )
        count("users", True)
        _audit("Create", user)
    technician, created = MaintenanceTechnician.objects.get_or_create(
        user=user, defaults={"workshop": "Agency workshop, Andheri"}
    )
    count("technicians", created)
    grant, created = UnsafeClearanceAuthorisation.objects.get_or_create(
        technician=technician, defaults={"granted_by": User.objects.get(email=ADMIN.email)}
    )
    if created:  # BR-16, as the Users screen records it
        AuditLog.objects.record(
            actor=None,
            action="Unsafe Clearance Authorised",
            entity_type=entity_type(technician),
            entity_id=technician.pk,
            after=snapshot(grant),
        )
    return technician


def seed_demo_n3_maintenance(count: Callable[[str, bool], None]) -> None:
    """Called by seed_demo after the other demos; `count(label, created)` is its counter."""
    _service_due_car(count)
    _authorised_technician(count)


def delete_demo_n3_maintenance() -> None:
    """For seed_demo --reset: remove what seed_demo_n3_maintenance() creates, and any
    Preventive job the system raised on a demo vehicle that nobody has touched yet
    (the daily task raises them), with its alerts, so they never block the reset."""
    untouched = MaintenanceJob.objects.filter(
        job_type=MaintenanceJob.JobType.PREVENTIVE,
        reported_by__isnull=True,
        status=MaintenanceJob.Status.REPORTED,
        vehicle__chassis_number__startswith="DEMO",
    )
    for job in untouched:
        Notification.objects.filter(
            template="maintenance_service_due", context__job_id=job.pk
        ).delete()
    untouched.delete()
    for car in Car.objects.filter(registration_no=SERVICE_DUE_CAR):
        _audit("Delete", car)
        car.delete()  # its documents cascade
    UnsafeClearanceAuthorisation.objects.filter(technician__user__email=TECH2[0]).delete()
    MaintenanceTechnician.objects.filter(user__email=TECH2[0]).delete()
    for user in User.objects.filter(email=TECH2[0]):
        _audit("Delete", user)
        user.delete()
