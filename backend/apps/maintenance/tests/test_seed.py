"""Demo maintenance jobs created by seed_demo: the three states, idempotent, reset-safe."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.fleet.models import Vehicle
from apps.maintenance import services
from apps.maintenance.models import MaintenanceJob
from apps.maintenance.seed import DEMO_PROBLEMS

pytestmark = pytest.mark.django_db


def _seed(*args):
    call_command("seed_demo", *args, stdout=StringIO())


def _demo_jobs():
    return MaintenanceJob.objects.filter(reported_problem__in=DEMO_PROBLEMS).select_related(
        "vehicle", "technician__user"
    )


def test_seed_creates_the_three_demo_jobs():
    _seed()
    jobs = {job.reported_problem: job for job in _demo_jobs()}
    scheduled, in_progress, awaiting = (jobs[p] for p in DEMO_PROBLEMS)

    assert {job.technician.user.email for job in jobs.values()} == {"tech@vrms.test"}
    assert {job.vehicle.home_branch.branch_name for job in jobs.values()} == {"Andheri"}

    assert scheduled.status == MaintenanceJob.Status.SCHEDULED
    assert scheduled.vehicle.status == Vehicle.Status.UNDER_MAINTENANCE

    assert in_progress.status == MaintenanceJob.Status.IN_PROGRESS
    assert services.missing_work(in_progress) == []  # ready to complete
    assert in_progress.vehicle.status == Vehicle.Status.UNDER_MAINTENANCE

    for started in (in_progress, awaiting):  # started within the scheduled period
        assert started.scheduled_from <= started.started_at <= started.scheduled_to

    assert awaiting.awaiting_clearance
    assert services.missing_work(awaiting) == []
    assert awaiting.vehicle.status == Vehicle.Status.UNSAFE
    assert list(services.clearance_queue()) == [awaiting]


def test_seed_twice_creates_no_more_jobs():
    _seed()
    _seed()
    assert _demo_jobs().count() == 3


def test_reset_removes_and_reloads_the_demo_jobs():
    _seed()
    _seed("--reset")
    assert _demo_jobs().count() == 3


# ─── Module N3 demo (maintenance/seed_n3.py) ──────────────────────────────


def test_n3_demo_has_an_authorised_technician_and_a_car_due_for_service(outbox):
    from apps.accounts.models import User
    from apps.fleet.services.status import may_clear_unsafe
    from apps.maintenance import tasks
    from apps.maintenance.seed_n3 import SERVICE_DUE_CAR

    _seed()
    tech2 = User.objects.get(email="tech2@vrms.test")
    assert tech2.check_password("Demo@1234") and may_clear_unsafe(tech2)  # BR-16
    assert not may_clear_unsafe(User.objects.get(email="tech@vrms.test"))  # jobs 1-3 as before
    car = Vehicle.objects.get(registration_no=SERVICE_DUE_CAR)
    assert services.service_due(car) is not None  # SA-2 refuses its handover
    assert MaintenanceJob.objects.count() == 3  # no job is seeded

    tasks.raise_preventive_jobs.delay()  # the daily Beat task (Maint.Auto.Time / Km)
    job = MaintenanceJob.objects.get(vehicle=car)
    assert (job.job_type, job.reported_by, job.due_odometer) == ("Preventive", None, 25100)
    assert services.alert_expiring_documents() >= 1  # its insurance expires in ten days
    assert any(SERVICE_DUE_CAR in m.body for m in outbox if "documents" in m.subject)


def test_n3_reset_removes_untouched_system_jobs_and_their_alerts():
    from apps.maintenance import tasks
    from apps.notifications.models import Notification

    _seed()
    tasks.raise_preventive_jobs.delay()
    assert Notification.objects.filter(template="maintenance_service_due").exists()
    _seed("--reset")  # the system's jobs and alerts do not block the reset
    assert not MaintenanceJob.objects.filter(reported_by__isnull=True).exists()
    assert _demo_jobs().count() == 3
