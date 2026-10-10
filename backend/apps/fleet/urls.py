"""Fleet API routes, mounted under /api/v1/fleet/."""

from django.urls import path

from . import views

app_name = "fleet"

urlpatterns = [
    path("branches/", views.BranchListView.as_view(), name="branch-list"),
    path("categories/", views.VehicleCategoryListView.as_view(), name="category-list"),
    path("search/", views.VehicleSearchView.as_view(), name="search"),
]
