"""Fleet API routes, mounted under /api/v1/fleet/."""

from django.urls import path

from . import admin_views, views

app_name = "fleet"

urlpatterns = [
    path("branches/", views.BranchListView.as_view(), name="branch-list"),
    path("categories/", views.VehicleCategoryListView.as_view(), name="category-list"),
    path("search/", views.VehicleSearchView.as_view(), name="search"),
    path(
        "search/alternatives/",
        views.SearchAlternativesView.as_view(),
        name="search-alternatives",
    ),
    path("vehicles/<int:pk>/", views.VehicleDetailView.as_view(), name="vehicle-detail"),
]

# Fleet administration (Module N3, UC 11): admin_views.py, Administrator only.
urlpatterns += [
    path("admin/vehicles/", admin_views.AdminVehicleListView.as_view(), name="admin-vehicles"),
    path(
        "admin/vehicles/<int:pk>/",
        admin_views.AdminVehicleDetailView.as_view(),
        name="admin-vehicle",
    ),
    path(
        "admin/vehicles/<int:pk>/retire/",
        admin_views.AdminVehicleRetireView.as_view(),
        name="admin-vehicle-retire",
    ),
    path(
        "admin/vehicles/<int:pk>/photos/",
        admin_views.AdminVehiclePhotoView.as_view(),
        name="admin-vehicle-photos",
    ),
    path(
        "admin/vehicles/<int:pk>/photos/<int:photo_id>/",
        admin_views.AdminVehiclePhotoDetailView.as_view(),
        name="admin-vehicle-photo",
    ),
    path(
        "admin/vehicles/<int:pk>/documents/",
        admin_views.AdminVehicleDocumentView.as_view(),
        name="admin-vehicle-documents",
    ),
    path(
        "admin/vehicles/<int:pk>/documents/<int:document_id>/",
        admin_views.AdminVehicleDocumentDetailView.as_view(),
        name="admin-vehicle-document",
    ),
    path("admin/branches/", admin_views.AdminBranchListView.as_view(), name="admin-branches"),
    path(
        "admin/branches/<int:pk>/", admin_views.AdminBranchDetailView.as_view(), name="admin-branch"
    ),
    path(
        "admin/branches/<int:pk>/areas/",
        admin_views.AdminBranchAreaView.as_view(),
        name="admin-branch-areas",
    ),
    path(
        "admin/branches/<int:pk>/areas/<int:area_id>/",
        admin_views.AdminBranchAreaDetailView.as_view(),
        name="admin-branch-area",
    ),
]
