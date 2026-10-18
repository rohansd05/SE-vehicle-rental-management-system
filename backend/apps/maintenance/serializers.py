"""Maintenance API serializers. Money and quantities are Decimals sent as strings (CO-6)."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import MaintenanceTechnician
from apps.core.files import signed_file_url
from apps.core.validators import validate_image_upload
from apps.fleet.models import Vehicle
from apps.fleet.services.status import may_clear_unsafe

from . import services
from .models import MaintenanceJob, PartUsed


class NextServiceDueSerializer(serializers.Serializer):
    """BR-15: whichever comes first."""

    odometer = serializers.IntegerField(allow_null=True)
    date = serializers.DateField(allow_null=True)


class MaintenanceVehicleSerializer(serializers.ModelSerializer):
    vehicle_type = serializers.CharField(read_only=True)
    category = serializers.CharField(source="category.name", read_only=True)
    home_branch = serializers.CharField(source="home_branch.branch_name", read_only=True)
    next_service_due = serializers.SerializerMethodField()
    service_overdue = serializers.SerializerMethodField(
        help_text="BR-15, SA-2: the service is due by distance or date; no handover until done."
    )

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "registration_no",
            "brand",
            "model",
            "status",
            "vehicle_type",
            "category",
            "home_branch",
            "home_branch_id",
            "odometer",
            "last_service_date",
            "last_service_odometer",
            "next_service_due",
            "service_overdue",
        ]
        read_only_fields = fields

    @extend_schema_field(NextServiceDueSerializer)
    def get_next_service_due(self, vehicle) -> dict:
        return NextServiceDueSerializer(services.next_service_due(vehicle)).data

    def get_service_overdue(self, vehicle) -> bool:
        return services.service_due(vehicle) is not None


class TechnicianSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.name", read_only=True)
    authorised_to_clear_unsafe = serializers.SerializerMethodField(help_text="BR-16")

    class Meta:
        model = MaintenanceTechnician
        fields = ["technician_id", "name", "workshop", "authorised_to_clear_unsafe"]
        read_only_fields = fields

    def get_authorised_to_clear_unsafe(self, technician) -> bool:
        return hasattr(technician, "unsafe_clearance_authorisation")


class PartUsedSerializer(serializers.ModelSerializer):
    total_cost = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = PartUsed
        fields = ["id", "part_name", "quantity", "unit_cost", "total_cost"]
        read_only_fields = fields


class MaintenanceJobSerializer(serializers.ModelSerializer):
    vehicle = MaintenanceVehicleSerializer(read_only=True)
    technician = TechnicianSerializer(read_only=True, allow_null=True)
    reported_by = serializers.CharField(
        source="reported_by.name",
        read_only=True,
        default=None,
        allow_null=True,
        help_text="Empty for a Preventive job the system raised (Maint.Auto.Km, Maint.Auto.Time).",
    )
    closed_by = serializers.CharField(
        source="closed_by.name", read_only=True, default=None, allow_null=True
    )
    cancelled_by = serializers.CharField(
        source="cancelled_by.name", read_only=True, default=None, allow_null=True
    )
    workshop_invoice_url = serializers.SerializerMethodField(
        help_text="Maint.Record: a signed link to the attached workshop invoice (SI-3)."
    )
    can_clear_unsafe = serializers.SerializerMethodField(
        help_text="BR-16: the caller may clear the vehicle's Unsafe flag while closing the job."
    )
    parts = PartUsedSerializer(many=True, read_only=True)
    awaiting_clearance = serializers.BooleanField(read_only=True)
    missing_work = serializers.SerializerMethodField(
        help_text="Maint.Record items still to record; empty when the job can be completed."
    )

    class Meta:
        model = MaintenanceJob
        fields = [
            "job_id",
            "job_type",
            "severity",
            "status",
            "vehicle",
            "technician",
            "reported_problem",
            "reported_by",
            "due_odometer",
            "due_date",
            "scheduled_from",
            "scheduled_to",
            "started_at",
            "service_date",
            "odometer_at_service",
            "work_description",
            "labour_cost",
            "downtime_hours",
            "total_cost",
            "parts",
            "missing_work",
            "awaiting_clearance",
            "clearance_requested_at",
            "closed_by",
            "closed_at",
            "cancelled_by",
            "cancelled_at",
            "cancel_reason",
            "workshop_invoice_url",
            "can_clear_unsafe",
            "created_at",
        ]
        read_only_fields = fields

    def get_missing_work(self, job) -> list[str]:
        if job.status != MaintenanceJob.Status.IN_PROGRESS:
            return []
        return services.missing_work(job)

    def get_workshop_invoice_url(self, job) -> str | None:
        return signed_file_url(job.workshop_invoice, self.context.get("request"))

    def get_can_clear_unsafe(self, job) -> bool:
        request = self.context.get("request")
        if request is None:
            return False
        if "can_clear_unsafe" not in self.context:  # one lookup per response
            self.context["can_clear_unsafe"] = may_clear_unsafe(request.user)
        return self.context["can_clear_unsafe"]


# ─── Requests ─────────────────────────────────────────────────────────────


class ReportJobSerializer(serializers.Serializer):
    """Maint.Create; Maint.Unsafe (flag_unsafe)."""

    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all())
    job_type = serializers.ChoiceField(choices=MaintenanceJob.JobType.choices)
    severity = serializers.ChoiceField(choices=MaintenanceJob.Severity.choices)
    reported_problem = serializers.CharField(max_length=2000)
    flag_unsafe = serializers.BooleanField(default=False)


class ScheduleJobSerializer(serializers.Serializer):
    """Maint.Schedule, Maint.Conflict."""

    technician = serializers.PrimaryKeyRelatedField(
        queryset=MaintenanceTechnician.objects.select_related("user")
    )
    scheduled_from = serializers.DateTimeField()
    scheduled_to = serializers.DateTimeField()
    confirm_conflicts = serializers.BooleanField(default=False)


class PartInputSerializer(serializers.Serializer):
    part_name = serializers.CharField(max_length=150)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    unit_cost = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))


class RecordWorkSerializer(serializers.Serializer):
    """Maint.Record."""

    service_date = serializers.DateField()
    odometer_at_service = serializers.IntegerField(min_value=0)
    work_description = serializers.CharField(max_length=5000)
    labour_cost = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))
    downtime_hours = serializers.DecimalField(
        max_digits=7, decimal_places=2, min_value=Decimal("0")
    )
    parts = PartInputSerializer(many=True, allow_empty=True)


class CancelJobSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)


class CompleteJobSerializer(serializers.Serializer):
    """BR-16, UC 10 extension 1a: an Administrator or an authorised technician may
    clear the Unsafe flag as part of closing the job."""

    clear_unsafe = serializers.BooleanField(default=False)


def _workshop_invoice(upload):
    """Maint.Record invoice: a PDF (checked by its header) or an image (Pillow, D3)."""
    extension = upload.name.rsplit(".", 1)[-1].lower() if "." in (upload.name or "") else ""
    if extension not in settings.WORKSHOP_INVOICE_EXTENSIONS:
        raise serializers.ValidationError("Upload the invoice as a PDF, JPG or PNG file.")
    if upload.size > settings.WORKSHOP_INVOICE_MAX_BYTES:
        limit = settings.WORKSHOP_INVOICE_MAX_BYTES // (1024 * 1024)
        raise serializers.ValidationError(f"The file is larger than {limit} MB.")
    if extension == "pdf":
        upload.seek(0)
        header = upload.read(5)
        upload.seek(0)
        if header != b"%PDF-":
            raise serializers.ValidationError("The file is not a valid PDF.")
        return upload
    try:
        validate_image_upload(
            upload,
            extensions=tuple(e for e in settings.WORKSHOP_INVOICE_EXTENSIONS if e != "pdf"),
            max_bytes=settings.WORKSHOP_INVOICE_MAX_BYTES,
        )
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.messages) from exc
    return upload


class WorkshopInvoiceSerializer(serializers.Serializer):
    """Maint.Record "permit the workshop invoice to be attached", as multipart/form-data."""

    workshop_invoice = serializers.FileField(validators=[_workshop_invoice])


class ConflictBookingSerializer(serializers.Serializer):
    booking_reference = serializers.CharField()
    pickup_datetime = serializers.DateTimeField()
    return_datetime = serializers.DateTimeField()


class ScheduleConflictSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField()
    bookings = ConflictBookingSerializer(many=True)


class WorkIncompleteSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField()
    missing = serializers.ListField(child=serializers.CharField())
