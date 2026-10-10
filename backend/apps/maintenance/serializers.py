"""Maintenance API serializers. Money and quantities are Decimals sent as strings (CO-6)."""

from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import MaintenanceTechnician
from apps.fleet.models import Vehicle

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
        ]
        read_only_fields = fields

    @extend_schema_field(NextServiceDueSerializer)
    def get_next_service_due(self, vehicle) -> dict:
        return NextServiceDueSerializer(services.next_service_due(vehicle)).data


class TechnicianSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.name", read_only=True)

    class Meta:
        model = MaintenanceTechnician
        fields = ["technician_id", "name", "workshop"]
        read_only_fields = fields


class PartUsedSerializer(serializers.ModelSerializer):
    total_cost = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = PartUsed
        fields = ["id", "part_name", "quantity", "unit_cost", "total_cost"]
        read_only_fields = fields


class MaintenanceJobSerializer(serializers.ModelSerializer):
    vehicle = MaintenanceVehicleSerializer(read_only=True)
    technician = TechnicianSerializer(read_only=True)
    reported_by = serializers.CharField(source="reported_by.name", read_only=True)
    closed_by = serializers.CharField(source="closed_by.name", read_only=True, default=None)
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
            "created_at",
        ]
        read_only_fields = fields

    def get_missing_work(self, job) -> list[str]:
        if job.status != MaintenanceJob.Status.IN_PROGRESS:
            return []
        return services.missing_work(job)


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
