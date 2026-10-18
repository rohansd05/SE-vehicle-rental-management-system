"""Core API views.

Every view must declare permission_classes explicitly (SE-4).
"""

from django.conf import settings
from django.db import DatabaseError, connection
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .permissions import IsAdministrator, IsBranchManager
from .serializers import (
    AuditEntrySerializer,
    AuditFilterOptionsSerializer,
    AuditFilterSerializer,
    HealthSerializer,
)

AUDIT_TAG = "Audit log"
AUDIT_READERS = IsAdministrator | IsBranchManager


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


class AuditLogListView(ListAPIView):
    """Fleet.Audit, SE-10: the audit log, newest first, read-only (no write endpoint exists).

    An Administrator reads every entry; a Branch Manager only their branch's.
    """

    permission_classes = [AUDIT_READERS]
    serializer_class = AuditEntrySerializer
    filter_backends: list = []

    def get_queryset(self):
        params = AuditFilterSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        entries = services.audit_entries_for(self.request.user)
        return services.filter_audit_entries(entries, **params.validated_data)

    @extend_schema(
        tags=[AUDIT_TAG],
        summary="Read the audit log (Fleet.Audit)",
        description=(
            "Filter with `actor` (part of a name or e-mail, or `system`), `action`, "
            "`entity_type`, `entity_id`, and `date_from` / `date_to` (local dates)."
        ),
        parameters=[
            OpenApiParameter("actor", str, required=False),
            OpenApiParameter("action", str, required=False),
            OpenApiParameter("entity_type", str, required=False),
            OpenApiParameter("entity_id", str, required=False),
            OpenApiParameter("date_from", str, required=False, description="YYYY-MM-DD"),
            OpenApiParameter("date_to", str, required=False, description="YYYY-MM-DD"),
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AuditFilterOptionsView(APIView):
    """The actions and entity types the caller's entries hold, for the filter lists."""

    permission_classes = [AUDIT_READERS]

    @extend_schema(
        tags=[AUDIT_TAG],
        summary="Actions and entity types to filter the audit log by",
        responses={200: AuditFilterOptionsSerializer},
    )
    def get(self, request: Request) -> Response:
        options = services.audit_filter_options(services.audit_entries_for(request.user))
        return Response(AuditFilterOptionsSerializer(options).data)
