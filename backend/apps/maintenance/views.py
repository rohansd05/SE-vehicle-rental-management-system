"""Maintenance API views (SRS 3.6; Exp 4 sequence 3). Views stay thin: every
write goes through services.py, which audits it.

Every view declares permission_classes explicitly (SE-4). Records are scoped
on the server (SE-5): Branch Staff and Branch Managers see their branch's
vehicles, a technician sees only the jobs assigned to them, and an
Administrator sees everything. A record outside the caller's scope is a 404.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveAPIView
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import MaintenanceTechnician, User
from apps.accounts.serializers import DetailSerializer
from apps.core.permissions import (
    IsAdministrator,
    IsBranchManager,
    IsBranchStaff,
    IsMaintenanceTechnician,
    scope_queryset,
)
from apps.fleet.models import Vehicle

from . import services
from .models import MaintenanceJob
from .serializers import (
    CancelJobSerializer,
    CompleteJobSerializer,
    MaintenanceJobSerializer,
    MaintenanceVehicleSerializer,
    RecordWorkSerializer,
    ReportJobSerializer,
    ScheduleConflictSerializer,
    ScheduleJobSerializer,
    TechnicianSerializer,
    WorkIncompleteSerializer,
    WorkshopInvoiceSerializer,
)

TAG = "Maintenance"
CLEARANCE_TAG = "Maintenance clearance (BR-16)"

# Maint.Create, Maint.Schedule: Branch Staff, Branch Managers and Administrators.
JOB_MANAGERS = IsBranchStaff | IsBranchManager | IsAdministrator


class ReadOnly(BasePermission):
    def has_permission(self, request, view) -> bool:
        return request.method in SAFE_METHODS


JOB_RELATED = (
    "vehicle__category",
    "vehicle__home_branch",
    "technician__user",
    "technician__unsafe_clearance_authorisation",
    "reported_by",
    "closed_by",
    "cancelled_by",
)


def scoped_jobs(user):
    """The jobs `user` may see (SE-5)."""
    jobs = MaintenanceJob.objects.select_related(*JOB_RELATED).prefetch_related("parts")
    if user.is_authenticated and user.role == User.Role.MAINTENANCE_TECHNICIAN:
        return jobs.filter(technician__user=user)
    return scope_queryset(jobs, user, branch_lookup="vehicle__home_branch_id")


def scoped_vehicles(user):
    vehicles = Vehicle.objects.select_related("category", "home_branch")
    return scope_queryset(vehicles, user, branch_lookup="home_branch_id")


def _job_response(job, request, code=status.HTTP_200_OK) -> Response:
    job = scoped_jobs(request.user).get(pk=job.pk)
    return Response(MaintenanceJobSerializer(job, context={"request": request}).data, status=code)


def _bad_request(exc: services.MaintenanceError):
    if isinstance(exc, services.WorkIncompleteError):
        return Response(
            {"detail": str(exc), "code": "work_incomplete", "missing": exc.missing},
            status=status.HTTP_400_BAD_REQUEST,
        )
    raise ValidationError({"detail": str(exc)}) from exc


class _JobActionView(APIView):
    """POST on one job the caller can see."""

    def get_job(self, request, pk: int) -> MaintenanceJob:
        return get_object_or_404(scoped_jobs(request.user), pk=pk)


JOB_EXAMPLE = OpenApiExample(
    "Report a fault",
    request_only=True,
    value={
        "vehicle": 12,
        "job_type": "Corrective",
        "severity": "High",
        "reported_problem": "Brake pedal feels soft; pulls to the left under braking.",
        "flag_unsafe": True,
    },
)


class JobListCreateView(ListCreateAPIView):
    """Maint.Create (POST) and the branch or technician job list (GET)."""

    permission_classes = [JOB_MANAGERS | (IsMaintenanceTechnician & ReadOnly)]
    serializer_class = MaintenanceJobSerializer
    filterset_fields = ["status", "vehicle", "severity", "job_type"]

    def get_queryset(self):
        return scoped_jobs(self.request.user)

    @extend_schema(
        tags=[TAG],
        summary="List maintenance jobs",
        description=(
            "Branch Staff and Branch Managers see their branch's jobs, a technician sees only "
            "the jobs assigned to them, an Administrator sees all. Filter with `status`, "
            "`vehicle`, `severity` and `job_type`."
        ),
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=[TAG],
        summary="Report a fault (Maint.Create)",
        description=(
            "Creates a Reported job. `flag_unsafe` flags the vehicle Unsafe at once "
            "(Maint.Unsafe); otherwise the vehicle status changes only when the job is "
            "scheduled (Appendix B)."
        ),
        request=ReportJobSerializer,
        responses={201: MaintenanceJobSerializer, 400: DetailSerializer},
        examples=[JOB_EXAMPLE],
    )
    def post(self, request, *args, **kwargs):
        serializer = ReportJobSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        get_object_or_404(scoped_vehicles(request.user), pk=data["vehicle"].pk)
        try:
            job = services.report_job(request.user, **data, request=request)
        except services.MaintenanceError as exc:
            return _bad_request(exc)
        return _job_response(job, request, status.HTTP_201_CREATED)


class JobDetailView(RetrieveAPIView):
    permission_classes = [JOB_MANAGERS | IsMaintenanceTechnician]
    serializer_class = MaintenanceJobSerializer

    def get_queryset(self):
        return scoped_jobs(self.request.user)

    @extend_schema(tags=[TAG], summary="A maintenance job with its record and parts")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class JobScheduleView(_JobActionView):
    permission_classes = [JOB_MANAGERS]

    @extend_schema(
        tags=[TAG],
        summary="Assign a technician and a period (Maint.Schedule)",
        description=(
            "Reported -> Scheduled; an Available vehicle goes Under Maintenance. If the "
            "period overlaps Confirmed bookings the answer is 409 listing them; send again "
            "with `confirm_conflicts: true` to go ahead (Maint.Conflict)."
        ),
        request=ScheduleJobSerializer,
        responses={
            200: MaintenanceJobSerializer,
            400: DetailSerializer,
            409: ScheduleConflictSerializer,
        },
        examples=[
            OpenApiExample(
                "Schedule",
                request_only=True,
                value={
                    "technician": 3,
                    "scheduled_from": "2026-10-14T04:30:00Z",
                    "scheduled_to": "2026-10-14T12:30:00Z",
                    "confirm_conflicts": False,
                },
            )
        ],
    )
    def post(self, request, pk: int):
        job = self.get_job(request, pk)
        serializer = ScheduleJobSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            job = services.schedule_job(
                job.pk, request.user, **serializer.validated_data, request=request
            )
        except services.ScheduleConflictError as exc:
            body = {
                "detail": str(exc),
                "code": "schedule_conflict",
                "bookings": [
                    {
                        "booking_reference": b.booking_reference,
                        "pickup_datetime": b.pickup_datetime,
                        "return_datetime": b.return_datetime,
                    }
                    for b in exc.bookings
                ],
            }
            return Response(ScheduleConflictSerializer(body).data, status=status.HTTP_409_CONFLICT)
        except services.MaintenanceError as exc:
            return _bad_request(exc)
        return _job_response(job, request)


class JobCancelView(_JobActionView):
    permission_classes = [JOB_MANAGERS]

    @extend_schema(
        tags=[TAG],
        summary="Cancel a Reported or Scheduled job",
        request=CancelJobSerializer,
        responses={200: MaintenanceJobSerializer, 400: DetailSerializer},
        examples=[
            OpenApiExample("Cancel", request_only=True, value={"reason": "Duplicate of job 41."})
        ],
    )
    def post(self, request, pk: int):
        job = self.get_job(request, pk)
        serializer = CancelJobSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            job = services.cancel_job(
                job.pk, request.user, serializer.validated_data["reason"], request
            )
        except services.MaintenanceError as exc:
            return _bad_request(exc)
        return _job_response(job, request)


class JobStartView(_JobActionView):
    permission_classes = [IsMaintenanceTechnician]

    @extend_schema(
        tags=[TAG],
        summary="Start a scheduled job (Scheduled -> In Progress)",
        request=None,
        responses={200: MaintenanceJobSerializer, 400: DetailSerializer},
    )
    def post(self, request, pk: int):
        job = self.get_job(request, pk)
        try:
            job = services.start_job(job.pk, request.user, request)
        except services.MaintenanceError as exc:
            return _bad_request(exc)
        return _job_response(job, request)


class JobRecordView(_JobActionView):
    permission_classes = [IsMaintenanceTechnician]

    @extend_schema(
        tags=[TAG],
        summary="Record the work, parts, cost and downtime (Maint.Record)",
        description=(
            "Replaces the job's record. The total cost is computed: labour plus every "
            "part's quantity x unit cost."
        ),
        request=RecordWorkSerializer,
        responses={200: MaintenanceJobSerializer, 400: DetailSerializer},
        examples=[
            OpenApiExample(
                "Record work",
                request_only=True,
                value={
                    "service_date": "2026-10-14",
                    "odometer_at_service": 15230,
                    "work_description": "Replaced front brake pads; bled the brake lines.",
                    "labour_cost": "800.00",
                    "downtime_hours": "6.50",
                    "parts": [
                        {
                            "part_name": "Brake pads (front)",
                            "quantity": "1",
                            "unit_cost": "1450.00",
                        },
                        {"part_name": "Brake fluid DOT4", "quantity": "0.5", "unit_cost": "600.00"},
                    ],
                },
            )
        ],
    )
    def put(self, request, pk: int):
        job = self.get_job(request, pk)
        serializer = RecordWorkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            job = services.record_work(
                job.pk, request.user, **serializer.validated_data, request=request
            )
        except services.MaintenanceError as exc:
            return _bad_request(exc)
        return _job_response(job, request)


class JobCompleteView(_JobActionView):
    # BR-16: the assigned technician (scoped above) or an Administrator.
    permission_classes = [IsMaintenanceTechnician | IsAdministrator]

    @extend_schema(
        tags=[TAG],
        summary="Complete a job (Exp 4 sequence 3, MaintenanceJob.complete_job())",
        description=(
            "Validates the recorded work, parts and cost; if incomplete the answer is 400 "
            'with `code: work_incomplete` ("record work first"). If the vehicle is flagged '
            "Unsafe the job stays In Progress with `awaiting_clearance: true` until an "
            "Administrator approves it (BR-16), unless the caller may clear the flag "
            "(`can_clear_unsafe`: an Administrator or an authorised technician) and sends "
            "`clear_unsafe: true`; the flag is then cleared as the job closes and the caller is "
            "recorded (UC 10 extension 1a). Otherwise the vehicle becomes Available, the next "
            "service due is computed (BR-15) and the job is Completed."
        ),
        request=CompleteJobSerializer,
        responses={200: MaintenanceJobSerializer, 400: WorkIncompleteSerializer},
    )
    def post(self, request, pk: int):
        job = self.get_job(request, pk)
        serializer = CompleteJobSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            job = services.complete_job(job.pk, request.user, request, **serializer.validated_data)
        except services.MaintenanceError as exc:
            return _bad_request(exc)
        return _job_response(job, request)


class JobInvoiceView(_JobActionView):
    permission_classes = [IsMaintenanceTechnician]
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=[TAG],
        summary="Attach the workshop invoice (Maint.Record, UC 9 step 3)",
        description="A PDF, JPG or PNG of at most 5 MB; a new upload replaces the previous one.",
        request={"multipart/form-data": WorkshopInvoiceSerializer},
        responses={200: MaintenanceJobSerializer, 400: DetailSerializer},
    )
    def put(self, request, pk: int):
        job = self.get_job(request, pk)
        serializer = WorkshopInvoiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            job = services.attach_invoice(
                job.pk, request.user, serializer.validated_data["workshop_invoice"], request
            )
        except services.MaintenanceError as exc:
            return _bad_request(exc)
        return _job_response(job, request)


class ClearanceQueueView(ListAPIView):
    """BR-16: jobs whose work is complete on an Unsafe vehicle, oldest first."""

    permission_classes = [IsAdministrator]
    serializer_class = MaintenanceJobSerializer

    def get_queryset(self):
        return (
            scoped_jobs(self.request.user)
            .filter(pk__in=services.clearance_queue().values("pk"))
            .order_by("clearance_requested_at")
        )

    @extend_schema(tags=[CLEARANCE_TAG], summary="Jobs awaiting Unsafe-flag clearance")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ApproveClearanceView(_JobActionView):
    permission_classes = [IsAdministrator]

    @extend_schema(
        tags=[CLEARANCE_TAG],
        summary="Clear the Unsafe flag and complete the job (BR-16)",
        description=(
            "The vehicle becomes Available, the Administrator is recorded as `closed_by`, "
            "the next service due is computed (BR-15) and the job is Completed."
        ),
        request=None,
        responses={200: MaintenanceJobSerializer, 400: DetailSerializer},
    )
    def post(self, request, pk: int):
        job = self.get_job(request, pk)
        try:
            job = services.approve_clearance(job.pk, request.user, request)
        except services.MaintenanceError as exc:
            return _bad_request(exc)
        return _job_response(job, request)


class TechnicianListView(ListAPIView):
    """Technicians a job can be assigned to (Appendix A "assigned to")."""

    permission_classes = [JOB_MANAGERS]
    serializer_class = TechnicianSerializer
    pagination_class = None

    def get_queryset(self):
        return (
            MaintenanceTechnician.objects.filter(user__is_active=True)
            .select_related("user", "unsafe_clearance_authorisation")
            .order_by("user__name")
        )

    @extend_schema(tags=[TAG], summary="Active maintenance technicians")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class TechnicianAuthorisationView(APIView):
    """BR-16: an Administrator authorises a technician to clear an Unsafe flag, or revokes it."""

    permission_classes = [IsAdministrator]

    def _technician(self, pk: int) -> MaintenanceTechnician:
        return get_object_or_404(MaintenanceTechnician.objects.select_related("user"), pk=pk)

    def _answer(self, technician: MaintenanceTechnician) -> Response:
        technician = MaintenanceTechnician.objects.select_related(
            "user", "unsafe_clearance_authorisation"
        ).get(pk=technician.pk)
        return Response(TechnicianSerializer(technician).data)

    @extend_schema(
        tags=[CLEARANCE_TAG],
        summary="Authorise the technician to clear Unsafe flags (BR-16)",
        request=None,
        responses={200: TechnicianSerializer, 400: DetailSerializer},
    )
    def put(self, request, pk: int):
        technician = self._technician(pk)
        try:
            services.authorise_technician(technician, request.user, request)
        except services.MaintenanceError as exc:
            return _bad_request(exc)
        return self._answer(technician)

    @extend_schema(
        tags=[CLEARANCE_TAG],
        summary="Revoke the technician's authorisation (BR-16)",
        request=None,
        responses={200: TechnicianSerializer},
    )
    def delete(self, request, pk: int):
        technician = self._technician(pk)
        services.revoke_authorisation(technician, request.user, request)
        return self._answer(technician)


class VehicleListView(ListAPIView):
    """Vehicles a fault can be reported on, with status and BR-15 next service due."""

    permission_classes = [JOB_MANAGERS]
    serializer_class = MaintenanceVehicleSerializer
    filterset_fields = ["status"]
    pagination_class = None  # a picker: every vehicle of the branch

    def get_queryset(self):
        return scoped_vehicles(self.request.user).order_by("registration_no")

    @extend_schema(
        tags=[TAG],
        summary="Vehicles of the caller's branch (all for an Administrator)",
        parameters=[OpenApiParameter("status", str, enum=Vehicle.Status.values)],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class VehicleHistoryView(ListAPIView):
    """Maint.History: every job on a vehicle, newest first, for staff,
    technicians and Administrators."""

    permission_classes = [JOB_MANAGERS | IsMaintenanceTechnician]
    serializer_class = MaintenanceJobSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return MaintenanceJob.objects.none()
        user = self.request.user
        if user.role == User.Role.MAINTENANCE_TECHNICIAN:
            vehicle = get_object_or_404(Vehicle, pk=self.kwargs["pk"])
        else:
            vehicle = get_object_or_404(scoped_vehicles(user), pk=self.kwargs["pk"])
        return (
            MaintenanceJob.objects.filter(vehicle=vehicle)
            .select_related(*JOB_RELATED)
            .prefetch_related("parts")
            .order_by("-created_at")
        )

    @extend_schema(
        tags=[TAG],
        summary="Maintenance history of a vehicle (Maint.History)",
        responses={200: MaintenanceJobSerializer(many=True), 404: OpenApiResponse()},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
