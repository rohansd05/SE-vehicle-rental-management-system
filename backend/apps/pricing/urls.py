"""Pricing API routes, mounted under /api/v1/pricing/."""

from django.urls import path

from . import admin_views, views

app_name = "pricing"

urlpatterns = [
    path("add-ons/", views.AddOnListView.as_view(), name="add-on-list"),
    path("quote/", views.QuoteView.as_view(), name="quote"),
]

# Tariff administration (Module N3, UC 11 step 2): admin_views.py, Administrator only.
urlpatterns += [
    path("admin/tariffs/", admin_views.AdminTariffListView.as_view(), name="admin-tariffs"),
    path(
        "admin/tariffs/<int:pk>/", admin_views.AdminTariffDetailView.as_view(), name="admin-tariff"
    ),
    path("admin/add-ons/", admin_views.AdminAddOnListView.as_view(), name="admin-add-ons"),
    path(
        "admin/add-ons/<int:pk>/", admin_views.AdminAddOnDetailView.as_view(), name="admin-add-on"
    ),
    path(
        "admin/discount-codes/",
        admin_views.AdminDiscountCodeListView.as_view(),
        name="admin-discount-codes",
    ),
    path(
        "admin/discount-codes/<int:pk>/",
        admin_views.AdminDiscountCodeDetailView.as_view(),
        name="admin-discount-code",
    ),
]
