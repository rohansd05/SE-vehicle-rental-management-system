"""Rentals API views: Handover Vehicle (SRS 3.3; Exp 2 use case 7).

Every view declares permission_classes explicitly (SE-4). Bookings are
scoped on the server (SE-5): Branch Staff and Branch Managers see only their
own branch's bookings, and a booking outside it is a 404. Only Branch Staff
hand a vehicle over (UC 7 actor; the report's recorded_by is BranchStaff).
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers import DetailSerializer
from apps.bookings.models import Booking
from apps.core.permissions import IsBranchManager, IsBranchStaff, scope_queryset
from apps.fleet.services.status import VehicleStatusError

from . import services
from .serializers import (
    BranchBookingSerializer,
    HandoverDetailSerializer,
    HandoverRefusedSerializer,
    HandoverSerializer,
)

TAG = "Handover"
BRANCH_TEAM = IsBranchStaff | IsBranchManager


def scoped_bookings(user):
    bookings = Booking.objects.select_related(
        "vehicle__category", "customer__user", "pickup_branch", "tariff"
    )
    return scope_queryset(bookings, user, branch_lookup="pickup_branch_id")


class BranchBookingListView(ListAPIView):
    """UC 7 step 1: today's and upcoming collections, and the booking lookup."""

    permission_classes = [BRANCH_TEAM]
    serializer_class = BranchBookingSerializer

    def get_queryset(self):
        params = self.request.query_params
        return services.branch_collections(
            scoped_bookings(self.request.user),
            when=params.get("when", "today"),
            query=params.get("q", ""),
        )

    @extend_schema(
        tags=[TAG],
        summary="Collections at your branch, or find a booking",
        description=(
            "Confirmed bookings collected at the caller's branch, earliest first: `when=today` "
            "(default) or `when=upcoming`. With `q`, finds a Confirmed booking on any date by "
            "its booking reference, its pickup code or the customer's mobile number; `when` is "
            "then ignored. The pickup code itself is never returned."
        ),
        parameters=[
            OpenApiParameter("when", str, enum=["today", "upcoming"], required=False),
            OpenApiParameter("q", str, required=False),
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class HandoverDetailView(RetrieveAPIView):
    permission_classes = [BRANCH_TEAM]
    serializer_class = HandoverDetailSerializer

    def get_queryset(self):
        return scoped_bookings(self.request.user)

    @extend_schema(
        tags=[TAG],
        summary="A booking's handover checklist (UC 7 steps 1 and 2, Handover.Refuse)",
        description=(
            "The booking, the customer's licence, the accessories to issue (BR-7), the photo "
            "sides required and the rental terms to sign. `refusals` lists every condition "
            "that blocks the handover (licence, statutory documents, Unsafe vehicle, payment); "
            "`can_hand_over` is true when there are none. Once handed over, `report` holds "
            "the signed condition report."
        ),
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class HandoverCompleteView(APIView):
    permission_classes = [IsBranchStaff]
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=[TAG],
        summary="Record, sign and complete a handover (BranchStaff.handover_vehicle())",
        description=(
            "Handover.Checklist, Handover.Sign and Handover.Activate in one transaction: the "
            "condition report with one photo of each side and the customer's signature is "
            "stored and can never be altered, the booking becomes Active with the handover "
            "time, the vehicle goes On Rent, everything is audited and a copy is e-mailed to "
            "the customer. If a condition is not met the answer is 409 with `refusals`."
        ),
        request={"multipart/form-data": HandoverSerializer},
        responses={
            201: HandoverDetailSerializer,
            400: DetailSerializer,
            409: OpenApiResponse(HandoverRefusedSerializer, description="Handover.Refuse"),
        },
    )
    def post(self, request, pk: int):
        booking = get_object_or_404(scoped_bookings(request.user), pk=pk)
        serializer = HandoverSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.handover_vehicle(
                booking.pk, request.user, request=request, **serializer.to_checklist()
            )
        except services.HandoverRefusedError as exc:
            body = {
                "detail": str(exc),
                "code": "handover_refused",
                "refusals": [{"code": r.code, "message": r.message} for r in exc.refusals],
            }
            return Response(body, status=status.HTTP_409_CONFLICT)
        except (services.HandoverError, VehicleStatusError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        booking = scoped_bookings(request.user).get(pk=booking.pk)
        data = HandoverDetailSerializer(booking, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED)
