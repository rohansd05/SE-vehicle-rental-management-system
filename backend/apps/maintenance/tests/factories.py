"""factory-boy factories for maintenance."""

from decimal import Decimal

import factory

from apps.accounts.tests.factories import MaintenanceTechnicianFactory, UserFactory
from apps.fleet.tests.factories import CarFactory
from apps.maintenance.models import MaintenanceJob, PartUsed


class MaintenanceJobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = MaintenanceJob

    job_type = MaintenanceJob.JobType.CORRECTIVE
    severity = MaintenanceJob.Severity.MEDIUM
    vehicle = factory.SubFactory(CarFactory)
    technician = factory.SubFactory(MaintenanceTechnicianFactory)
    reported_problem = "Brake pedal feels soft."
    reported_by = factory.SubFactory(UserFactory)


class PartUsedFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PartUsed

    job = factory.SubFactory(MaintenanceJobFactory)
    part_name = "Brake pads (front)"
    quantity = Decimal("1.00")
    unit_cost = Decimal("1450.00")
