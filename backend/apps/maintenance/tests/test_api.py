"""Maintenance API: Exp 4 sequence 3 end to end, error shapes and scoping (SE-4, SE-5)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchStaffFactory,
    MaintenanceTechnicianFactory,
)
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings.tests.factories import BookingFactory
from apps.fleet.models import Vehicle
from apps.fleet.tests.factories import CarFactory
from apps.maintenance.tests.factories import MaintenanceJobFactory

pytestmark = pytest.mark.django_db


def url(name, *args):
    return reverse(f"maintenance:{name}", args=args)


@pytest.fixture
def vehicle():
    return CarFactory(odometer=15000)


@pytest.fixture
def staff(vehicle):
    return authenticated_client(BranchStaffFactory(branch=vehicle.home_branch).user)


@pytest.fixture
def tech():
    return MaintenanceTechnicianFactory()


@pytest.fixture
def tech_client(tech):
    return authenticated_client(tech.user)


@pytest.fixture
def admin_client():
    return authenticated_client(AdministratorFactory().user)


RECORD = {
    "service_date": None,  # filled per test (today)
    "odometer_at_service": 15100,
    "work_description": "Replaced front brake pads.",
    "labour_cost": "800.00",
    "downtime_hours": "6.50",
    "parts": [{"part_name": "Brake pads", "quantity": "1", "unit_cost": "1450.00"}],
}


def _report_and_schedule(staff, vehicle, tech, flag_unsafe=False):
    response = staff.post(
        url("job-list"),
        {
            "vehicle": vehicle.pk,
            "job_type": "Corrective",
            "severity": "High",
            "reported_problem": "Brakes squeal.",
            "flag_unsafe": flag_unsafe,
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    job_id = response.json()["job_id"]
    start = timezone.now() + timedelta(days=1)
    response = staff.post(
        url("job-schedule", job_id),
        {
            "technician": tech.pk,
            "scheduled_from": start.isoformat(),
            "scheduled_to": (start + timedelta(hours=8)).isoformat(),
        },
        format="json",
    )
    assert response.status_code == 200, response.content
    assert response.json()["status"] == "Scheduled"
    return job_id


def _record(tech_client, job_id):
    body = {**RECORD, "service_date": timezone.localdate().isoformat()}
    return tech_client.put(url("job-record", job_id), body, format="json")


def test_technician_completes_a_normal_job(staff, vehicle, tech, tech_client):
    job_id = _report_and_schedule(staff, vehicle, tech)
    assert tech_client.post(url("job-start", job_id)).json()["status"] == "In Progress"

    response = _record(tech_client, job_id)
    assert response.status_code == 200
    assert response.json()["total_cost"] == "2250.00"
    assert response.json()["missing_work"] == []

    response = tech_client.post(url("job-complete", job_id))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "Completed"
    assert body["vehicle"]["status"] == "Available"
    assert body["vehicle"]["next_service_due"]["odometer"] == 20100
    assert body["closed_by"] == tech.user.name


def test_complete_without_record_says_record_work_first(staff, vehicle, tech, tech_client):
    job_id = _report_and_schedule(staff, vehicle, tech)
    tech_client.post(url("job-start", job_id))
    response = tech_client.post(url("job-complete", job_id))
    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "work_incomplete"
    assert "record work first" in body["detail"]
    assert "work performed" in body["missing"]


def test_unsafe_job_waits_then_admin_approves(staff, vehicle, tech, tech_client, admin_client):
    job_id = _report_and_schedule(staff, vehicle, tech, flag_unsafe=True)
    tech_client.post(url("job-start", job_id))
    _record(tech_client, job_id)

    body = tech_client.post(url("job-complete", job_id)).json()
    assert body["status"] == "In Progress"
    assert body["awaiting_clearance"] is True
    assert body["vehicle"]["status"] == "Unsafe"

    queue = admin_client.get(url("clearance-queue")).json()
    assert [job["job_id"] for job in queue["results"]] == [job_id]

    assert tech_client.post(url("job-approve-clearance", job_id)).status_code == 403
    assert staff.post(url("job-approve-clearance", job_id)).status_code == 403

    body = admin_client.post(url("job-approve-clearance", job_id)).json()
    assert body["status"] == "Completed"
    assert body["vehicle"]["status"] == "Available"
    assert body["closed_by"] is not None
    assert admin_client.get(url("clearance-queue")).json()["count"] == 0


def test_schedule_conflict_is_409_with_bookings(staff, vehicle, tech):
    start = timezone.now() + timedelta(days=3)
    booking = BookingFactory(
        vehicle=vehicle, pickup_datetime=start, return_datetime=start + timedelta(days=1)
    )
    job = staff.post(
        url("job-list"),
        {
            "vehicle": vehicle.pk,
            "job_type": "Inspection",
            "severity": "Low",
            "reported_problem": "Annual inspection.",
        },
        format="json",
    ).json()
    payload = {
        "technician": tech.pk,
        "scheduled_from": start.isoformat(),
        "scheduled_to": (start + timedelta(hours=4)).isoformat(),
    }
    response = staff.post(url("job-schedule", job["job_id"]), payload, format="json")
    assert response.status_code == 409
    assert response.json()["code"] == "schedule_conflict"
    assert response.json()["bookings"][0]["booking_reference"] == booking.booking_reference

    payload["confirm_conflicts"] = True
    response = staff.post(url("job-schedule", job["job_id"]), payload, format="json")
    assert response.status_code == 200


def test_technician_sees_only_own_jobs(tech, tech_client):
    mine = MaintenanceJobFactory(technician=tech)
    theirs = MaintenanceJobFactory()
    listed = [job["job_id"] for job in tech_client.get(url("job-list")).json()["results"]]
    assert listed == [mine.pk]
    assert tech_client.get(url("job-detail", theirs.pk)).status_code == 404
    assert tech_client.post(url("job-start", theirs.pk)).status_code == 404


def test_technician_cannot_create_jobs(vehicle, tech_client):
    response = tech_client.post(url("job-list"), {"vehicle": vehicle.pk}, format="json")
    assert response.status_code == 403


def test_staff_scoped_to_their_branch(staff, vehicle):
    own = MaintenanceJobFactory(vehicle=vehicle)
    other = MaintenanceJobFactory()
    listed = [job["job_id"] for job in staff.get(url("job-list")).json()["results"]]
    assert listed == [own.pk]
    assert staff.get(url("job-detail", other.pk)).status_code == 404
    response = staff.post(
        url("job-list"),
        {
            "vehicle": other.vehicle.pk,
            "job_type": "Corrective",
            "severity": "Low",
            "reported_problem": "x",
        },
        format="json",
    )
    assert response.status_code == 404
    vehicles = [v["id"] for v in staff.get(url("vehicle-list")).json()["results"]]
    assert vehicles == [vehicle.pk]


def test_job_list_filters_by_status(admin_client):
    MaintenanceJobFactory(status="Reported")
    done = MaintenanceJobFactory(status="Completed")
    response = admin_client.get(url("job-list"), {"status": "Completed"})
    assert [job["job_id"] for job in response.json()["results"]] == [done.pk]


def test_technicians_list_and_vehicle_history(staff, vehicle, tech, tech_client):
    MaintenanceTechnicianFactory(user__is_active=False)
    technicians = staff.get(url("technician-list")).json()
    assert [t["technician_id"] for t in technicians] == [tech.pk]

    job = MaintenanceJobFactory(vehicle=vehicle)
    history = tech_client.get(url("vehicle-history", vehicle.pk)).json()
    assert [j["job_id"] for j in history["results"]] == [job.pk]
    assert staff.get(url("vehicle-history", CarFactory().pk)).status_code == 404


def test_cancel_endpoint(staff, vehicle, tech):
    job_id = _report_and_schedule(staff, vehicle, tech)
    response = staff.post(url("job-cancel", job_id), {"reason": "Duplicate"}, format="json")
    assert response.status_code == 200
    assert response.json()["status"] == "Cancelled"
    vehicle.refresh_from_db()
    assert vehicle.status == Vehicle.Status.AVAILABLE
