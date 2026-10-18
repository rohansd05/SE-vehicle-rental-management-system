"""Reports API routes, mounted under /api/v1/reports/."""

from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("summary/", views.DashboardView.as_view(), name="summary"),
    path("utilisation/", views.UtilisationReportView.as_view(), name="utilisation"),
    path("revenue/", views.RevenueReportView.as_view(), name="revenue"),
    path("maintenance/", views.MaintenanceReportView.as_view(), name="maintenance"),
    path("customers/", views.CustomerReportView.as_view(), name="customers"),
]
