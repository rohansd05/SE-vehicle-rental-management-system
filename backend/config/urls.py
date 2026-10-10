"""Root URL configuration.

/api/v1/      versioned REST API (CO-4)
/api/schema/  OpenAPI 3.0 schema
/api/docs/    Swagger UI
/admin/       Django admin
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework_simplejwt.authentication import JWTAuthentication

# D12: public in development; administrators only elsewhere. A Django admin
# session is accepted so a signed-in administrator can open Swagger UI.
if settings.API_DOCS_PUBLIC:
    docs_access = {"permission_classes": [AllowAny], "authentication_classes": []}
else:
    docs_access = {
        "permission_classes": [IsAdminUser],
        "authentication_classes": [SessionAuthentication, JWTAuthentication],
    }

api_v1 = [
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),  # auth/, me/, licence/, licences/
    path("fleet/", include("apps.fleet.urls")),
    path("pricing/", include("apps.pricing.urls")),
    path("bookings/", include("apps.bookings.urls")),
    path("rentals/", include("apps.rentals.urls")),
    path("payments/", include("apps.payments.urls")),
    path("maintenance/", include("apps.maintenance.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("reports/", include("apps.reports.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(**docs_access), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema", **docs_access),
        name="swagger-ui",
    ),
]

if "debug_toolbar" in settings.INSTALLED_APPS:
    from debug_toolbar.toolbar import debug_toolbar_urls

    urlpatterns += debug_toolbar_urls()
