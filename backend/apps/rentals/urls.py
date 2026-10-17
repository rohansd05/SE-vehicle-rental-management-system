"""Rentals API routes, mounted under /api/v1/rentals/."""

from django.urls import path

from . import views

app_name = "rentals"

urlpatterns = [
    path("branch-bookings/", views.BranchBookingListView.as_view(), name="branch-bookings"),
    path("handovers/<int:pk>/", views.HandoverDetailView.as_view(), name="handover-detail"),
    path(
        "handovers/<int:pk>/complete/",
        views.HandoverCompleteView.as_view(),
        name="handover-complete",
    ),
    path("returns/", views.ReturnListView.as_view(), name="returns"),
    path("returns/<int:pk>/", views.ReturnDetailView.as_view(), name="return-detail"),
    path("returns/<int:pk>/quote/", views.ReturnQuoteView.as_view(), name="return-quote"),
    path("returns/<int:pk>/complete/", views.ReturnCompleteView.as_view(), name="return-complete"),
]
