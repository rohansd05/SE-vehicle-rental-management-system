"""Maintenance business logic (SRS 3.6, Appendix B, BR-15, BR-16). Views stay thin.

Job lifecycle (Appendix B, Maint.Status): Reported -> Scheduled -> In Progress
-> Completed; Cancelled only from Reported or Scheduled.

complete_job() follows Exp 4 sequence diagram 3:

    complete_job()
      validate recorded work, parts and cost
      alt [recorded work incomplete]  -> "record work first"
      alt [vehicle flagged Unsafe]    -> request clearance (BR-16); an Administrator
                                         later calls approve_clearance(), which
                                         runs update_status() and records the approver
          [vehicle not flagged]       -> update_status() -> Available
      compute next service due (BR-15)
      job status = Completed

Every write locks the job row, calls record_audit (SE-10) and queues any
notification through Celery after commit (SI-2.2).

Owner: Nidhi (WBS 1.4.4).
"""

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import MaintenanceTechnician, User
from apps.core.audit import record_audit, snapshot
from apps.core.choices import VehicleType
from apps.core.permissions import branch_id_of
from apps.fleet.models import Vehicle
from apps.fleet.services.status import update_status
from apps.notifications.services import queue_email

from .models import MaintenanceJob, PartUsed

Job = MaintenanceJob
VStatus = Vehicle.Status

# Jobs that hold the vehicle Under Maintenance (Appendix B: "scheduled or started").
OPEN_STATUSES = (Job.Status.SCHEDULED, Job.Status.IN_PROGRESS)

CENT = Decimal("0.01")


class MaintenanceError(Exception):
    """The maintenance action is not allowed; the message says why."""


class WorkIncompleteError(MaintenanceError):
    """Exp 4 sequence 3, alt [recorded work incomplete]: the job cannot be closed."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(
            "This job cannot be closed: record work first (missing: " + ", ".join(missing) + ")."
        )


class ScheduleConflictError(MaintenanceError):
    """Maint.Conflict: the period overlaps Confirmed bookings; confirmation is required."""

    def __init__(self, bookings: list):
        self.bookings = bookings
        super().__init__(
            "The maintenance period overlaps Confirmed bookings. " "Confirm to schedule it anyway."
        )


# ─── BR-15: next service due ──────────────────────────────────────────────


@dataclass(frozen=True)
class NextServiceDue:
    """BR-15: preventive service is due at whichever of these comes first."""

    odometer: int | None
    date: date | None


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year, month = start.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def service_interval(vehicle: Vehicle) -> tuple[int, int]:
    """BR-15 (km, months) for the vehicle's type."""
    if vehicle.vehicle_type == VehicleType.TWO_WHEELER:
        return (
            settings.PREVENTIVE_SERVICE_INTERVAL_KM_TWO_WHEELER,
            settings.PREVENTIVE_SERVICE_INTERVAL_MONTHS_TWO_WHEELER,
        )
    return (
        settings.PREVENTIVE_SERVICE_INTERVAL_KM_CAR,
        settings.PREVENTIVE_SERVICE_INTERVAL_MONTHS_CAR,
    )


def next_service_due(vehicle: Vehicle) -> NextServiceDue:
    """Maint.Complete, BR-15: computed from the last service, never stored.

    Vehicle.last_service_odometer and last_service_date hold everything the
    rule needs, so no extra fleet column can drift from them (CO-5).
    """
    km, months = service_interval(vehicle)
    return NextServiceDue(
        odometer=(
            vehicle.last_service_odometer + km
            if vehicle.last_service_odometer is not None
            else None
        ),
        date=(
            _add_months(vehicle.last_service_date, months)
            if vehicle.last_service_date is not None
            else None
        ),
    )


# ─── Helpers ──────────────────────────────────────────────────────────────


def _lock(job_id: int) -> MaintenanceJob:
    return Job.objects.select_for_update().select_related("vehicle__category").get(pk=job_id)


def _audit(actor, action: str, job: MaintenanceJob, before: dict | None, request) -> None:
    after = snapshot(job)
    after["parts"] = [
        {"part_name": p.part_name, "quantity": str(p.quantity), "unit_cost": str(p.unit_cost)}
        for p in job.parts.all()
    ]
    record_audit(actor, action, job, before, after, request)


def _is_role(actor, *roles) -> bool:
    return bool(actor and actor.is_authenticated and actor.is_active and actor.role in roles)


def _check_branch(actor, vehicle: Vehicle) -> None:
    """Branch Staff and Branch Managers act only on their own branch's vehicles (SE-4)."""
    if _is_role(actor, User.Role.ADMINISTRATOR):
        return
    if not _is_role(actor, User.Role.BRANCH_STAFF, User.Role.BRANCH_MANAGER):
        raise MaintenanceError("You cannot manage maintenance jobs.")
    if branch_id_of(actor) != vehicle.home_branch_id:
        raise MaintenanceError("This vehicle belongs to another branch.")


def _check_assignee(actor, job: MaintenanceJob) -> None:
    """Only the technician the job is assigned to works on it (BR-16 "authorised")."""
    if job.technician is None or job.technician.user_id != getattr(actor, "pk", None):
        raise MaintenanceError("This job is not assigned to you.")


def _has_other_open_jobs(job: MaintenanceJob) -> bool:
    return (
        Job.objects.filter(vehicle_id=job.vehicle_id, status__in=OPEN_STATUSES)
        .exclude(pk=job.pk)
        .exists()
    )


def _release_vehicle(job: MaintenanceJob, actor, reason: str, request) -> None:
    """Under Maintenance -> Available, unless another job still holds the vehicle
    (Proposed M7). Other statuses are left alone: Unsafe needs BR-16 clearance,
    and Retired is terminal."""
    vehicle = Vehicle.objects.select_for_update().get(pk=job.vehicle_id)
    if vehicle.status == VStatus.UNDER_MAINTENANCE and not _has_other_open_jobs(job):
        update_status(vehicle, VStatus.AVAILABLE, actor=actor, reason=reason, request=request)


def conflicting_bookings(vehicle: Vehicle, start, end):
    """Maint.Conflict: Confirmed bookings whose blocked period overlaps [start, end)."""
    from apps.bookings.models import Booking

    return (
        Booking.objects.filter(
            vehicle=vehicle,
            status=Booking.Status.CONFIRMED,
            pickup_datetime__lt=end,
            return_datetime__gt=start,
        )
        .select_related("customer__user")
        .order_by("pickup_datetime")
    )


def blocked_vehicle_ids(start, end) -> set[int]:
    """Maint.Schedule: vehicles whose scheduled maintenance overlaps [start, end).

    For the availability search (Search.Available), so a vehicle does not
    appear for a period when it is booked into the workshop.
    """
    return set(
        Job.objects.filter(
            status__in=OPEN_STATUSES, scheduled_from__lt=end, scheduled_to__gt=start
        ).values_list("vehicle_id", flat=True)
    )


# ─── Notifications (Notify.*, SI-2.2) ─────────────────────────────────────


def _local(value) -> str:
    return timezone.localtime(value).strftime("%d %b %Y %H:%M") if value else ""


def _notify_technician_assigned(job: MaintenanceJob) -> None:
    queue_email(
        job.technician.user,
        "maintenance_assigned",
        {
            "name": job.technician.user.name,
            "job_id": job.job_id,
            "registration_no": job.vehicle.registration_no,
            "job_type": job.job_type,
            "severity": job.severity,
            "problem": job.reported_problem,
            "scheduled_from": _local(job.scheduled_from),
            "scheduled_to": _local(job.scheduled_to),
        },
    )


def _notify_clearance_requested(job: MaintenanceJob) -> None:
    administrators = User.objects.filter(role=User.Role.ADMINISTRATOR, is_active=True)
    for admin in administrators:
        queue_email(
            admin,
            "maintenance_clearance_requested",
            {
                "name": admin.name,
                "job_id": job.job_id,
                "registration_no": job.vehicle.registration_no,
                "technician": job.technician.user.name,
                "work": job.work_description,
            },
        )


# ─── Report, schedule, cancel (Branch Staff, Branch Manager, Administrator) ─


@transaction.atomic
def report_job(
    actor,
    *,
    vehicle: Vehicle,
    job_type: str,
    severity: str,
    reported_problem: str,
    flag_unsafe: bool = False,
    request=None,
) -> MaintenanceJob:
    """Maint.Create: a job is Reported. Maint.Unsafe: the reporter may flag the vehicle.

    Reporting alone does not change the vehicle status (Appendix B: a vehicle
    goes Under Maintenance when its job is scheduled or started).
    """
    vehicle = Vehicle.objects.select_for_update().select_related("category").get(pk=vehicle.pk)
    _check_branch(actor, vehicle)
    if vehicle.status == VStatus.RETIRED:
        raise MaintenanceError("A retired vehicle cannot be sent for maintenance.")
    if not reported_problem.strip():
        raise MaintenanceError("Describe the problem.")
    job = Job.objects.create(
        vehicle=vehicle,
        job_type=job_type,
        severity=severity,
        reported_problem=reported_problem.strip(),
        reported_by=actor,
        status=Job.Status.REPORTED,
    )
    _audit(actor, "Create", job, None, request)
    if flag_unsafe:
        update_status(
            vehicle,
            VStatus.UNSAFE,
            actor=actor,
            reason=f"Flagged Unsafe with maintenance job {job.job_id}",
            request=request,
        )
    return job


@transaction.atomic
def schedule_job(
    job_id: int,
    actor,
    *,
    technician: MaintenanceTechnician,
    scheduled_from,
    scheduled_to,
    confirm_conflicts: bool = False,
    request=None,
) -> MaintenanceJob:
    """Exp 3 MaintenanceJob.schedule_job(); Maint.Schedule, Maint.Conflict.

    Assigns a technician and a period: Reported -> Scheduled. An Available
    vehicle goes Under Maintenance (Appendix B, Exp 4 sequence 2). A period
    overlapping Confirmed bookings needs `confirm_conflicts` (Maint.Conflict).
    """
    job = _lock(job_id)
    _check_branch(actor, job.vehicle)
    if job.status != Job.Status.REPORTED:
        raise MaintenanceError(f"A {job.status} job cannot be scheduled.")
    if not (technician.user.is_active and technician.user.role == User.Role.MAINTENANCE_TECHNICIAN):
        raise MaintenanceError("Assign an active maintenance technician.")
    if scheduled_to <= scheduled_from:
        raise MaintenanceError("The end of the period must be after its start.")
    conflicts = list(conflicting_bookings(job.vehicle, scheduled_from, scheduled_to))
    if conflicts and not confirm_conflicts:
        raise ScheduleConflictError(conflicts)

    before = snapshot(job)
    job.technician = technician
    job.scheduled_from = scheduled_from
    job.scheduled_to = scheduled_to
    job.status = Job.Status.SCHEDULED
    job.save()
    _audit(actor, "Schedule", job, before, request)
    if job.vehicle.status == VStatus.AVAILABLE:
        update_status(
            job.vehicle,
            VStatus.UNDER_MAINTENANCE,
            actor=actor,
            reason=f"Maintenance job {job.job_id} scheduled",
            request=request,
        )
    _notify_technician_assigned(job)
    return job


@transaction.atomic
def cancel_job(job_id: int, actor, reason: str, request=None) -> MaintenanceJob:
    """Appendix B: a job may be Cancelled from Reported or Scheduled only."""
    job = _lock(job_id)
    _check_branch(actor, job.vehicle)
    if job.status not in (Job.Status.REPORTED, Job.Status.SCHEDULED):
        raise MaintenanceError(f"A {job.status} job cannot be cancelled.")
    if not reason.strip():
        raise MaintenanceError("Give a reason for cancelling.")
    before = snapshot(job)
    job.status = Job.Status.CANCELLED
    job.save()
    record_audit(actor, "Cancel", job, before, {**snapshot(job), "reason": reason}, request)
    _release_vehicle(job, actor, f"Maintenance job {job.job_id} cancelled", request)
    return job


# ─── Start and record work (assigned technician) ──────────────────────────


@transaction.atomic
def start_job(job_id: int, actor, request=None) -> MaintenanceJob:
    """Appendix B Scheduled -> In Progress; the vehicle goes Under Maintenance."""
    job = _lock(job_id)
    _check_assignee(actor, job)
    if job.status != Job.Status.SCHEDULED:
        raise MaintenanceError(f"A {job.status} job cannot be started.")
    vehicle = Vehicle.objects.select_for_update().get(pk=job.vehicle_id)
    if vehicle.status in (VStatus.ON_RENT, VStatus.RETIRED):
        raise MaintenanceError(f"The vehicle is {vehicle.status}; the job cannot start.")
    before = snapshot(job)
    job.status = Job.Status.IN_PROGRESS
    job.started_at = timezone.now()
    job.save()
    _audit(actor, "Start", job, before, request)
    if vehicle.status == VStatus.AVAILABLE:
        update_status(
            vehicle,
            VStatus.UNDER_MAINTENANCE,
            actor=actor,
            reason=f"Maintenance job {job.job_id} started",
            request=request,
        )
    return job


@transaction.atomic
def record_work(
    job_id: int,
    actor,
    *,
    service_date: date,
    odometer_at_service: int,
    work_description: str,
    labour_cost: Decimal,
    downtime_hours: Decimal,
    parts: list[dict],
    request=None,
) -> MaintenanceJob:
    """Maint.Record: the service date, odometer, work, parts, labour and total cost.

    Replaces any earlier record of the same job. The total cost is the labour
    cost plus every part's quantity x unit cost, so the two always agree.
    """
    job = _lock(job_id)
    _check_assignee(actor, job)
    if job.status != Job.Status.IN_PROGRESS:
        raise MaintenanceError("Work can be recorded only on a job in progress.")
    if job.clearance_requested_at:
        raise MaintenanceError("The record is with an Administrator for clearance.")
    if service_date > timezone.localdate():
        raise MaintenanceError("The service date cannot be in the future.")
    if odometer_at_service < job.vehicle.odometer:
        # Appendix A: an odometer reading may never decrease.
        raise MaintenanceError(
            f"The odometer reading cannot be lower than the vehicle's {job.vehicle.odometer} km."
        )
    if not work_description.strip():
        raise MaintenanceError("Describe the work performed.")
    if labour_cost < 0 or downtime_hours < 0:
        raise MaintenanceError("Costs and downtime cannot be negative.")

    before = snapshot(job)
    job.parts.all().delete()
    new_parts = PartUsed.objects.bulk_create(
        PartUsed(
            job=job,
            part_name=part["part_name"].strip(),
            quantity=part["quantity"],
            unit_cost=part["unit_cost"],
        )
        for part in parts
    )
    parts_total = sum((p.quantity * p.unit_cost for p in new_parts), Decimal("0"))
    job.service_date = service_date
    job.odometer_at_service = odometer_at_service
    job.work_description = work_description.strip()
    job.labour_cost = labour_cost
    job.downtime_hours = downtime_hours
    job.total_cost = (labour_cost + parts_total).quantize(CENT)
    job.save()
    _audit(actor, "Record Work", job, before, request)
    return job


# ─── Exp 4 sequence diagram 3: Close Maintenance Job ──────────────────────


def missing_work(job: MaintenanceJob) -> list[str]:
    """Maint.Record: what still has to be recorded before the job can close."""
    missing = []
    if job.service_date is None:
        missing.append("service date")
    if job.odometer_at_service is None:
        missing.append("odometer reading")
    if not job.work_description.strip():
        missing.append("work performed")
    if job.downtime_hours is None:
        missing.append("downtime")
    parts_total = sum((p.quantity * p.unit_cost for p in job.parts.all()), Decimal("0"))
    if job.total_cost != (job.labour_cost + parts_total).quantize(CENT):
        missing.append("total cost")
    return missing


def _finish(job: MaintenanceJob, closer, request) -> MaintenanceJob:
    """Maint.Complete: update the last service and compute BR-15; job Completed."""
    vehicle = Vehicle.objects.select_for_update().select_related("category").get(pk=job.vehicle_id)
    vehicle_before = snapshot(vehicle)
    if vehicle.last_service_date is None or job.service_date >= vehicle.last_service_date:
        vehicle.last_service_date = job.service_date
        vehicle.last_service_odometer = job.odometer_at_service
    vehicle.odometer = max(vehicle.odometer, job.odometer_at_service)
    vehicle.save(
        update_fields=["last_service_date", "last_service_odometer", "odometer", "updated_at"]
    )
    due = next_service_due(vehicle)
    record_audit(
        closer,
        "Service Recorded",
        vehicle,
        vehicle_before,
        {
            **snapshot(vehicle),
            "maintenance_job": job.job_id,
            "next_service_due_km": due.odometer,
            "next_service_due_date": due.date.isoformat() if due.date else None,
        },
        request,
    )

    before = snapshot(job)
    job.status = Job.Status.COMPLETED
    job.closed_by = closer
    job.closed_at = timezone.now()
    job.save()
    job.vehicle = vehicle
    _audit(closer, "Complete", job, before, request)
    return job


@transaction.atomic
def complete_job(job_id: int, actor, request=None) -> MaintenanceJob:
    """Exp 3 MaintenanceJob.complete_job(), Exp 4 sequence diagram 3.

    Returns the job: Completed, or still In Progress and awaiting an
    Administrator's clearance (job.awaiting_clearance) if the vehicle is Unsafe.
    """
    job = _lock(job_id)
    # BR-16: only an Administrator or the assigned technician closes a job.
    if not _is_role(actor, User.Role.ADMINISTRATOR):
        _check_assignee(actor, job)
    if job.status != Job.Status.IN_PROGRESS:
        raise MaintenanceError(f"A {job.status} job cannot be completed.")
    if job.clearance_requested_at:
        raise MaintenanceError("This job is already waiting for an Administrator's clearance.")

    # 1. Validate recorded work, parts and cost. alt [incomplete]: "record work first".
    missing = missing_work(job)
    if missing:
        raise WorkIncompleteError(missing)

    vehicle = Vehicle.objects.select_for_update().get(pk=job.vehicle_id)
    if vehicle.status == VStatus.UNSAFE:
        # 2. alt [vehicle flagged Unsafe]: request clearance of the flag (BR-16).
        before = snapshot(job)
        job.clearance_requested_at = timezone.now()
        job.save()
        _audit(actor, "Clearance Requested", job, before, request)
        _notify_clearance_requested(job)
        return job

    # 3. [vehicle not flagged]: update_status() -> Available.
    _release_vehicle(job, actor, f"Maintenance job {job.job_id} completed", request)
    # 4-5. Compute next service due (BR-15); job status = Completed.
    return _finish(job, actor, request)


@transaction.atomic
def approve_clearance(job_id: int, actor, request=None) -> MaintenanceJob:
    """Exp 4 sequence 3, Administrator lifeline: clear the Unsafe flag (BR-16),
    update_status() -> Available, record the approver, then complete the job."""
    job = _lock(job_id)
    if not _is_role(actor, User.Role.ADMINISTRATOR):
        raise MaintenanceError("Only an Administrator can clear an Unsafe flag (BR-16).")
    if not job.awaiting_clearance:
        raise MaintenanceError("This job is not waiting for clearance.")
    missing = missing_work(job)
    if missing:
        raise WorkIncompleteError(missing)

    update_status(
        job.vehicle,
        VStatus.AVAILABLE,
        actor=actor,
        reason=f"Unsafe flag cleared on maintenance job {job.job_id}",
        request=request,
    )
    if _has_other_open_jobs(job):
        # Another job still holds the vehicle (Proposed M7).
        update_status(
            job.vehicle,
            VStatus.UNDER_MAINTENANCE,
            actor=actor,
            reason=f"Another maintenance job is open after job {job.job_id}",
            request=request,
        )
    return _finish(job, actor, request)


def clearance_queue():
    """Jobs whose work is complete and that wait for an Administrator (BR-16)."""
    return Job.objects.filter(
        status=Job.Status.IN_PROGRESS, clearance_requested_at__isnull=False
    ).order_by("clearance_requested_at")
