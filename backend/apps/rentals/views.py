"""Rentals API views: Handover Vehicle and Return Vehicle (SRS 3.3; Exp 2 use cases 7, 8).

Every view declares permission_classes explicitly (SE-4). Bookings are
scoped on the server (SE-5): Branch Staff and Branch Managers see only their
own branch's bookings, and a booking outside it is a 404. Only Branch Staff
hand a vehicle over or take it back (UC 7 and UC 8 actor; a report's
recorded_by is BranchStaff).
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
from apps.payments.services import PaymentError

from . import services
from .serializers import (
    BranchBookingSerializer,
    HandoverDetailSerializer,
    HandoverRefusedSerializer,
    HandoverSerializer,
    ReturnDetailSerializer,
    ReturnQuoteSerializer,
    ReturnReadingsSerializer,
    ReturnRefusedSerializer,
    ReturnSerializer,
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


# ═══ Module N2: Return Vehicle (SRS 3.3 Return.*; Exp 2 use case 8) ═════
# UC 8's actor is Branch Staff: only they quote and complete a return; Branch
# Managers follow it read only. A supervisor's override is checked in the service.

RETURN_TAG = "Return"


def _refusal(exc: services.ReturnError) -> Response:
    body = {"detail": str(exc), "code": exc.code}
    if isinstance(exc, services.ReturnRefusedError):
        body["refusals"] = [{"code": r.code, "message": r.message} for r in exc.refusals]
    if exc.field:
        body[exc.field] = [str(exc)]
    return Response(body, status=exc.status)


class ReturnListView(ListAPIView):
    """UC 8 step 1: the branch's returns due today or overdue, and the booking lookup."""

    permission_classes = [BRANCH_TEAM]
    serializer_class = BranchBookingSerializer

    def get_queryset(self):
        return services.branch_returns(
            scoped_bookings(self.request.user), query=self.request.query_params.get("q", "")
        )

    @extend_schema(
        tags=[RETURN_TAG],
        summary="Returns due at your branch, or find a rental in progress",
        description=(
            "Active bookings collected at the caller's branch and due back today or overdue, "
            "earliest return first. With `q`, finds an Active booking on any date by its "
            "booking reference or the customer's mobile number."
        ),
        parameters=[OpenApiParameter("q", str, required=False)],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ReturnDetailView(RetrieveAPIView):
    permission_classes = [BRANCH_TEAM]
    serializer_class = ReturnDetailSerializer

    def get_queryset(self):
        return scoped_bookings(self.request.user)

    @extend_schema(
        tags=[RETURN_TAG],
        summary="A booking's return checklist (UC 8 step 1)",
        description=(
            "The booking, its handover condition report (whose photos are shown beside the "
            "return photos, Return.Checklist), the BR-10 to BR-12 terms, the rental already "
            "paid (extensions included, never charged again) and how the deposit was paid. "
            "`refusals` says why a booking cannot be returned (only an Active one can). Once "
            "returned, `return_report` and `settlement` hold the signed settlement, its "
            "refund status (Pending Approval above the approval limit) and any due."
        ),
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ReturnQuoteView(APIView):
    permission_classes = [IsBranchStaff]

    @extend_schema(
        tags=[RETURN_TAG],
        summary="Compute the itemised settlement (UC 8 step 3, Return.Charges)",
        description=(
            "From the return readings and the charges the staff member enters: the late "
            "return (BR-10), excess kilometres (BR-11), fuel or charge shortfall (BR-12), "
            "accessories not returned, damage and tax as separate lines, then what is "
            "deducted from the deposit, refunded (BR-14) or left as a due. Nothing is saved. "
            "`override_required` is true when the distance needs a supervisor's approval "
            "(Return.Odometer). A reading below the handover reading is 400."
        ),
        request=ReturnReadingsSerializer,
        responses={
            200: ReturnQuoteSerializer,
            400: DetailSerializer,
            409: OpenApiResponse(ReturnRefusedSerializer, description="Not an Active booking"),
        },
    )
    def post(self, request, pk: int):
        booking = get_object_or_404(scoped_bookings(request.user), pk=pk)
        serializer = ReturnReadingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            quote = services.return_quote(booking, request.user, serializer.to_readings())
        except services.ReturnError as exc:
            return _refusal(exc)
        return Response(ReturnQuoteSerializer.of(quote))


class ReturnCompleteView(APIView):
    permission_classes = [IsBranchStaff]
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=[RETURN_TAG],
        summary="Record, settle and complete a return (BranchStaff.return_vehicle())",
        description=(
            "Exp 4 sequence 2 in one transaction: the return condition report with one photo "
            "of each side, signed by the customer to acknowledge the settlement; the charges "
            "deducted from the deposit and put on the invoice as a debit note; the balance "
            "refunded (BR-14) or the excess recorded as a due (Pay.Dues); the vehicle's "
            "odometer updated; a maintenance job raised if the vehicle is flagged "
            "(Return.Flag); the booking Completed and the vehicle Available, or Under "
            "Maintenance if flagged unfit. If the charges differ from `expected_total` the "
            "answer is 409 `settlement_changed`. Sending it again for a returned booking "
            "returns the same result and moves no money."
        ),
        request={"multipart/form-data": ReturnSerializer},
        responses={
            201: ReturnDetailSerializer,
            400: DetailSerializer,
            402: DetailSerializer,
            409: OpenApiResponse(ReturnRefusedSerializer, description="Not an Active booking"),
        },
    )
    def post(self, request, pk: int):
        booking = get_object_or_404(scoped_bookings(request.user), pk=pk)
        serializer = ReturnSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            services.return_vehicle(
                booking.pk, request.user, request=request, **serializer.to_return()
            )
        except services.ReturnError as exc:
            return _refusal(exc)
        except PaymentError as exc:  # R1's refusal, e.g. a gateway that refuses the capture
            return Response({"detail": str(exc), "code": exc.code}, status=exc.status)
        booking = scoped_bookings(request.user).get(pk=booking.pk)
        data = ReturnDetailSerializer(booking, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED)
