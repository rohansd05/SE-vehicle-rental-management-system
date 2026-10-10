"""Pricing admin registrations."""

from django.contrib import admin

from apps.core.admin import AuditedModelAdmin

from .models import AddOn, DiscountCode, FuelPrice, Tariff


@admin.register(Tariff)
class TariffAdmin(AuditedModelAdmin):
    """BR-13: a tariff in effect is view-only; a change is a new tariff."""

    list_display = (
        "vehicle_category",
        "hourly_rate",
        "daily_rate",
        "weekly_rate",
        "security_deposit",
        "free_km_allowance",
        "excess_km_rate",
        "effective_from",
        "defined_by",
    )
    list_filter = ("vehicle_category",)
    date_hierarchy = "effective_from"

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        administrator = getattr(request.user, "administrator", None)
        if administrator is not None:
            initial.setdefault("defined_by", administrator.pk)
        return initial

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj._has_taken_effect():
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj._has_taken_effect():
            return False
        return super().has_delete_permission(request, obj)


@admin.register(AddOn)
class AddOnAdmin(AuditedModelAdmin):
    list_display = ("name", "daily_rate", "vehicle_type", "is_active")
    list_filter = ("is_active", "vehicle_type")
    search_fields = ("name",)


@admin.register(FuelPrice)
class FuelPriceAdmin(AuditedModelAdmin):
    list_display = ("fuel_type", "price_per_unit", "effective_from", "defined_by")
    list_filter = ("fuel_type",)
    date_hierarchy = "effective_from"


@admin.register(DiscountCode)
class DiscountCodeAdmin(AuditedModelAdmin):
    list_display = (
        "code",
        "discount_type",
        "value",
        "valid_from",
        "valid_to",
        "is_active",
        "times_used",
        "usage_limit",
    )
    list_filter = ("discount_type", "is_active")
    search_fields = ("code",)
    readonly_fields = ("times_used",)
