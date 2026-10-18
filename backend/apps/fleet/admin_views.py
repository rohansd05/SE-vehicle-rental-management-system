"""Fleet administration API (Module N3; SRS 3.7; Exp 2 use case 11), mounted under
/api/v1/fleet/admin/. Administrator only (SE-4): every view declares IsAdministrator.

Kept apart from the catalogue and search views (views.py, Rohan's). Views stay
thin: services/admin.py validates, writes and audits.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers import DetailSerializer
from apps.core.permissions import IsAdministrator

from .admin_serializers import (
    AdminAreaSerializer,
    AdminBranchSerializer,
    AdminDocumentSerializer,
    AdminPhotoSerializer,
    AdminVehicleDetailSerializer,
    AdminVehicleSerializer,
    AreaInputSerializer,
    BranchInputSerializer,
    DocumentUploadSerializer,
    PhotoUploadSerializer,
    RetireSerializer,
    VehicleCreateSerializer,
    VehicleUpdateSerializer,
)
from .models import Branch, BranchServiceableArea, Vehicle, VehicleDocument, VehiclePhoto
from .services import admin as fleet_admin
from .services.status import VehicleStatusError

TAG = "Fleet administration"


def _vehicles():
    return Vehicle.objects.select_related(
        "category", "home_branch", "car", "twowheeler"
    ).prefetch_related("photos", "documents")


def _refused(exc: fleet_admin.FleetAdminError):
    raise ValidationError({exc.field or "detail": [str(exc)]}) from exc


def _detail(vehicle: Vehicle, request, code=status.HTTP_200_OK) -> Response:
    vehicle = _vehicles().get(pk=vehicle.pk)
    return Response(AdminVehicleDetailSerializer(vehicle, context={"request": request}).data, code)


class AdminVehicleListView(ListAPIView):
    """Fleet.Status: every vehicle with its current status; Fleet.Add (POST)."""

    permission_classes = [IsAdministrator]
    serializer_class = AdminVehicleSerializer
    parser_classes = [MultiPartParser]
    filter_backends: list = []

    def get_queryset(self):
        params = self.request.query_params
        vehicles = _vehicles().order_by("registration_no")
        if params.get("status"):
            vehicles = vehicles.filter(status=params["status"])
        if params.get("home_branch"):
            vehicles = vehicles.filter(home_branch_id=params["home_branch"])
        if query := params.get("q", "").strip():
            vehicles = vehicles.filter(
                Q(registration_no__icontains=query)
                | Q(brand__icontains=query)
                | Q(model__icontains=query)
            )
        return vehicles

    @extend_schema(
        tags=[TAG],
        summary="The fleet (Fleet.Status)",
        parameters=[
            OpenApiParameter("status", str, enum=Vehicle.Status.values, required=False),
            OpenApiParameter("home_branch", int, required=False),
            OpenApiParameter("q", str, required=False, description="Registration, brand, model"),
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=[TAG],
        summary="Add a vehicle (Fleet.Add, UC 11 step 1)",
        description=(
            "multipart/form-data. `photos` repeated, at least four images; `documents` a JSON "
            "list with each statutory document's type and expiry date. A registration or "
            "chassis number already on record is refused (UC 11 extension 1a)."
        ),
        request={"multipart/form-data": VehicleCreateSerializer},
        responses={201: AdminVehicleDetailSerializer, 400: DetailSerializer},
    )
    def post(self, request):
        serializer = VehicleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        photos, documents = data.pop("photos"), data.pop("documents")
        try:
            vehicle = fleet_admin.create_vehicle(
                request.user, data, photos=photos, documents=documents, request=request
            )
        except fleet_admin.FleetAdminError as exc:
            _refused(exc)
        return _detail(vehicle, request, status.HTTP_201_CREATED)


class AdminVehicleDetailView(APIView):
    permission_classes = [IsAdministrator]
    parser_classes = [JSONParser]

    @extend_schema(
        tags=[TAG],
        summary="A vehicle with its photos and documents",
        responses=AdminVehicleDetailSerializer,
    )
    def get(self, request, pk: int):
        return _detail(get_object_or_404(Vehicle, pk=pk), request)

    @extend_schema(
        tags=[TAG],
        summary="Edit a vehicle's master data (UC 11 step 1)",
        description="Status is not editable here: it changes only through the state machine.",
        request=VehicleUpdateSerializer,
        responses={200: AdminVehicleDetailSerializer, 400: DetailSerializer},
    )
    def patch(self, request, pk: int):
        vehicle = get_object_or_404(Vehicle, pk=pk)
        serializer = VehicleUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            vehicle = fleet_admin.update_vehicle(
                vehicle, request.user, serializer.validated_data, request
            )
        except fleet_admin.FleetAdminError as exc:
            _refused(exc)
        return _detail(vehicle, request)


class AdminVehicleRetireView(APIView):
    permission_classes = [IsAdministrator]

    @extend_schema(
        tags=[TAG],
        summary="Retire a vehicle (Fleet.Retire)",
        description=(
            "Through the vehicle state machine: 409 while the vehicle has a booking that is "
            "not over (cancel or reassign it first). History is kept and reportable."
        ),
        request=RetireSerializer,
        responses={200: AdminVehicleDetailSerializer, 400: DetailSerializer, 409: DetailSerializer},
    )
    def post(self, request, pk: int):
        vehicle = get_object_or_404(Vehicle, pk=pk)
        serializer = RetireSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            fleet_admin.retire_vehicle(
                vehicle, request.user, serializer.validated_data["reason"], request
            )
        except fleet_admin.FleetAdminError as exc:
            _refused(exc)
        except VehicleStatusError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return _detail(vehicle, request)


class AdminVehiclePhotoView(APIView):
    permission_classes = [IsAdministrator]
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=[TAG],
        summary="Add a photograph (Fleet.Add)",
        request={"multipart/form-data": PhotoUploadSerializer},
        responses={201: AdminPhotoSerializer, 400: DetailSerializer},
    )
    def post(self, request, pk: int):
        vehicle = get_object_or_404(Vehicle, pk=pk)
        serializer = PhotoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photo = fleet_admin.add_photo(
            vehicle, serializer.validated_data["image"], request.user, request=request
        )
        return Response(
            AdminPhotoSerializer(photo, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class AdminVehiclePhotoDetailView(APIView):
    permission_classes = [IsAdministrator]

    @extend_schema(
        tags=[TAG],
        summary="Remove a photograph (at least four stay)",
        responses={204: None, 400: DetailSerializer},
    )
    def delete(self, request, pk: int, photo_id: int):
        photo = get_object_or_404(VehiclePhoto, pk=photo_id, vehicle_id=pk)
        try:
            fleet_admin.remove_photo(photo, request.user, request)
        except fleet_admin.FleetAdminError as exc:
            _refused(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminVehicleDocumentView(APIView):
    permission_classes = [IsAdministrator]
    parser_classes = [MultiPartParser, JSONParser]

    @extend_schema(
        tags=[TAG],
        summary="Record a statutory document or its renewal (Fleet.Add, SA-3)",
        request={"multipart/form-data": DocumentUploadSerializer},
        responses={201: AdminDocumentSerializer, 400: DetailSerializer},
    )
    def post(self, request, pk: int):
        vehicle = get_object_or_404(Vehicle, pk=pk)
        serializer = DocumentUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            document = fleet_admin.add_document(
                vehicle, serializer.validated_data, request.user, request=request
            )
        except fleet_admin.FleetAdminError as exc:
            _refused(exc)
        return Response(
            AdminDocumentSerializer(document, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class AdminVehicleDocumentDetailView(APIView):
    permission_classes = [IsAdministrator]

    @extend_schema(tags=[TAG], summary="Remove a document entered in error", responses={204: None})
    def delete(self, request, pk: int, document_id: int):
        document = get_object_or_404(VehicleDocument, pk=document_id, vehicle_id=pk)
        fleet_admin.remove_document(document, request.user, request)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _branches():
    return Branch.objects.prefetch_related("serviceable_areas")


class AdminBranchListView(ListAPIView):
    """UC 11 "branches": every branch with its serviceable areas."""

    permission_classes = [IsAdministrator]
    serializer_class = AdminBranchSerializer
    pagination_class = None
    filter_backends: list = []

    def get_queryset(self):
        return _branches().order_by("branch_name")

    @extend_schema(tags=[TAG], summary="Branches and their serviceable areas")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=[TAG],
        summary="Add a branch",
        request=BranchInputSerializer,
        responses={201: AdminBranchSerializer, 400: DetailSerializer},
    )
    def post(self, request):
        serializer = BranchInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            branch = fleet_admin.create_branch(request.user, serializer.validated_data, request)
        except fleet_admin.FleetAdminError as exc:
            _refused(exc)
        return Response(
            AdminBranchSerializer(_branches().get(pk=branch.pk)).data,
            status=status.HTTP_201_CREATED,
        )


class AdminBranchDetailView(APIView):
    permission_classes = [IsAdministrator]

    @extend_schema(
        tags=[TAG],
        summary="Edit a branch",
        request=BranchInputSerializer,
        responses={200: AdminBranchSerializer, 400: DetailSerializer},
    )
    def patch(self, request, pk: int):
        branch = get_object_or_404(Branch, pk=pk)
        serializer = BranchInputSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            fleet_admin.update_branch(branch, request.user, serializer.validated_data, request)
        except fleet_admin.FleetAdminError as exc:
            _refused(exc)
        return Response(AdminBranchSerializer(_branches().get(pk=pk)).data)


class AdminBranchAreaView(APIView):
    permission_classes = [IsAdministrator]

    @extend_schema(
        tags=[TAG],
        summary="Add a serviceable area (Book.Deliver.Location)",
        request=AreaInputSerializer,
        responses={201: AdminAreaSerializer, 400: DetailSerializer},
    )
    def post(self, request, pk: int):
        branch = get_object_or_404(Branch, pk=pk)
        serializer = AreaInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            area = fleet_admin.add_area(branch, serializer.validated_data, request.user, request)
        except fleet_admin.FleetAdminError as exc:
            _refused(exc)
        return Response(AdminAreaSerializer(area).data, status=status.HTTP_201_CREATED)


class AdminBranchAreaDetailView(APIView):
    permission_classes = [IsAdministrator]

    @extend_schema(tags=[TAG], summary="Remove a serviceable area", responses={204: None})
    def delete(self, request, pk: int, area_id: int):
        area = get_object_or_404(BranchServiceableArea, pk=area_id, branch_id=pk)
        fleet_admin.remove_area(area, request.user, request)
        return Response(status=status.HTTP_204_NO_CONTENT)
