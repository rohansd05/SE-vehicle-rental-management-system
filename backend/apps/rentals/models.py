"""Rental models: handover and return condition reports (SRS 3.3).

Owner: Nidhi (WBS 1.4.4). Only the owner edits this file or its migrations.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.exceptions import ImmutableRecordError
from apps.core.models import TimeStampedModel


class ConditionReport(TimeStampedModel):
    """Exp 3 ConditionReport; Appendix A condition report.

    Booking ◆ ConditionReport (0..2): at most one Handover and one Return
    report per booking. Handover.Sign: once the customer's signature is
    stored the report "cannot subsequently be altered", so save() and
    delete() refuse any change to a signed report.
    """

    class ReportType(models.TextChoices):
        HANDOVER = "Handover", "Handover"
        RETURN = "Return", "Return"

    booking = models.ForeignKey(
        "bookings.Booking", on_delete=models.PROTECT, related_name="condition_reports"
    )
    report_type = models.CharField(max_length=16, choices=ReportType.choices)
    odometer_reading = models.PositiveIntegerField()  # whole km (Appendix A)
    # Exp 3 fuel_level (double) -> fixed-point percentage of a full tank or charge.
    fuel_level = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percent of a full tank or battery.",
    )
    # Exp 3 signature; SI-3: the stored object key of the signature image.
    signature = models.FileField(upload_to="rentals/signatures/", blank=True)
    signed_at = models.DateTimeField(null=True, blank=True)
    # BranchStaff–ConditionReport association (Exp 3); Appendix A recorded by/at.
    recorded_by = models.ForeignKey(
        "accounts.BranchStaff", on_delete=models.PROTECT, related_name="condition_reports"
    )
    recorded_at = models.DateTimeField(default=timezone.now)
    # Handover.Checklist / Return.Checklist: accessories issued or returned.
    accessories = models.JSONField(default=list, blank=True)
    # Appendix A 0:m damage mark; Handover.Checklist "marked on a diagram".
    damage_marks = models.JSONField(default=list, blank=True)
    # Return.Odometer: supervisor override when the distance is implausible.
    odometer_override_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="odometer_overrides",
    )
    odometer_override_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["booking", "recorded_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["booking", "report_type"], name="rentals_one_report_per_type"
            ),
            models.CheckConstraint(
                condition=Q(fuel_level__gte=0) & Q(fuel_level__lte=100),
                name="rentals_fuel_level_percent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.report_type} report for {self.booking}"

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance._stored_signature = instance.__dict__.get("signature") or ""
        return instance

    def save(self, *args, **kwargs):
        if not self._state.adding and self.is_signed_in_db:
            raise ImmutableRecordError(
                "Handover.Sign: a signed condition report cannot be altered."
            )
        super().save(*args, **kwargs)
        self._stored_signature = self.signature.name if self.signature else ""

    def delete(self, *args, **kwargs):
        if self.is_signed_in_db:
            raise ImmutableRecordError(
                "Handover.Sign: a signed condition report cannot be deleted."
            )
        return super().delete(*args, **kwargs)

    @property
    def is_signed_in_db(self) -> bool:
        stored = getattr(self, "_stored_signature", "")
        return bool(str(stored))


class ConditionPhoto(models.Model):
    """A photograph in a condition report (Handover.Checklist: at least four).

    SI-3: only the object key is stored. Part of the signed document, so a
    signed report's photographs cannot be added, changed or removed.
    """

    report = models.ForeignKey(ConditionReport, on_delete=models.CASCADE, related_name="photos")
    image = models.FileField(upload_to="rentals/photos/")
    caption = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["report", "uploaded_at"]

    def __str__(self) -> str:
        return f"Photo of {self.report}"

    def save(self, *args, **kwargs):
        self._refuse_if_signed()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._refuse_if_signed()
        return super().delete(*args, **kwargs)

    def _refuse_if_signed(self) -> None:
        signed = ConditionReport.objects.filter(pk=self.report_id).exclude(signature="").exists()
        if signed:
            raise ImmutableRecordError(
                "Handover.Sign: a signed condition report cannot be altered."
            )
