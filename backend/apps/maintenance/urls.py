"""Maintenance API routes, mounted under /api/v1/maintenance/."""

from django.urls import path

from . import views

app_name = "maintenance"

urlpatterns = [
    path("jobs/", views.JobListCreateView.as_view(), name="job-list"),
    path("jobs/<int:pk>/", views.JobDetailView.as_view(), name="job-detail"),
    path("jobs/<int:pk>/schedule/", views.JobScheduleView.as_view(), name="job-schedule"),
    path("jobs/<int:pk>/cancel/", views.JobCancelView.as_view(), name="job-cancel"),
    path("jobs/<int:pk>/start/", views.JobStartView.as_view(), name="job-start"),
    path("jobs/<int:pk>/record/", views.JobRecordView.as_view(), name="job-record"),
    path("jobs/<int:pk>/complete/", views.JobCompleteView.as_view(), name="job-complete"),
    path(
        "jobs/<int:pk>/approve-clearance/",
        views.ApproveClearanceView.as_view(),
        name="job-approve-clearance",
    ),
    path("clearances/", views.ClearanceQueueView.as_view(), name="clearance-queue"),
    path("technicians/", views.TechnicianListView.as_view(), name="technician-list"),
    path("vehicles/", views.VehicleListView.as_view(), name="vehicle-list"),
    path("vehicles/<int:pk>/history/", views.VehicleHistoryView.as_view(), name="vehicle-history"),
]
