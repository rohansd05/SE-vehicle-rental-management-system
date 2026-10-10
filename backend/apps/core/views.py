"""Core API views.

Every view must declare permission_classes explicitly (SE-4).
"""

from django.conf import settings
from django.db import DatabaseError, connection
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import HealthSerializer


def database_reachable() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return False
    return True


class HealthView(APIView):
    """Liveness and readiness check, also the source of the agency name (D7).

    Public on purpose: used by deployment health checks and by the home page
    before anyone signs in. It exposes no user or business data.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(tags=["System"], responses={200: HealthSerializer, 503: HealthSerializer})
    def get(self, request: Request) -> Response:
        db_ok = database_reachable()
        payload = {
            "status": "ok" if db_ok else "degraded",
            "database": "ok" if db_ok else "unreachable",
            "agency_name": settings.AGENCY_NAME,
            "currency": settings.CURRENCY,
        }
        http_status = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(HealthSerializer(payload).data, status=http_status)
