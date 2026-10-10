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
