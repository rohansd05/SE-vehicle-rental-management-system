"""Core admin: shared admin mixins and the read-only audit log.

Fleet.Audit / CLAUDE.md: every create, update and delete of vehicle, tariff,
branch, user and blacklist data writes an AuditLog entry. AuditedModelAdmin
does this for changes made through the Django admin, inline rows included.
"""

from django.conf import settings
from django.contrib import admin

from .audit import record_audit, snapshot
from .models import AuditLog

# D7: the agency name comes only from settings.
admin.site.site_header = f"{settings.AGENCY_NAME} — VRMS administration"
admin.site.site_title = "VRMS administration"
admin.site.index_title = "Vehicle Rental Management System"


def record_change(request, action: str, obj, before: dict | None, after: dict | None) -> None:
    record_audit(request.user, action, obj, before, after, request)


def _stored_snapshot(obj) -> dict | None:
    if obj.pk is None:
        return None
    stored = type(obj)._base_manager.filter(pk=obj.pk).first()
    return snapshot(stored) if stored is not None else None


class AuditedModelAdmin(admin.ModelAdmin):
    """Writes an AuditLog entry for every admin create, update and delete."""

    def save_model(self, request, obj, form, change):
        before = _stored_snapshot(obj) if change else None
        super().save_model(request, obj, form, change)
        record_change(request, "Update" if change else "Create", obj, before, snapshot(obj))

    def delete_model(self, request, obj):
        before = snapshot(obj)
        pk = obj.pk
        super().delete_model(request, obj)
        obj.pk = pk
        record_change(request, "Delete", obj, before, None)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self.delete_model(request, obj)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            before = snapshot(obj)
            pk = obj.pk
            obj.delete()
            obj.pk = pk
            record_change(request, "Delete", obj, before, None)
        for obj in instances:
            adding = obj._state.adding
            before = None if adding else _stored_snapshot(obj)
            obj.save()
            record_change(request, "Create" if adding else "Update", obj, before, snapshot(obj))
        formset.save_m2m()


class ReadOnlyModelAdmin(admin.ModelAdmin):
    """View-only admin for append-only and log tables: no add, change or delete."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ReadOnlyTabularInline(admin.TabularInline):
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyModelAdmin):
    list_display = ("timestamp", "actor", "action", "entity_type", "entity_id", "ip_address")
    list_filter = ("action", "entity_type")
    search_fields = ("entity_type", "entity_id", "actor__email")
    date_hierarchy = "timestamp"
