"""Rentals admin registrations."""

from django.contrib import admin

from apps.core.admin import AuditedModelAdmin

from .models import ConditionPhoto, ConditionReport


class ConditionPhotoInline(admin.TabularInline):
    model = ConditionPhoto
    extra = 0


def _is_signed(report) -> bool:
    return report is not None and report.is_signed_in_db


@admin.register(ConditionReport)
class ConditionReportAdmin(AuditedModelAdmin):
    """Handover.Sign: a signed report is view-only."""

    list_display = (
        "booking",
        "report_type",
        "odometer_reading",
        "fuel_level",
        "recorded_by",
        "recorded_at",
        "signed_at",
    )
    list_filter = ("report_type",)
    search_fields = ("booking__booking_reference",)
    raw_id_fields = ("booking", "recorded_by", "odometer_override_by")
    inlines = [ConditionPhotoInline]

    def has_change_permission(self, request, obj=None):
        return not _is_signed(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not _is_signed(obj) and super().has_delete_permission(request, obj)


@admin.register(ConditionPhoto)
class ConditionPhotoAdmin(AuditedModelAdmin):
    list_display = ("report", "caption", "uploaded_at")
    search_fields = ("report__booking__booking_reference",)

    def has_change_permission(self, request, obj=None):
        report = obj.report if obj is not None else None
        return not _is_signed(report) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        report = obj.report if obj is not None else None
        return not _is_signed(report) and super().has_delete_permission(request, obj)
