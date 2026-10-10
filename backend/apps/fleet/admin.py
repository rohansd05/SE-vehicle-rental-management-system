"""Fleet admin registrations."""

from django.contrib import admin

from apps.core.admin import AuditedModelAdmin

from .models import (
    Branch,
    BranchServiceableArea,
    Car,
    TwoWheeler,
    Vehicle,
    VehicleCategory,
    VehicleDocument,
    VehiclePhoto,
)


class ServiceableAreaInline(admin.TabularInline):
    model = BranchServiceableArea
    extra = 0


@admin.register(Branch)
class BranchAdmin(AuditedModelAdmin):
    list_display = ("branch_id", "branch_name", "address")
    search_fields = ("branch_name", "address", "serviceable_areas__pincode")
    inlines = [ServiceableAreaInline]


@admin.register(BranchServiceableArea)
class BranchServiceableAreaAdmin(AuditedModelAdmin):
    list_display = ("branch", "pincode", "locality")
    list_filter = ("branch",)
    search_fields = ("pincode", "locality")


@admin.register(VehicleCategory)
class VehicleCategoryAdmin(AuditedModelAdmin):
    list_display = ("name", "vehicle_type")
    list_filter = ("vehicle_type",)
    search_fields = ("name",)


class VehicleDocumentInline(admin.TabularInline):
    model = VehicleDocument
    extra = 0


class VehiclePhotoInline(admin.TabularInline):
    model = VehiclePhoto
    extra = 0


VEHICLE_LIST_DISPLAY = (
    "registration_no",
    "brand",
    "model",
    "category",
    "home_branch",
    "status",
    "odometer",
)
VEHICLE_LIST_FILTER = ("status", "home_branch", "category", "fuel_type")
VEHICLE_SEARCH = ("registration_no", "chassis_number", "brand", "model")


@admin.register(Vehicle)
class VehicleAdmin(AuditedModelAdmin):
    """All vehicles. New vehicles are added as a Car or a TwoWheeler."""

    list_display = VEHICLE_LIST_DISPLAY
    list_filter = VEHICLE_LIST_FILTER
    search_fields = VEHICLE_SEARCH
    inlines = [VehicleDocumentInline, VehiclePhotoInline]

    def has_add_permission(self, request):
        return False


@admin.register(Car)
class CarAdmin(AuditedModelAdmin):
    list_display = (*VEHICLE_LIST_DISPLAY, "transmission", "seating_capacity")
    list_filter = (*VEHICLE_LIST_FILTER, "transmission")
    search_fields = VEHICLE_SEARCH
    inlines = [VehicleDocumentInline, VehiclePhotoInline]


@admin.register(TwoWheeler)
class TwoWheelerAdmin(AuditedModelAdmin):
    list_display = (*VEHICLE_LIST_DISPLAY, "engine_cc")
    list_filter = VEHICLE_LIST_FILTER
    search_fields = VEHICLE_SEARCH
    inlines = [VehicleDocumentInline, VehiclePhotoInline]


@admin.register(VehicleDocument)
class VehicleDocumentAdmin(AuditedModelAdmin):
    list_display = ("vehicle", "document_type", "document_number", "expiry_date")
    list_filter = ("document_type",)
    search_fields = ("vehicle__registration_no", "document_number")
    date_hierarchy = "expiry_date"


@admin.register(VehiclePhoto)
class VehiclePhotoAdmin(AuditedModelAdmin):
    list_display = ("vehicle", "position", "image", "uploaded_at")
    search_fields = ("vehicle__registration_no",)
