"""DEMO maintenance jobs for seed_demo (fictitious data, not business rules).

Three jobs on Andheri vehicles, all assigned to the demo technician
(tech@vrms.test) and reported by the demo branch staff (staff@vrms.test):

1. Scheduled, on an Available vehicle, which goes Under Maintenance.
2. In Progress with its work recorded, ready to complete.
3. In Progress on an Unsafe vehicle, work recorded, awaiting an
   Administrator's clearance (BR-16).

Idempotent: a job is created only if its demo problem text is not already on
that vehicle, so a second run changes nothing. Vehicle status changes go
through the status service and are audited as system actions (actor None),
like every other seed_demo audit entry, so --reset can still remove the demo users.
"""

from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from apps.accounts.models import MaintenanceTechnician, User
from apps.fleet.models import Vehicle
from apps.fleet.services.status import update_status

from .models import MaintenanceJob, PartUsed

Job = MaintenanceJob
STAFF_EMAIL = "staff@vrms.test"
TECH_EMAIL = "tech@vrms.test"

# (registration index in seed_demo.demo_registrations(), problem). Indexes 5,
# 10 and 15 are Andheri vehicles; index 0 stays Available for the demo walk.
SCHEDULED = (5, "[Demo] Clutch slipping in third gear.")
IN_PROGRESS = (10, "[Demo] Front brake pads worn; squeal when braking.")
AWAITING = (15, "[Demo] Front brake failure reported by the customer.")
DEMO_PROBLEMS = [SCHEDULED[1], IN_PROGRESS[1], AWAITING[1]]


def _record(job: MaintenanceJob, vehicle: Vehicle, work: str, labour: str, parts) -> None:
    now = timezone.now()
    job.status = Job.Status.IN_PROGRESS
    job.started_at = now - timedelta(hours=3)
    job.service_date = timezone.localdate()
    job.odometer_at_service = vehicle.odometer
    job.work_description = work
    job.labour_cost = Decimal(labour)
    job.downtime_hours = Decimal("3.00")
    job.save()
    for name, quantity, unit_cost in parts:
        PartUsed.objects.create(
            job=job, part_name=name, quantity=Decimal(quantity), unit_cost=Decimal(unit_cost)
        )
    parts_total = sum((p.quantity * p.unit_cost for p in job.parts.all()), Decimal("0"))
    job.total_cost = (job.labour_cost + parts_total).quantize(Decimal("0.01"))
    job.save(update_fields=["total_cost", "updated_at"])


def seed_demo_jobs(count: Callable[[str, bool], None]) -> None:
    """Create the three demo jobs; `count(label, created)` is seed_demo's counter."""
    from apps.core.management.commands.seed_demo import demo_registrations

    registrations = demo_registrations()
    staff = User.objects.get(email=STAFF_EMAIL)
    technician = MaintenanceTechnician.objects.get(user__email=TECH_EMAIL)
    start = timezone.now().replace(minute=0, second=0, microsecond=0)

    def make(
        index: int, problem: str, severity: str, from_hours: int
    ) -> tuple[MaintenanceJob, Vehicle] | None:
        vehicle = Vehicle.objects.get(registration_no=registrations[index])
        if Job.objects.filter(vehicle=vehicle, reported_problem=problem).exists():
            count("maintenance jobs", False)
            return None
        job = Job.objects.create(
            vehicle=vehicle,
            job_type=Job.JobType.CORRECTIVE,
            severity=severity,
            reported_problem=problem,
            reported_by=staff,
            technician=technician,
            scheduled_from=start + timedelta(hours=from_hours),
            scheduled_to=start + timedelta(hours=from_hours + 8),
            status=Job.Status.SCHEDULED,
        )
        count("maintenance jobs", True)
        return job, vehicle

    if made := make(*SCHEDULED, Job.Severity.MEDIUM, 1):
        update_status(
            made[1], Vehicle.Status.UNDER_MAINTENANCE, actor=None, reason="Demo job scheduled"
        )

    if made := make(*IN_PROGRESS, Job.Severity.HIGH, -4):
        job, vehicle = made
        update_status(
            vehicle, Vehicle.Status.UNDER_MAINTENANCE, actor=None, reason="Demo job started"
        )
        _record(
            job,
            vehicle,
            "Replaced the front brake pads and cleaned the callipers.",
            "800.00",
            [("Brake pads (front)", "1", "1450.00"), ("Brake cleaner", "1", "250.00")],
        )

    if made := make(*AWAITING, Job.Severity.CRITICAL, -4):
        job, vehicle = made
        update_status(
            vehicle, Vehicle.Status.UNSAFE, actor=None, reason="Demo: flagged Unsafe at report"
        )
        _record(
            job,
            vehicle,
            "Replaced the front brake disc and pads; bled the hydraulic line; road-tested.",
            "600.00",
            [("Brake disc (front)", "1", "1800.00"), ("Brake pads (front)", "1", "650.00")],
        )
        job.clearance_requested_at = timezone.now()
        job.save(update_fields=["clearance_requested_at", "updated_at"])


def delete_demo_jobs() -> None:
    """For seed_demo --reset: remove only the demo jobs (their parts cascade)."""
    Job.objects.filter(reported_problem__in=DEMO_PROBLEMS).delete()
