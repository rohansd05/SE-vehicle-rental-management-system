"""Accounts admin registrations."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from apps.core.admin import AuditedModelAdmin, ReadOnlyModelAdmin

from .models import (
    Administrator,
    BranchManager,
    BranchStaff,
    Customer,
    Licence,
    LicenceCategory,
    MaintenanceTechnician,
    OneTimePassword,
    User,
)


class UserCreationAdminForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "name", "mobile_no", "role")


class UserChangeAdminForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(AuditedModelAdmin, DjangoUserAdmin):
    form = UserChangeAdminForm
    add_form = UserCreationAdminForm

    list_display = ("email", "name", "mobile_no", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "name", "mobile_no")
    ordering = ("email",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("name", "mobile_no", "address", "role")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "name",
                    "mobile_no",
                    "role",
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(Customer)
class CustomerAdmin(AuditedModelAdmin):
    list_display = ("customer_id", "user", "date_of_birth", "is_blacklisted", "outstanding_due")
    list_filter = ("is_blacklisted",)
    search_fields = ("user__email", "user__name", "user__mobile_no")
    autocomplete_fields = ("user",)


@admin.register(BranchStaff)
class BranchStaffAdmin(AuditedModelAdmin):
    list_display = ("staff_id", "user", "branch")
    list_filter = ("branch",)
    search_fields = ("user__email", "user__name")
    autocomplete_fields = ("user",)


@admin.register(MaintenanceTechnician)
class MaintenanceTechnicianAdmin(AuditedModelAdmin):
    list_display = ("technician_id", "user", "workshop")
    search_fields = ("user__email", "user__name", "workshop")
    autocomplete_fields = ("user",)


@admin.register(Administrator)
class AdministratorAdmin(AuditedModelAdmin):
    list_display = ("admin_id", "user")
    search_fields = ("user__email", "user__name")
    autocomplete_fields = ("user",)


@admin.register(BranchManager)
class BranchManagerAdmin(AuditedModelAdmin):
    list_display = ("admin_id", "user", "branch")
    list_filter = ("branch",)
    search_fields = ("user__email", "user__name")
    autocomplete_fields = ("user",)


class LicenceCategoryInline(admin.TabularInline):
    model = LicenceCategory
    extra = 0


@admin.register(Licence)
class LicenceAdmin(AuditedModelAdmin):
    list_display = ("licence_number", "customer", "status", "expiry_date", "verified_by")
    list_filter = ("status",)
    search_fields = ("licence_number", "customer__user__email", "customer__user__name")
    inlines = [LicenceCategoryInline]
    raw_id_fields = ("customer", "verified_by")


@admin.register(LicenceCategory)
class LicenceCategoryAdmin(AuditedModelAdmin):
    list_display = ("licence", "category")
    list_filter = ("category",)
    search_fields = ("licence__licence_number",)


@admin.register(OneTimePassword)
class OneTimePasswordAdmin(ReadOnlyModelAdmin):
    list_display = ("user", "purpose", "destination", "expires_at", "attempt_count", "consumed_at")
    list_filter = ("purpose",)
    search_fields = ("user__email", "destination")
    exclude = ("code_hash",)
