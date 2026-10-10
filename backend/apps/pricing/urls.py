"""Pricing API routes, mounted under /api/v1/pricing/."""

from django.urls import path

from . import views

app_name = "pricing"

urlpatterns = [
    path("add-ons/", views.AddOnListView.as_view(), name="add-on-list"),
    path("quote/", views.QuoteView.as_view(), name="quote"),
]
