"""Maintenance models (SRS 3.6; Appendix A maintenance job; BR-15, BR-16).

Owner: Nidhi (WBS 1.4.4). Only the owner edits this file or its migrations.
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

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
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="maintenance_reported",
        help_text="Empty for a Preventive job the system raised (Maint.Auto.Km, Maint.Auto.Time).",
    )
    # UC 9 extension 2a: the BR-15 due point an automatic Preventive job was raised for.
    due_odometer = models.PositiveIntegerField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    # Maint.Schedule: the period blocked from search and booking.
    scheduled_from = models.DateTimeField(null=True, blank=True)
    scheduled_to = models.DateTimeField(null=True, blank=True)
    # Maint.Record: required on completion.
    service_date = models.DateField(null=True, blank=True)
    odometer_at_service = models.PositiveIntegerField(null=True, blank=True)
    work_description = models.TextField(blank=True)
    labour_cost = _money(default=0)
    workshop_invoice = models.FileField(upload_to="maintenance/invoices/", blank=True)
    # Maint.History "downtime": entered by the technician with the record.
    downtime_hours = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    # Appendix B Scheduled -> In Progress.
    started_at = models.DateTimeField(null=True, blank=True)
    # Exp 4 sequence 3, BR-16: the technician completed the work on an Unsafe
    # vehicle and the job waits for an Administrator to clear the flag.
    clearance_requested_at = models.DateTimeField(null=True, blank=True)
    # BR-16, Maint.Unsafe: only an Administrator or authorised technician
    # closes a job, and that user is recorded. When a clearance is approved
    # this is the approving Administrator.
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="maintenance_closed",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    # Appendix B Cancelled: who cancelled the job, when and why.
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="maintenance_cancelled",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(blank=True)

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
            models.CheckConstraint(
                condition=Q(downtime_hours__isnull=True) | Q(downtime_hours__gte=0),
                name="maintenance_downtime_not_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"Job {self.job_id} ({self.job_type}, {self.status})"

    @property
    def awaiting_clearance(self) -> bool:
        """BR-16: work is complete and an Administrator must clear the Unsafe flag."""
        return self.status == self.Status.IN_PROGRESS and self.clearance_requested_at is not None

    # Exp 3 class-diagram methods; the logic is in services.py.

    def schedule_job(self, *, technician, scheduled_from, scheduled_to, actor, **kwargs):
        """Exp 3 MaintenanceJob.schedule_job(): Reported -> Scheduled (Maint.Schedule)."""
        from .services import schedule_job

        return schedule_job(
            self.pk,
            actor,
            technician=technician,
            scheduled_from=scheduled_from,
            scheduled_to=scheduled_to,
            **kwargs,
        )

    def complete_job(self, *, actor, request=None):
        """Exp 3 MaintenanceJob.complete_job(): Exp 4 sequence diagram 3."""
        from .services import complete_job

        return complete_job(self.pk, actor, request=request)


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


class UnsafeClearanceAuthorisation(models.Model):
    """BR-16, SA-3, SE-6: a technician an Administrator has authorised to clear an
    Unsafe flag. One row per authorised technician; revoking deletes it, and the
    audit log keeps both decisions."""

    technician = models.OneToOneField(
        "accounts.MaintenanceTechnician",
        on_delete=models.CASCADE,
        related_name="unsafe_clearance_authorisation",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    granted_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return f"{self.technician} may clear Unsafe flags"
