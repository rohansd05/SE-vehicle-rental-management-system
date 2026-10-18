"""Tariff, add-on and discount code administration API (Module N3; Fleet.Tariff,
BR-13, D17), mounted under /api/v1/pricing/admin/. Administrator only (BR-13,
SE-6): every view declares IsAdministrator.

Kept apart from the quote views (views.py, Rohan's). No pricing or repricing
code is called or changed here.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers import DetailSerializer
from apps.core.permissions import IsAdministrator

from . import admin_services
from .admin_serializers import (
    AdminAddOnSerializer,
    AdminDiscountCodeSerializer,
    AdminTariffSerializer,
    TariffInputSerializer,
)
from .models import AddOn, DiscountCode, Tariff
from .services import tariffs_in_force

TAG = "Tariff administration"


def _refused(exc: admin_services.PricingAdminError):
    raise ValidationError({exc.field or "detail": [str(exc)]}) from exc


def _tariffs():
    return Tariff.objects.select_related("vehicle_category", "defined_by__user")


class AdminTariffListView(ListAPIView):
    """Fleet.Tariff.History: every tariff, newest first per category."""

    permission_classes = [IsAdministrator]
    serializer_class = AdminTariffSerializer
    pagination_class = None
    filter_backends: list = []

    def get_queryset(self):
        tariffs = _tariffs().order_by("vehicle_category__name", "-effective_from")
        category = self.request.query_params.get("vehicle_category")
        return tariffs.filter(vehicle_category_id=category) if category else tariffs

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "in_force": tariffs_in_force()}

    @extend_schema(
        tags=[TAG],
        summary="Tariff history (Fleet.Tariff.History)",
        parameters=[OpenApiParameter("vehicle_category", int, required=False)],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=[TAG],
        summary="Define a tariff from an effective date (Fleet.Tariff, BR-13)",
        description=(
            "The previous tariff stays; bookings and invoices keep the tariff they were priced "
            "at (UC 11 extension 2a). `effective_from` empty means now; a past date is refused."
        ),
        request=TariffInputSerializer,
        responses={201: AdminTariffSerializer, 400: DetailSerializer},
    )
    def post(self, request):
        serializer = TariffInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            tariff = admin_services.define_tariff(request.user, serializer.validated_data, request)
        except admin_services.PricingAdminError as exc:
            _refused(exc)
        context = {"in_force": tariffs_in_force()}
        return Response(
            AdminTariffSerializer(_tariffs().get(pk=tariff.pk), context=context).data,
            status=status.HTTP_201_CREATED,
        )


class AdminTariffDetailView(APIView):
    permission_classes = [IsAdministrator]

    @extend_schema(
        tags=[TAG],
        summary="Withdraw a scheduled tariff before it takes effect",
        responses={204: None, 400: DetailSerializer},
    )
    def delete(self, request, pk: int):
        tariff = get_object_or_404(Tariff, pk=pk)
        try:
            admin_services.withdraw_tariff(tariff, request.user, request)
        except admin_services.PricingAdminError as exc:
            _refused(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminAddOnListView(ListAPIView):
    permission_classes = [IsAdministrator]
    serializer_class = AdminAddOnSerializer
    pagination_class = None
    filter_backends: list = []
    queryset = AddOn.objects.order_by("name")

    @extend_schema(tags=[TAG], summary="Add-ons, active or not (Book.Addons)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=[TAG],
        summary="Add an add-on (BR-7: charged at its daily rate)",
        request=AdminAddOnSerializer,
        responses={201: AdminAddOnSerializer, 400: DetailSerializer},
    )
    def post(self, request):
        serializer = AdminAddOnSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            add_on = admin_services.save_add_on(
                request.user, serializer.validated_data, request=request
            )
        except admin_services.PricingAdminError as exc:
            _refused(exc)
        return Response(AdminAddOnSerializer(add_on).data, status=status.HTTP_201_CREATED)


class AdminAddOnDetailView(APIView):
    permission_classes = [IsAdministrator]

    @extend_schema(
        tags=[TAG],
        summary="Change an add-on's name, rate, vehicle type or availability",
        description="Confirmed bookings keep the rate they were priced at (BR-13).",
        request=AdminAddOnSerializer,
        responses={200: AdminAddOnSerializer, 400: DetailSerializer},
    )
    def patch(self, request, pk: int):
        add_on = get_object_or_404(AddOn, pk=pk)
        serializer = AdminAddOnSerializer(add_on, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            add_on = admin_services.save_add_on(
                request.user, serializer.validated_data, add_on, request
            )
        except admin_services.PricingAdminError as exc:
            _refused(exc)
        return Response(AdminAddOnSerializer(add_on).data)


class AdminDiscountCodeListView(ListAPIView):
    permission_classes = [IsAdministrator]
    serializer_class = AdminDiscountCodeSerializer
    pagination_class = None
    filter_backends: list = []
    queryset = DiscountCode.objects.order_by("code")

    @extend_schema(tags=[TAG], summary="Discount codes (D17)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=[TAG],
        summary="Create a discount code (D17)",
        request=AdminDiscountCodeSerializer,
        responses={201: AdminDiscountCodeSerializer, 400: DetailSerializer},
    )
    def post(self, request):
        serializer = AdminDiscountCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            code = admin_services.save_discount_code(
                request.user, serializer.validated_data, request=request
            )
        except admin_services.PricingAdminError as exc:
            _refused(exc)
        return Response(AdminDiscountCodeSerializer(code).data, status=status.HTTP_201_CREATED)


class AdminDiscountCodeDetailView(APIView):
    permission_classes = [IsAdministrator]

    @extend_schema(
        tags=[TAG],
        summary="Change a discount code's value, window, limit or availability",
        description="The code text itself cannot change.",
        request=AdminDiscountCodeSerializer,
        responses={200: AdminDiscountCodeSerializer, 400: DetailSerializer},
    )
    def patch(self, request, pk: int):
        code = get_object_or_404(DiscountCode, pk=pk)
        serializer = AdminDiscountCodeSerializer(code, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            code = admin_services.save_discount_code(
                request.user, serializer.validated_data, code, request
            )
        except admin_services.PricingAdminError as exc:
            _refused(exc)
        return Response(AdminDiscountCodeSerializer(code).data)
