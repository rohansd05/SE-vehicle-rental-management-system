"""Core API routes, mounted under /api/v1/."""

from django.urls import path

from .files import SignedFileView
from .views import AuditFilterOptionsView, AuditLogListView, HealthView

app_name = "core"

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("files/<str:token>/", SignedFileView.as_view(), name="signed-file"),
    path("audit/", AuditLogListView.as_view(), name="audit-log"),
    path("audit/filters/", AuditFilterOptionsView.as_view(), name="audit-filters"),
]
