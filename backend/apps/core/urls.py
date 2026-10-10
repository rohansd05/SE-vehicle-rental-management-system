"""Core API routes, mounted under /api/v1/."""

from django.urls import path

from .files import SignedFileView
from .views import HealthView

app_name = "core"

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("files/<str:token>/", SignedFileView.as_view(), name="signed-file"),
]
