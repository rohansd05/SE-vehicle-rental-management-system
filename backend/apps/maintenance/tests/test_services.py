"""Maintenance services: lifecycle, Exp 4 sequence 3, BR-15, BR-16 (SRS 3.6, Appendix B)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchManagerFactory,
    BranchStaffFactory,
    MaintenanceTechnicianFactory,
)
from apps.bookings.tests.factories import BookingFactory
from apps.core.models import AuditLog
from apps.fleet.models import Vehicle
from apps.fleet.services.status import ActorNotPermittedError
from apps.fleet.tests.factories import CarFactory, TwoWheelerFactory
from apps.maintenance import services
from apps.maintenance.models import MaintenanceJob
from apps.maintenance.tests.factories import MaintenanceJobFactory

pytestmark = pytest.mark.django_db

S = MaintenanceJob.Status
V = Vehicle.Status


@pytest.fixture
def vehicle():
    return CarFactory(odometer=15000)


@pytest.fixture
def staff(vehicle):
    return BranchStaffFactory(branch=vehicle.home_branch).user


@pytest.fixture
def tech():
    return MaintenanceTechnicianFactory()


@pytest.fixture
def admin():
    return AdministratorFactory().user


def _period(days=1):
    start = timezone.now() + timedelta(days=days)
    return start, start + timedelta(hours=8)


def _report(staff, vehicle, **kwargs):
    return services.report_job(
        staff,
        vehicle=vehicle,
        job_type=MaintenanceJob.JobType.CORRECTIVE,
        severity=MaintenanceJob.Severity.HIGH,
        reported_problem="Brakes squeal.",
        **kwargs,
    )


def _scheduled(staff, vehicle, tech, **kwargs):
    job = _report(staff, vehicle, **kwargs)
    start, end = _period()
    return services.schedule_job(
        job.pk, staff, technician=tech, scheduled_from=start, scheduled_to=end
    )


def _record(job, tech, **overrides):
    data = {
        "service_date": timezone.localdate(),
        "odometer_at_service": 15100,
        "work_description": "Replaced brake pads.",
        "labour_cost": Decimal("800.00"),
        "downtime_hours": Decimal("6.50"),
        "parts": [
            {"part_name": "Brake pads", "quantity": Decimal("1"), "unit_cost": Decimal("1450.00")},
            {"part_name": "Fluid", "quantity": Decimal("0.5"), "unit_cost": Decimal("600.00")},
        ],
    }
    data.update(overrides)
    return services.record_work(job.pk, tech.user, **data)


def _in_progress(staff, vehicle, tech, recorded=True, **kwargs):
    job = _scheduled(staff, vehicle, tech, **kwargs)
    job = services.start_job(job.pk, tech.user)
    return _record(job, tech) if recorded else job


def _status(vehicle):
    vehicle.refresh_from_db()
    return vehicle.status


# ─── Maint.Create / Maint.Unsafe ──────────────────────────────────────────


def test_report_creates_a_reported_job_and_leaves_the_vehicle_status(staff, vehicle):
    job = _report(staff, vehicle)
    assert job.status == S.REPORTED
    assert job.reported_by == staff
    assert _status(vehicle) == V.AVAILABLE  # Appendix B: only scheduling moves it
    assert AuditLog.objects.filter(entity_type="maintenance.MaintenanceJob", action="Create")


def test_report_can_flag_the_vehicle_unsafe(staff, vehicle):
    _report(staff, vehicle, flag_unsafe=True)
    assert _status(vehicle) == V.UNSAFE


def test_staff_cannot_report_on_another_branchs_vehicle(vehicle):
    other = BranchStaffFactory().user
    with pytest.raises(services.MaintenanceError, match="another branch"):
        _report(other, vehicle)


def test_branch_manager_reports_on_own_branch(vehicle):
    manager = BranchManagerFactory(branch=vehicle.home_branch).user
    assert _report(manager, vehicle).status == S.REPORTED


def test_cannot_report_on_a_retired_vehicle(staff):
    vehicle = CarFactory(status=V.RETIRED, home_branch=staff.branch_staff.branch)
    with pytest.raises(services.MaintenanceError, match="retired"):
        _report(staff, vehicle)


def test_technician_cannot_report_through_the_service(vehicle, tech):
    with pytest.raises(services.MaintenanceError):
        _report(tech.user, vehicle)


# ─── Maint.Schedule / Maint.Conflict ──────────────────────────────────────


def test_schedule_assigns_and_takes_vehicle_off_the_road(staff, vehicle, tech, outbox):
    job = _scheduled(staff, vehicle, tech)
    assert job.status == S.SCHEDULED
    assert job.technician == tech
    assert _status(vehicle) == V.UNDER_MAINTENANCE
    assert any(m.recipient == tech.user.email and "assigned" in m.subject for m in outbox)


def test_schedule_keeps_an_unsafe_vehicle_unsafe(staff, vehicle, tech):
    _scheduled(staff, vehicle, tech, flag_unsafe=True)
    assert _status(vehicle) == V.UNSAFE


def test_schedule_conflict_needs_confirmation(staff, vehicle, tech):
    start, end = _period(days=2)
    booking = BookingFactory(
        vehicle=vehicle, pickup_datetime=start, return_datetime=start + timedelta(days=1)
    )
    job = _report(staff, vehicle)
    with pytest.raises(services.ScheduleConflictError) as caught:
        services.schedule_job(
            job.pk, staff, technician=tech, scheduled_from=start, scheduled_to=end
        )
    assert caught.value.bookings == [booking]
    job.refresh_from_db()
    assert job.status == S.REPORTED

    services.schedule_job(
        job.pk,
        staff,
        technician=tech,
        scheduled_from=start,
        scheduled_to=end,
        confirm_conflicts=True,
    )
    job.refresh_from_db()
    assert job.status == S.SCHEDULED


@pytest.mark.parametrize(
    ("gap", "conflicts"),
    [(timedelta(minutes=30), True), (timedelta(minutes=60), False)],
    ids=["inside-the-buffer", "after-the-buffer"],
)
def test_conflicts_honour_the_br1_turnaround_buffer(vehicle, gap, conflicts):
    """BR-1: a booking holds the vehicle until 60 minutes after its return time."""
    pickup = timezone.now() + timedelta(days=2)
    booking = BookingFactory(
        vehicle=vehicle, pickup_datetime=pickup, return_datetime=pickup + timedelta(hours=8)
    )
    start = booking.return_datetime + gap
    found = list(services.conflicting_bookings(vehicle, start, start + timedelta(hours=4)))
    assert found == ([booking] if conflicts else [])


def test_schedule_rejects_bad_period_inactive_technician_and_wrong_status(staff, vehicle, tech):
    job = _report(staff, vehicle)
    start, end = _period()
    with pytest.raises(services.MaintenanceError, match="after its start"):
        services.schedule_job(
            job.pk, staff, technician=tech, scheduled_from=end, scheduled_to=start
        )
    inactive = MaintenanceTechnicianFactory(user__is_active=False)
    with pytest.raises(services.MaintenanceError, match="active"):
        services.schedule_job(
            job.pk, staff, technician=inactive, scheduled_from=start, scheduled_to=end
        )
    services.schedule_job(job.pk, staff, technician=tech, scheduled_from=start, scheduled_to=end)
    with pytest.raises(services.MaintenanceError, match="cannot be scheduled"):
        services.schedule_job(
            job.pk, staff, technician=tech, scheduled_from=start, scheduled_to=end
        )


def test_blocked_vehicle_ids_for_search(staff, vehicle, tech):
    job = _scheduled(staff, vehicle, tech)
    inside = (job.scheduled_from + timedelta(hours=1), job.scheduled_to + timedelta(hours=1))
    assert services.blocked_vehicle_ids(*inside) == {vehicle.pk}
    after = (job.scheduled_to, job.scheduled_to + timedelta(hours=1))
    assert services.blocked_vehicle_ids(*after) == set()


# ─── Start and record (Maint.Record) ──────────────────────────────────────


def test_only_the_assigned_technician_starts(staff, vehicle, tech):
    job = _scheduled(staff, vehicle, tech)
    with pytest.raises(services.MaintenanceError, match="not assigned"):
        services.start_job(job.pk, MaintenanceTechnicianFactory().user)
    job = services.start_job(job.pk, tech.user)
    assert job.status == S.IN_PROGRESS
    assert job.started_at is not None


def test_start_refused_while_vehicle_is_on_rent(staff, tech):
    vehicle = CarFactory(status=V.ON_RENT)
    staff = BranchStaffFactory(branch=vehicle.home_branch).user
    job = _scheduled(staff, vehicle, tech)
    with pytest.raises(services.MaintenanceError, match="On Rent"):
        services.start_job(job.pk, tech.user)


def test_start_moves_an_available_vehicle_under_maintenance(staff, vehicle, tech):
    job = _scheduled(staff, vehicle, tech)
    Vehicle.objects.filter(pk=vehicle.pk).update(status=V.AVAILABLE)
    services.start_job(job.pk, tech.user)
    assert _status(vehicle) == V.UNDER_MAINTENANCE


def test_record_computes_total_and_replaces_parts(staff, vehicle, tech):
    job = _in_progress(staff, vehicle, tech)
    assert job.total_cost == Decimal("2550.00")  # 800 + 1450 + 0.5 x 600
    job = _record(job, tech, parts=[], labour_cost=Decimal("500.00"))
    assert job.parts.count() == 0
    assert job.total_cost == Decimal("500.00")


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"odometer_at_service": 14999}, "lower"),
        ({"service_date": date.today() + timedelta(days=2)}, "future"),
        ({"work_description": "  "}, "Describe"),
    ],
)
def test_record_validation(staff, vehicle, tech, override, message):
    job = _in_progress(staff, vehicle, tech, recorded=False)
    with pytest.raises(services.MaintenanceError, match=message):
        _record(job, tech, **override)


def test_record_only_while_in_progress(staff, vehicle, tech):
    job = _scheduled(staff, vehicle, tech)
    with pytest.raises(services.MaintenanceError, match="in progress"):
        _record(job, tech)


# ─── Exp 4 sequence diagram 3: complete_job() ─────────────────────────────


def test_complete_refused_when_work_not_recorded(staff, vehicle, tech):
    job = _in_progress(staff, vehicle, tech, recorded=False)
    with pytest.raises(services.WorkIncompleteError, match="record work first") as caught:
        services.complete_job(job.pk, tech.user)
    assert "work performed" in caught.value.missing
    job.refresh_from_db()
    assert job.status == S.IN_PROGRESS
    assert _status(vehicle) == V.UNDER_MAINTENANCE


def test_complete_unflagged_vehicle_becomes_available(staff, vehicle, tech):
    job = _in_progress(staff, vehicle, tech)
    job = services.complete_job(job.pk, tech.user)

    assert job.status == S.COMPLETED
    assert job.closed_by == tech.user
    assert job.closed_at is not None
    vehicle.refresh_from_db()
    assert vehicle.status == V.AVAILABLE
    # Maint.Complete: last service distance and date; BR-15 next due (car).
    assert vehicle.last_service_odometer == 15100
    assert vehicle.odometer == 15100
    assert vehicle.last_service_date == timezone.localdate()
    due = services.next_service_due(vehicle)
    assert due.odometer == 20100
    assert AuditLog.objects.filter(entity_type="fleet.Vehicle", action="Service Recorded")


def test_complete_unsafe_vehicle_waits_for_clearance(staff, vehicle, tech, admin, outbox):
    job = _in_progress(staff, vehicle, tech, flag_unsafe=True)
    job = services.complete_job(job.pk, tech.user)

    assert job.status == S.IN_PROGRESS
    assert job.awaiting_clearance
    assert _status(vehicle) == V.UNSAFE
    assert list(services.clearance_queue()) == [job]
    assert any(m.recipient == admin.email and "clearance" in m.subject for m in outbox)
    with pytest.raises(services.MaintenanceError, match="already waiting"):
        services.complete_job(job.pk, tech.user)
    with pytest.raises(services.MaintenanceError, match="clearance"):
        _record(job, tech)


@pytest.mark.parametrize("who", ["tech", "staff", "manager"])
def test_non_administrator_cannot_approve_clearance(staff, vehicle, tech, who):
    job = services.complete_job(_in_progress(staff, vehicle, tech, flag_unsafe=True).pk, tech.user)
    actor = {
        "tech": tech.user,
        "staff": staff,
        "manager": BranchManagerFactory(branch=vehicle.home_branch).user,
    }[who]
    with pytest.raises(services.MaintenanceError, match="BR-16"):
        services.approve_clearance(job.pk, actor)
    assert _status(vehicle) == V.UNSAFE


def test_technician_cannot_clear_unsafe_through_the_status_service(staff, vehicle, tech):
    _in_progress(staff, vehicle, tech, flag_unsafe=True)
    with pytest.raises(ActorNotPermittedError):
        vehicle.update_status(V.AVAILABLE, actor=tech.user, reason="done")


def test_administrator_approves_clearance(staff, vehicle, tech, admin):
    job = services.complete_job(_in_progress(staff, vehicle, tech, flag_unsafe=True).pk, tech.user)
    job = services.approve_clearance(job.pk, admin)

    assert job.status == S.COMPLETED
    assert job.closed_by == admin  # BR-16: the approver is recorded
    vehicle.refresh_from_db()
    assert vehicle.status == V.AVAILABLE
    assert vehicle.last_service_odometer == 15100
    assert not services.clearance_queue().exists()
    cleared = AuditLog.objects.get(
        entity_type="fleet.Vehicle", action="Vehicle Status Changed", before={"status": V.UNSAFE}
    )
    assert cleared.actor == admin


def test_approve_requires_a_waiting_job(staff, vehicle, tech, admin):
    job = _in_progress(staff, vehicle, tech)
    with pytest.raises(services.MaintenanceError, match="not waiting"):
        services.approve_clearance(job.pk, admin)


def test_administrator_may_complete_directly(staff, vehicle, tech, admin):
    job = _in_progress(staff, vehicle, tech)
    job = services.complete_job(job.pk, admin)
    assert job.closed_by == admin


def test_other_technician_cannot_complete(staff, vehicle, tech):
    job = _in_progress(staff, vehicle, tech)
    with pytest.raises(services.MaintenanceError, match="not assigned"):
        services.complete_job(job.pk, MaintenanceTechnicianFactory().user)


def test_vehicle_stays_under_maintenance_while_another_job_is_open(staff, vehicle, tech):
    first = _in_progress(staff, vehicle, tech)
    _scheduled(staff, vehicle, tech)
    services.complete_job(first.pk, tech.user)
    assert _status(vehicle) == V.UNDER_MAINTENANCE


def test_clearance_with_another_open_job_leaves_vehicle_under_maintenance(
    staff, vehicle, tech, admin
):
    job = services.complete_job(_in_progress(staff, vehicle, tech, flag_unsafe=True).pk, tech.user)
    _scheduled(staff, vehicle, tech)
    services.approve_clearance(job.pk, admin)
    assert _status(vehicle) == V.UNDER_MAINTENANCE


def test_complete_only_in_progress(staff, vehicle, tech):
    job = _scheduled(staff, vehicle, tech)
    with pytest.raises(services.MaintenanceError, match="cannot be completed"):
        services.complete_job(job.pk, tech.user)


def test_class_diagram_methods_delegate(staff, vehicle, tech):
    """Exp 3 MaintenanceJob.schedule_job() and complete_job() keep their names."""
    job = _report(staff, vehicle)
    start, end = _period()
    job = job.schedule_job(technician=tech, scheduled_from=start, scheduled_to=end, actor=staff)
    assert job.status == S.SCHEDULED
    job = services.start_job(job.pk, tech.user)
    job = _record(job, tech)
    job = job.complete_job(actor=tech.user)
    assert job.status == S.COMPLETED


# ─── Cancel (Appendix B) ──────────────────────────────────────────────────


def test_cancel_scheduled_job_releases_the_vehicle(staff, vehicle, tech):
    job = _scheduled(staff, vehicle, tech)
    job = services.cancel_job(job.pk, staff, "Duplicate report")
    assert job.status == S.CANCELLED
    assert _status(vehicle) == V.AVAILABLE


def test_cancel_keeps_unsafe_flag(staff, vehicle, tech):
    job = _report(staff, vehicle, flag_unsafe=True)
    services.cancel_job(job.pk, staff, "Wrong vehicle")
    assert _status(vehicle) == V.UNSAFE


def test_cannot_cancel_in_progress_or_without_reason(staff, vehicle, tech):
    job = _report(staff, vehicle)
    with pytest.raises(services.MaintenanceError, match="reason"):
        services.cancel_job(job.pk, staff, " ")
    job = _in_progress(staff, vehicle, tech)
    with pytest.raises(services.MaintenanceError, match="cannot be cancelled"):
        services.cancel_job(job.pk, staff, "Changed mind")


# ─── BR-15 ────────────────────────────────────────────────────────────────


def test_br15_car_interval():
    car = CarFactory(
        odometer=20000, last_service_odometer=12000, last_service_date=date(2026, 3, 31)
    )
    due = services.next_service_due(car)
    assert due.odometer == 17000
    assert due.date == date(2026, 9, 30)  # 6 months, clamped to the month's last day


def test_br15_two_wheeler_interval():
    bike = TwoWheelerFactory(
        odometer=5000, last_service_odometer=4000, last_service_date=date(2026, 11, 15)
    )
    due = services.next_service_due(bike)
    assert due.odometer == 7000
    assert due.date == date(2027, 3, 15)  # 4 months, across the year end


def test_br15_unknown_without_a_service_record():
    due = services.next_service_due(CarFactory())
    assert due.odometer is None and due.date is None


def test_older_service_date_does_not_overwrite_last_service(staff, vehicle, tech):
    Vehicle.objects.filter(pk=vehicle.pk).update(
        last_service_date=timezone.localdate(), last_service_odometer=15000
    )
    job = _in_progress(staff, vehicle, tech, recorded=False)
    _record(job, tech, service_date=timezone.localdate() - timedelta(days=5))
    services.complete_job(job.pk, tech.user)
    vehicle.refresh_from_db()
    assert vehicle.last_service_date == timezone.localdate()
    assert vehicle.last_service_odometer == 15000
    assert vehicle.odometer == 15100


def test_factory_job_has_no_record():
    job = MaintenanceJobFactory(status=S.IN_PROGRESS)
    assert "service date" in services.missing_work(job)
