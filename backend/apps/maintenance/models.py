"""Maintenance models (SRS 3.6; Appendix A maintenance job; BR-15, BR-16).

Owner: Nidhi (WBS 1.4.4). Only the owner edits this file or its migrations.
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.core.models import TimeStampedModel


def _money(**kwargs) -> models.DecimalField:
    return models.DecimalField(max_digits=12, decimal_places=2, **kwargs)


class MaintenanceJob(TimeStampedModel):
    """Exp 3 MaintenanceJob."""

    class JobType(models.TextChoices):  # Maint.Create
        PREVENTIVE = "Preventive", "Preventive"
        CORRECTIVE = "Corrective", "Corrective"
        INSPECTION = "Inspection", "Inspection"
        CLEANING = "Cleaning", "Cleaning"
        DOCUMENTATION = "Documentation", "Documentation"

    class Severity(models.TextChoices):  # values proposed; the SRS names no scale
        LOW = "Low", "Low"
        MEDIUM = "Medium", "Medium"
        HIGH = "High", "High"
        CRITICAL = "Critical", "Critical"

    class Status(models.TextChoices):  # Maint.Status, Appendix B
        REPORTED = "Reported", "Reported"
        SCHEDULED = "Scheduled", "Scheduled"
        IN_PROGRESS = "In Progress", "In Progress"
        COMPLETED = "Completed", "Completed"
        CANCELLED = "Cancelled", "Cancelled"

    job_id = models.BigAutoField(primary_key=True)
    job_type = models.CharField(max_length=16, choices=JobType.choices)
    severity = models.CharField(max_length=16, choices=Severity.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REPORTED)
    total_cost = _money(default=0)
    # Vehicle–MaintenanceJob and MaintenanceTechnician–MaintenanceJob (Exp 3).
    vehicle = models.ForeignKey(
        "fleet.Vehicle", on_delete=models.PROTECT, related_name="maintenance_jobs"
    )
    technician = models.ForeignKey(  # Appendix A "assigned to"
        "accounts.MaintenanceTechnician",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="maintenance_jobs",
    )
    reported_problem = models.TextField()  # Maint.Create
    reported_by = models.ForeignKey(  # Maint.Create "the reporting user"
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="maintenance_reported"
    )
    # Maint.Schedule: the period blocked from search and booking.
    scheduled_from = models.DateTimeField(null=True, blank=True)
    scheduled_to = models.DateTimeField(null=True, blank=True)
    # Maint.Record: required on completion.
    service_date = models.DateField(null=True, blank=True)
    odometer_at_service = models.PositiveIntegerField(null=True, blank=True)
    work_description = models.TextField(blank=True)
    labour_cost = _money(default=0)
    workshop_invoice = models.FileField(upload_to="maintenance/invoices/", blank=True)
    # BR-16, Maint.Unsafe: only an Administrator or authorised technician
    # closes a job, and that user is recorded.
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="maintenance_closed",
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["vehicle", "status"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(scheduled_from__isnull=True)
                | Q(scheduled_to__isnull=True)
                | Q(scheduled_to__gt=F("scheduled_from")),
                name="maintenance_schedule_ends_after_start",
            ),
            models.CheckConstraint(
                condition=Q(total_cost__gte=0) & Q(labour_cost__gte=0),
                name="maintenance_costs_not_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"Job {self.job_id} ({self.job_type}, {self.status})"


class PartUsed(models.Model):
    """Maint.Record: each part replaced with its quantity and cost."""

    job = models.ForeignKey(MaintenanceJob, on_delete=models.CASCADE, related_name="parts")
    part_name = models.CharField(max_length=150)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_cost = _money()

    class Meta:
        verbose_name_plural = "parts used"
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0) & Q(unit_cost__gte=0),
                name="maintenance_part_quantity_and_cost",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.part_name} x{self.quantity} (job {self.job_id})"

    @property
    def total_cost(self):
        return self.quantity * self.unit_cost
