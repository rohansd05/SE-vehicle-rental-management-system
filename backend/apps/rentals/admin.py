"""Rentals admin registrations.

Condition reports (handover and return) and their photographs are view-only:
only the handover and return flows write them, after their checks, and a
signed report can never change (Handover.Sign, append-only).
"""

from django.contrib import admin

from apps.core.admin import ReadOnlyModelAdmin, ReadOnlyTabularInline

from .models import ConditionPhoto, ConditionReport


class ConditionPhotoInline(ReadOnlyTabularInline):
    model = ConditionPhoto


@admin.register(ConditionReport)
class ConditionReportAdmin(ReadOnlyModelAdmin):
    """Handover.Sign: view-only, signed or not."""

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
    inlines = [ConditionPhotoInline]


@admin.register(ConditionPhoto)
class ConditionPhotoAdmin(ReadOnlyModelAdmin):
    list_display = ("report", "caption", "uploaded_at")
    search_fields = ("report__booking__booking_reference",)
