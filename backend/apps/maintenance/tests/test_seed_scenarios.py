"""Demo data for the Exp 10 Maintenance scenarios (seed_scenarios.py)."""

from datetime import date, datetime, time, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone
from freezegun import freeze_time

from apps.fleet.models import Branch, Vehicle, VehicleCategory, VehicleDocument
from apps.fleet.services.availability import available_vehicles
from apps.maintenance.models import MaintenanceJob
from apps.maintenance.seed_scenarios import (
    JOB_PROBLEM,
    NEXT_DUE,
    NOT_DUE,
    OVERDUE,
    REGISTRATIONS,
    SCOOTER_DUE,
)
from apps.maintenance.services import next_service_due, raise_due_preventive_jobs, service_due

pytestmark = pytest.mark.django_db

SEEDED_AT = "2026-10-24 04:37:00+00:00"


def _scenarios() -> str:
    out = StringIO()
    call_command("seed_maintenance_scenarios", stdout=out)
    return out.getvalue()


@pytest.fixture(autouse=True)
def seeded():
    with freeze_time(SEEDED_AT):
        call_command("seed_demo", stdout=StringIO())
        _scenarios()
        yield


def _vehicle(registration: str) -> Vehicle:
    return Vehicle.objects.select_related("category").get(registration_no=registration)


def test_a_second_run_creates_nothing():
    output = _scenarios()
    assert "Created: nothing." in output
    assert all(registration in output for registration in REGISTRATIONS)
    assert Vehicle.objects.filter(registration_no__in=REGISTRATIONS).count() == 4
    assert MaintenanceJob.objects.filter(reported_problem=JOB_PROBLEM).count() == 1
    for registration in REGISTRATIONS:
        vehicle = _vehicle(registration)
        assert vehicle.photos.count() == 4
        assert vehicle.documents.count() == len(VehicleDocument.DocumentType.values)


def test_service_due_at_the_br15_boundaries():
    assert service_due(_vehicle(OVERDUE)) is not None  # TC-M4: odometer == due point
    assert service_due(_vehicle(NOT_DUE)) is None  # TC-M5: one km short
    assert service_due(_vehicle(SCOOTER_DUE)) is not None  # TC-M1: 3,000 km two-wheeler
    assert service_due(_vehicle(NEXT_DUE)) is None


def test_next_service_due_of_the_job_vehicle():
    due = next_service_due(_vehicle(NEXT_DUE))  # TC-M2, TC-M3
    assert (due.odometer, due.date) == (35000, date(2027, 2, 28))
    job = MaintenanceJob.objects.get(reported_problem=JOB_PROBLEM)
    assert job.vehicle.registration_no == NEXT_DUE
    assert (job.job_type, job.severity, job.status) == ("Corrective", "Low", "Reported")


def test_search_leaves_out_the_overdue_sedan():
    tomorrow = timezone.localdate() + timedelta(days=1)
    pickup = timezone.make_aware(datetime.combine(tomorrow, time(10)))
    found = available_vehicles(
        branch=Branch.objects.get(branch_name="Powai"),
        pickup=pickup,
        return_=pickup + timedelta(days=1),
        category=VehicleCategory.objects.get(name="Sedan"),
    ).values_list("registration_no", flat=True)
    assert OVERDUE not in found
    assert NOT_DUE in found
    assert set(found) == {NOT_DUE, NEXT_DUE}  # the demo doc's "2 vehicles are free at Powai"


def test_the_daily_task_raises_preventive_jobs_for_the_due_vehicles():
    raise_due_preventive_jobs()
    raised = set(
        MaintenanceJob.objects.filter(
            job_type=MaintenanceJob.JobType.PREVENTIVE, vehicle__registration_no__in=REGISTRATIONS
        ).values_list("vehicle__registration_no", flat=True)
    )
    assert raised == {OVERDUE, SCOOTER_DUE}
