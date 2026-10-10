"""Pricing API views.

Every view must declare permission_classes explicitly (SE-4). Views stay thin;
the charge is computed by services.calculate_price (BR-6).
"""

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.choices import VehicleType
from apps.core.permissions import IsCustomer

from . import services
from .models import AddOn
from .serializers import AddOnSerializer, QuoteRequestSerializer, QuoteSerializer

TAG = "Pricing"


class AddOnListView(ListAPIView):
    """Book.Addons: the add-ons on offer, at their published daily rate (BR-7)."""

    permission_classes = [AllowAny]  # published rates, like the catalogue (Search.Browse)
    authentication_classes: list = []
    serializer_class = AddOnSerializer
    pagination_class = None
    filter_backends: list = []

    def get_queryset(self):
        add_ons = AddOn.objects.filter(is_active=True)
        vehicle_type = self.request.query_params.get("vehicle_type", "")
        if vehicle_type:
            if vehicle_type not in VehicleType.values:
                raise ValidationError({"vehicle_type": ["Choose Car or Two-Wheeler."]})
            add_ons = add_ons.filter(vehicle_type__in=["", vehicle_type])
        return add_ons

    @extend_schema(
        tags=[TAG],
        summary="Add-ons on offer (Book.Addons)",
        description="Active add-ons. With `vehicle_type`, only those offered with that type.",
        parameters=[
            OpenApiParameter("vehicle_type", str, enum=list(VehicleType.values), required=False)
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class QuoteView(APIView):
    """Book.Quote.Display: the itemised price of a booking before payment."""

    permission_classes = [IsCustomer]  # Book.Create: only a customer books

    @extend_schema(
        tags=[TAG],
        summary="Quote a booking (Tariff.calculate_price(), BR-6)",
        description=(
            "Base charge (whole days from 24 hours, otherwise whole hours after a 15-minute "
            "grace), add-ons per billed day, the discount, then tax on the discounted amount "
            "(D14 rate). The security deposit (BR-3) is separate and not part of "
            "`total_payable`. Usage-based charges arise only at return. Nothing is saved."
        ),
        request=QuoteRequestSerializer,
        responses={200: QuoteSerializer},
        examples=[
            OpenApiExample(
                "Two days with a child seat and a code",
                request_only=True,
                value={
                    "vehicle": 12,
                    "pickup_datetime": "2026-10-20T04:30:00Z",
                    "return_datetime": "2026-10-22T04:30:00Z",
                    "add_ons": [{"add_on": 3, "quantity": 1}],
                    "discount_code": "WELCOME10",
                },
            )
        ],
    )
    def post(self, request: Request) -> Response:
        serializer = QuoteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = services.quote(
                data["vehicle"],
                data["pickup_datetime"],
                data["return_datetime"],
                add_ons=[(line["add_on"], line["quantity"]) for line in data["add_ons"]],
                discount_code=data["discount_code"],
            )
        except services.PricingError as exc:
            raise ValidationError({exc.field: [str(exc)]}) from exc
        return Response(QuoteSerializer(result).data)
