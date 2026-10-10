"""Maintenance jobs and parts (Exp 3; Maint.*; BR-16)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.maintenance.models import MaintenanceJob
from apps.maintenance.tests.factories import MaintenanceJobFactory, PartUsedFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "factory_class", [MaintenanceJobFactory, PartUsedFactory], ids=lambda f: f.__name__
)
def test_factory_creates_a_valid_row(factory_class):
    instance = factory_class()
    instance.full_clean()
    assert instance.pk is not None
    assert str(instance)


def test_status_values_match_the_handoff():
    assert MaintenanceJob.Status.values == [
        "Reported",
        "Scheduled",
        "In Progress",
        "Completed",
        "Cancelled",
    ]


def test_job_types_are_those_of_maint_create():
    assert MaintenanceJob.JobType.values == [
        "Preventive",
        "Corrective",
        "Inspection",
        "Cleaning",
        "Documentation",
    ]


def test_new_job_is_reported_and_keeps_the_diagram_id():
    job = MaintenanceJobFactory()
    assert job.status == "Reported"
    assert job.job_id == job.pk


def test_schedule_must_end_after_it_starts():
    start = timezone.now()
    with pytest.raises(IntegrityError), transaction.atomic():
        MaintenanceJobFactory(scheduled_from=start, scheduled_to=start - timedelta(hours=1))


def test_closing_user_is_recorded():
    """BR-16: the identity of the user who closes the job is recorded."""
    closer = UserFactory()
    job = MaintenanceJobFactory(
        status=MaintenanceJob.Status.COMPLETED, closed_by=closer, closed_at=timezone.now()
    )
    assert job.closed_by == closer


def test_parts_and_their_cost():
    part = PartUsedFactory(quantity=Decimal("2.00"), unit_cost=Decimal("450.50"))
    assert part.total_cost == Decimal("901.00")
    with pytest.raises(IntegrityError), transaction.atomic():
        PartUsedFactory(quantity=Decimal("0"))


def test_vehicle_with_history_cannot_be_deleted():
    """Fleet.Retire: maintenance history is retained."""
    job = MaintenanceJobFactory()
    with pytest.raises(ProtectedError):
        job.vehicle.delete()
