"""Module N3 in the rentals flows: SA-2's "overdue for a mandatory safety service" at
handover (BR-15), and Maint.Auto.Km evaluated at every return."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.factories import BranchStaffFactory
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings.models import Booking
from apps.fleet.models import Vehicle
from apps.maintenance.models import MaintenanceJob
from apps.maintenance.services import _add_months
from apps.rentals import services
from apps.rentals.tests.factories import active_booking, readings, ready_booking, return_kwargs

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _media_in_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _serviced(booking, **fields):
    Vehicle.objects.filter(pk=booking.vehicle_id).update(**fields)
    return Booking.objects.get(pk=booking.pk)


# ─── SA-2: no handover while the preventive service is overdue ────────────


def test_a_vehicle_past_its_service_distance_is_refused_with_its_own_reason():
    booking = _serviced(
        ready_booking(),
        odometer=18000,
        last_service_odometer=13000,
        last_service_date=timezone.localdate() - timedelta(days=30),
    )
    [refusal] = services.handover_refusals(booking)
    assert refusal.code == "service_overdue"
    assert "18,000 km" in refusal.message and "BR-15" in refusal.message
    assert "SA-2" in refusal.message


def test_a_vehicle_past_its_service_date_is_refused():
    six_months_ago = _add_months(timezone.localdate(), -6)
    booking = _serviced(
        ready_booking(),
        odometer=13100,
        last_service_odometer=13000,
        last_service_date=six_months_ago,
    )
    assert [r.code for r in services.handover_refusals(booking)] == ["service_overdue"]


def test_a_vehicle_serviced_recently_or_never_is_handed_over():
    recent = _serviced(
        ready_booking(),
        odometer=17999,
        last_service_odometer=13000,
        last_service_date=timezone.localdate() - timedelta(days=30),
    )
    assert services.handover_refusals(recent) == []
    assert services.handover_refusals(ready_booking()) == []  # no service on record


def test_the_overdue_service_is_shown_to_the_staff_and_stops_the_handover():
    booking = _serviced(
        ready_booking(),
        odometer=18000,
        last_service_odometer=13000,
        last_service_date=timezone.localdate() - timedelta(days=30),
    )
    client = authenticated_client(BranchStaffFactory(branch=booking.pickup_branch).user)
    data = client.get(reverse("rentals:handover-detail", args=[booking.pk])).json()
    assert data["can_hand_over"] is False
    assert [r["code"] for r in data["refusals"]] == ["service_overdue"]


def test_the_unsafe_refusal_names_the_authorised_technician_too():
    booking = _serviced(ready_booking(), status=Vehicle.Status.UNSAFE)
    [refusal] = services.handover_refusals(booking)
    assert "Administrator or an authorised technician" in refusal.message  # BR-16


# ─── Maint.Auto.Km: evaluated at every return ─────────────────────────────


def _return(booking, odometer: int):
    staff = BranchStaffFactory(branch=booking.pickup_branch).user
    services.return_vehicle(
        booking.pk, staff, **return_kwargs(readings=readings(odometer_reading=odometer))
    )


def test_a_return_reaching_the_service_distance_raises_the_preventive_job_at_once():
    booking = active_booking()  # handed over at 12,000 km
    Vehicle.objects.filter(pk=booking.vehicle_id).update(
        last_service_odometer=7200, last_service_date=timezone.localdate() - timedelta(days=10)
    )
    _return(booking, 12200)  # due at 7,200 + 5,000 km

    job = MaintenanceJob.objects.get(vehicle_id=booking.vehicle_id)
    assert (job.job_type, job.status, job.reported_by) == ("Preventive", "Reported", None)
    assert job.due_odometer == 12200
    assert Vehicle.objects.get(pk=booking.vehicle_id).status == Vehicle.Status.AVAILABLE
    assert Booking.objects.get(pk=booking.pk).status == Booking.Status.COMPLETED


def test_a_return_short_of_the_interval_raises_nothing():
    booking = active_booking()
    Vehicle.objects.filter(pk=booking.vehicle_id).update(
        last_service_odometer=7300, last_service_date=timezone.localdate() - timedelta(days=10)
    )
    _return(booking, 12200)
    assert not MaintenanceJob.objects.filter(vehicle_id=booking.vehicle_id).exists()
