"""Notifications admin registrations: a view-only delivery log."""

from django.contrib import admin

from apps.core.admin import ReadOnlyModelAdmin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(ReadOnlyModelAdmin):
    list_display = ("queued_at", "recipient", "channel", "template", "status", "attempt_count")
    list_filter = ("channel", "status", "template")
    search_fields = ("recipient__email", "destination", "provider_message_id")
    date_hierarchy = "queued_at"
