"""Maintenance admin registrations."""

from django.contrib import admin

from apps.core.admin import AuditedModelAdmin

from .models import MaintenanceJob, PartUsed


class PartUsedInline(admin.TabularInline):
    model = PartUsed
    extra = 0


@admin.register(MaintenanceJob)
class MaintenanceJobAdmin(AuditedModelAdmin):
    list_display = (
        "job_id",
        "vehicle",
        "job_type",
        "severity",
        "status",
        "technician",
        "scheduled_from",
        "total_cost",
    )
    list_filter = ("status", "job_type", "severity")
    search_fields = ("vehicle__registration_no", "reported_problem")
    raw_id_fields = ("vehicle", "reported_by", "closed_by")
    inlines = [PartUsedInline]


@admin.register(PartUsed)
class PartUsedAdmin(AuditedModelAdmin):
    list_display = ("job", "part_name", "quantity", "unit_cost")
    search_fields = ("part_name",)
