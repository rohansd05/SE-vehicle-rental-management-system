"""Reports API views (UC 14 View Reports; Report.Access).

Every view must declare permission_classes explicitly (SE-4). Only an
Administrator or a Branch Manager may read a report (Report.Access: "No other
user class shall have access to revenue or cost reports"); the services limit
a Branch Manager to their own branch (UC 14 extension 1a).
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdministrator, IsBranchManager

from . import services
from .serializers import (
    CustomerReportSerializer,
    DashboardSerializer,
    MaintenanceCostReportSerializer,
    PeriodQuerySerializer,
    RevenueReportSerializer,
    UtilisationReportSerializer,
)

TAG = "Reports"
REPORT_READERS = IsAdministrator | IsBranchManager
PERIOD = [
    OpenApiParameter(
        "date_from", OpenApiTypes.DATE, required=False, description="Local date; default the 1st"
    ),
    OpenApiParameter("date_to", OpenApiTypes.DATE, required=False, description="Default today"),
]


def _report(request: Request, build, serializer_class) -> Response:
    """UC 14 steps 1 and 2: the actor's period, the report computed for their scope."""
    params = PeriodQuerySerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    period = params.validated_data["period"]
    report = {
        "date_from": period.date_from,
        "date_to": period.date_to,
        "scope": services.scope_label(request.user),
        **build(request.user, period),
    }
    return Response(serializer_class(report).data)


class DashboardView(APIView):
    """Report.Dashboard, for the Administrator's and Branch Manager's home page."""

    permission_classes = [REPORT_READERS]

    @extend_schema(
        tags=[TAG], summary="Summary dashboard (Report.Dashboard)", responses=DashboardSerializer
    )
    def get(self, request: Request) -> Response:
        summary = {"scope": services.scope_label(request.user), **services.dashboard(request.user)}
        return Response(DashboardSerializer(summary).data)


class UtilisationReportView(APIView):
    permission_classes = [REPORT_READERS]

    @extend_schema(
        tags=[TAG],
        summary="Vehicle utilisation (Report.Utilisation)",
        parameters=PERIOD,
        responses=UtilisationReportSerializer,
    )
    def get(self, request: Request) -> Response:
        return _report(request, services.utilisation_report, UtilisationReportSerializer)


class RevenueReportView(APIView):
    permission_classes = [REPORT_READERS]

    @extend_schema(
        tags=[TAG],
        summary="Revenue, refunds and net revenue (Report.Revenue)",
        parameters=PERIOD,
        responses=RevenueReportSerializer,
    )
    def get(self, request: Request) -> Response:
        return _report(request, services.revenue_report, RevenueReportSerializer)


class MaintenanceReportView(APIView):
    permission_classes = [REPORT_READERS]

    @extend_schema(
        tags=[TAG],
        summary="Maintenance cost by vehicle and job type (UC 14)",
        parameters=PERIOD,
        responses=MaintenanceCostReportSerializer,
    )
    def get(self, request: Request) -> Response:
        return _report(request, services.maintenance_report, MaintenanceCostReportSerializer)


class CustomerReportView(APIView):
    permission_classes = [REPORT_READERS]

    @extend_schema(
        tags=[TAG],
        summary="Customers: new, active, top, with dues, no-shows (UC 14)",
        parameters=PERIOD,
        responses=CustomerReportSerializer,
    )
    def get(self, request: Request) -> Response:
        return _report(request, services.customer_report, CustomerReportSerializer)
