"""Bookings API views (SRS 3.1, 3.4; Exp 4 sequence 1).

Every view declares permission_classes explicitly (SE-4). Views stay thin:
the lifecycle is in lifecycle.py, which audits every step (SE-10).
Records are scoped on the server (SE-5, History.Privacy): a customer sees
only their own bookings, Branch Staff and Branch Managers their branch's,
an Administrator all. A booking outside the caller's scope is a 404.
"""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView, RetrieveAPIView
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers import DetailSerializer
from apps.core.audit import record_audit
from apps.core.permissions import (
    IsAdministrator,
    IsBranchManager,
    IsBranchStaff,
    IsCustomer,
    scope_queryset,
)
from apps.fleet.services.availability import RentalPeriodError
from apps.payments.pdf import render_invoice_pdf

from . import lifecycle
from .eligibility import NotEligibleError
from .models import Booking
from .serializers import (
    BookingDetailSerializer,
    BookingErrorSerializer,
    BookingSerializer,
    CreateBookingSerializer,
    PayBookingSerializer,
)

TAG = "Bookings"
STAFF = IsBranchStaff | IsBranchManager | IsAdministrator


class ReadOnly(BasePermission):
    def has_permission(self, request, view) -> bool:
        return request.method in SAFE_METHODS


def scoped_bookings(user):
    bookings = Booking.objects.select_related(
        "vehicle__category", "pickup_branch", "discount_code", "invoice", "tariff"
    ).prefetch_related("add_ons__add_on")
    return scope_queryset(
        bookings, user, customer_lookup="customer_id", branch_lookup="pickup_branch_id"
    )


def refusal(exc: Exception) -> Response:
    """Turn a lifecycle refusal into its HTTP answer (400 field errors, 400/402/409 with a code)."""
    if isinstance(exc, RentalPeriodError):
        raise ValidationError({exc.field: [str(exc)]}) from exc
    if isinstance(exc, lifecycle.BookingError) and exc.field:
        raise ValidationError({exc.field: [str(exc)]}) from exc
    if isinstance(exc, NotEligibleError):
        return Response({"detail": str(exc), "code": exc.code}, status=status.HTTP_400_BAD_REQUEST)
    assert isinstance(exc, lifecycle.BookingError)
    return Response({"detail": str(exc), "code": exc.code}, status=exc.status)


REFUSALS = (RentalPeriodError, NotEligibleError, lifecycle.BookingError)


def _detail(booking, request, code=status.HTTP_200_OK) -> Response:
    booking = scoped_bookings(request.user).get(pk=booking.pk)
    return Response(
        BookingDetailSerializer(booking, context={"request": request}).data, status=code
    )


class BookingListCreateView(ListCreateAPIView):
    """History.View (GET, newest pickup first) and Book.Create (POST, customers only)."""

    permission_classes = [IsCustomer | (STAFF & ReadOnly)]
    serializer_class = BookingSerializer
    filterset_fields = ["status"]

    def get_queryset(self):
        return scoped_bookings(self.request.user)

    @extend_schema(tags=[TAG], summary="List bookings (History.View, History.Privacy)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=[TAG],
        summary="Create a booking and hold the vehicle (Booking.create_booking())",
        description=(
            "Exp 4 sequence 1: checks the period (BR-5), the terms (Book.Quote.Terms, SA-1), "
            "eligibility (Licence.is_valid(): BR-2, BR-3, BR-4), availability "
            "(Vehicle.check_availability(), BR-1) and prices it (Tariff.calculate_price(), "
            "BR-6). The booking is Pending Payment with a 15-minute hold (Book.Hold). "
            "Refusals: 400 with `code` licence_not_verified, licence_expired, "
            "licence_expires_before_return, licence_category, under_age, "
            "customer_blacklisted or outstanding_due; 409 `vehicle_unavailable`."
        ),
        request=CreateBookingSerializer,
        responses={
            201: BookingDetailSerializer,
            400: BookingErrorSerializer,
            409: BookingErrorSerializer,
        },
        examples=[
            OpenApiExample(
                "Two days with a child seat",
                request_only=True,
                value={
                    "vehicle": 12,
                    "pickup_datetime": "2026-10-20T04:30:00Z",
                    "return_datetime": "2026-10-22T04:30:00Z",
                    "add_ons": [{"add_on": 3, "quantity": 1}],
                    "discount_code": "WELCOME10",
                    "terms_accepted": True,
                    "safety_notice_acknowledged": False,
                },
            )
        ],
    )
    def post(self, request, *args, **kwargs):
        serializer = CreateBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            booking = lifecycle.create_booking(
                request.user.customer,
                vehicle=data["vehicle"],
                pickup=data["pickup_datetime"],
                return_=data["return_datetime"],
                add_ons=[(line["add_on"], line["quantity"]) for line in data["add_ons"]],
                discount_code=data["discount_code"],
                terms_accepted=data["terms_accepted"],
                safety_notice_acknowledged=data["safety_notice_acknowledged"],
                request=request,
            )
        except REFUSALS as exc:
            return refusal(exc)
        return _detail(booking, request, status.HTTP_201_CREATED)


class BookingDetailView(RetrieveAPIView):
    permission_classes = [IsCustomer | STAFF]
    serializer_class = BookingDetailSerializer

    def get_queryset(self):
        return scoped_bookings(self.request.user)

    @extend_schema(tags=[TAG], summary="A booking with its itemised price")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class BookingHoldView(APIView):
    """Book.Hold.Expire: hold an expired booking again with the details kept."""

    permission_classes = [IsCustomer]

    @extend_schema(
        tags=[TAG],
        summary="Hold a Draft booking again (Book.Hold.Expire)",
        description="Rechecks eligibility and availability and re-prices at today's tariff.",
        request=None,
        responses={
            200: BookingDetailSerializer,
            400: BookingErrorSerializer,
            409: BookingErrorSerializer,
        },
    )
    def post(self, request, pk: int):
        get_object_or_404(Booking, pk=pk, customer=request.user.customer)
        try:
            booking = lifecycle.hold_again(request.user.customer, pk, request=request)
        except REFUSALS as exc:
            return refusal(exc)
        return _detail(booking, request)


class BookingPayView(APIView):
    """Pay.Authorize and Book.Done (Payment.authorize() -> Invoice.generate_invoice())."""

    permission_classes = [IsCustomer]

    @extend_schema(
        tags=[TAG],
        summary="Pay for a held booking and confirm it (Pay.Authorize, Book.Done)",
        description=(
            "SE-9: the customer's password is required. One gateway authorisation for the "
            "rental and the deposit. Success: Confirmed, with booking reference, pickup code, "
            "transaction id and invoice. 402 `payment_declined`: the hold is kept. 409 "
            "`hold_expired`, `price_changed`, `discount_unavailable` or `invalid_state`. "
            "Repeating the same idempotency key never charges twice (Pay.Idempotent)."
        ),
        request=PayBookingSerializer,
        responses={
            200: BookingDetailSerializer,
            400: DetailSerializer,
            402: BookingErrorSerializer,
            409: BookingErrorSerializer,
        },
        examples=[
            OpenApiExample(
                "Sandbox card",
                request_only=True,
                value={
                    "payment_token": "tok_visa",
                    "idempotency_key": "pay-7f3a9c21",
                    "password": "…",
                },
            )
        ],
    )
    def post(self, request, pk: int):
        get_object_or_404(Booking, pk=pk, customer=request.user.customer)
        serializer = PayBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not request.user.check_password(data["password"]):  # SE-9
            record_audit(
                request.user,
                "Payment Re-authentication Failed",
                entity_label="bookings.Booking",
                entity_id=pk,
                request=request,
            )
            raise ValidationError({"password": ["That password is not correct."]})
        try:
            booking = lifecycle.pay_booking(
                request.user.customer,
                pk,
                payment_token=data["payment_token"],
                idempotency_key=data["idempotency_key"],
                request=request,
            )
        except REFUSALS as exc:
            return refusal(exc)
        return _detail(booking, request)


class BookingInvoiceView(APIView):
    """Pay.Invoice: the issued invoice as a PDF (History.Download)."""

    permission_classes = [IsCustomer | STAFF]

    @extend_schema(
        tags=[TAG],
        summary="Download the invoice PDF",
        responses={(200, "application/pdf"): OpenApiResponse(description="The invoice PDF.")},
    )
    def get(self, request, pk: int):
        booking = get_object_or_404(scoped_bookings(request.user), pk=pk)
        invoice = getattr(booking, "invoice", None)
        if invoice is None:
            return Response(
                {"detail": "This booking has no invoice yet."}, status=status.HTTP_404_NOT_FOUND
            )
        response = HttpResponse(render_invoice_pdf(invoice), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{invoice.invoice_number}.pdf"'
        return response
