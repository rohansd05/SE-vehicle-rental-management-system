"""Bookings API views (SRS 3.1, 3.4; Exp 4 sequence 1).

Every view declares permission_classes explicitly (SE-4). Views stay thin:
the lifecycle is in lifecycle.py, which audits every step (SE-10).
Records are scoped on the server (SE-5, History.Privacy): a customer sees
only their own bookings, Branch Staff and Branch Managers their branch's,
an Administrator all. A booking outside the caller's scope is a 404.
"""

import django_filters
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveAPIView
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers import DetailSerializer
from apps.core.choices import VehicleType
from apps.core.permissions import (
    IsAdministrator,
    IsBranchManager,
    IsBranchStaff,
    IsCustomer,
    scope_queryset,
)
from apps.fleet.services.availability import RentalPeriodError
from apps.payments.pdf import render_invoice_pdf
from apps.payments.reauth import require_password
from apps.payments.services import PaymentError

from . import lifecycle, services
from .eligibility import NotEligibleError
from .models import Booking
from .serializers import (
    BookingDetailSerializer,
    BookingErrorSerializer,
    BookingSerializer,
    CancelBookingSerializer,
    CancellationQuoteSerializer,
    CashDueBookingSerializer,
    CreateBookingSerializer,
    ExtendBookingSerializer,
    ExtensionQuoteSerializer,
    ExtensionRequestSerializer,
    ModificationQuoteSerializer,
    ModificationRequestSerializer,
    ModifyBookingSerializer,
    PayBookingSerializer,
    RecordCashSerializer,
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
    assert isinstance(exc, lifecycle.BookingError | PaymentError)
    return Response({"detail": str(exc), "code": exc.code}, status=exc.status)


REFUSALS = (RentalPeriodError, NotEligibleError, lifecycle.BookingError, PaymentError)


def _detail(booking, request, code=status.HTTP_200_OK) -> Response:
    booking = scoped_bookings(request.user).get(pk=booking.pk)
    return Response(
        BookingDetailSerializer(booking, context={"request": request}).data, status=code
    )


class BookingFilter(django_filters.FilterSet):
    """History.View: "filter them by date range, status and vehicle type or search them
    by booking reference". The date range applies to the pickup date (local, CO-6)."""

    pickup_from = django_filters.DateFilter(field_name="pickup_datetime", lookup_expr="date__gte")
    pickup_to = django_filters.DateFilter(field_name="pickup_datetime", lookup_expr="date__lte")
    vehicle_type = django_filters.ChoiceFilter(
        field_name="vehicle__category__vehicle_type", choices=VehicleType.choices
    )
    reference = django_filters.CharFilter(field_name="booking_reference", lookup_expr="icontains")

    class Meta:
        model = Booking
        fields = ["status"]


class BookingListCreateView(ListCreateAPIView):
    """History.View (GET, newest pickup first) and Book.Create (POST, customers only)."""

    permission_classes = [IsCustomer | (STAFF & ReadOnly)]
    serializer_class = BookingSerializer
    filterset_class = BookingFilter

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
    """Pay.Method, Pay.Authorize, Book.Done: Payment.authorize() -> Invoice.generate_invoice()."""

    permission_classes = [IsCustomer]

    @extend_schema(
        tags=[TAG],
        summary="Pay for a held booking and confirm it (Pay.Method, Pay.Authorize, Book.Done)",
        description=(
            "SE-9: the customer's password is required. `method` card or online (UPI, net "
            "banking, wallet; D6): one gateway authorisation for the rental and the deposit; "
            "success is Confirmed, with booking reference, pickup code, transaction id and "
            "invoice. `method` cash (BR-9): the booking stays Pending Payment, held for the "
            "collection, until branch staff record the cash. 402 `payment_declined`: the hold "
            "is kept. 409 `hold_expired`, `price_changed`, `discount_unavailable` or "
            "`invalid_state`. Repeating the same idempotency key never charges twice "
            "(Pay.Idempotent)."
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
            ),
            OpenApiExample(
                "Sandbox UPI",
                request_only=True,
                value={
                    "method": "online",
                    "channel": "UPI",
                    "upi_id": "asha@okbank",
                    "payment_token": "tok_upi",
                    "idempotency_key": "pay-7f3a9c22",
                    "password": "…",
                },
            ),
            OpenApiExample(
                "Cash at collection",
                request_only=True,
                value={"method": "cash", "idempotency_key": "pay-7f3a9c23", "password": "…"},
            ),
        ],
    )
    def post(self, request, pk: int):
        get_object_or_404(Booking, pk=pk, customer=request.user.customer)
        serializer = PayBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        require_password(request, data["password"], entity_label="bookings.Booking", entity_id=pk)
        try:
            booking = lifecycle.pay_booking(
                request.user.customer,
                pk,
                payment_token=data["payment_token"],
                idempotency_key=data["idempotency_key"],
                method=data["method"],
                channel=data["channel"],
                upi_id=data["upi_id"],
                request=request,
            )
        except REFUSALS as exc:
            return refusal(exc)
        return _detail(booking, request)


def awaiting_cash(user):
    """BR-9: the branch's bookings whose customers pay cash at collection, held and unpaid."""
    return (
        scoped_bookings(user)
        .select_related("customer__user")
        .filter(
            status=Booking.Status.PENDING_PAYMENT,
            cash_on_collection=True,
            hold_expires_at__gt=timezone.now(),
        )
        .order_by("pickup_datetime")
    )


class AwaitingCashListView(ListAPIView):
    """BR-9: the cash desk's list of collections to be paid in cash."""

    permission_classes = [IsBranchStaff]
    serializer_class = CashDueBookingSerializer

    def get_queryset(self):
        return awaiting_cash(self.request.user)

    @extend_schema(tags=[TAG], summary="Bookings waiting for cash at collection (BR-9)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class BookingCashView(APIView):
    """BR-9, Book.Confirm.Pay: record the cash received and confirm the booking (Book.Done)."""

    permission_classes = [IsBranchStaff]

    @extend_schema(
        tags=[TAG],
        summary="Record the cash received and confirm the booking (BR-9, Book.Done)",
        description=(
            "Only Branch Staff of the pickup branch: the CashPayment names them. SE-9: their "
            "password is required. `amount_received` must equal the rental plus the deposit. "
            "The booking is confirmed in the same single transaction as a card payment. 409 "
            "`invalid_state`, `hold_expired`, `price_changed` or `discount_unavailable`. The "
            "same idempotency key never records the cash twice."
        ),
        request=RecordCashSerializer,
        responses={
            200: BookingDetailSerializer,
            400: DetailSerializer,
            409: BookingErrorSerializer,
        },
    )
    def post(self, request, pk: int):
        get_object_or_404(scoped_bookings(request.user), pk=pk)
        serializer = RecordCashSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        require_password(request, data["password"], entity_label="bookings.Booking", entity_id=pk)
        try:
            booking = lifecycle.record_cash_payment(
                request.user,
                pk,
                amount_received=data["amount_received"],
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


# ─── Module R2: Modify / Cancel Booking (Exp 2 UC 4) and Book.Extend ──────
# The customer only (UC 4 actor; Book.Extend "permit the customer"), on their
# own booking. Every action that moves money asks for the password (SE-9) and
# takes the amounts the customer was shown.


def _own_booking(request, pk: int) -> Booking:
    return get_object_or_404(Booking, pk=pk, customer=request.user.customer)


def _payment(data) -> dict:
    return {field: data[field] for field in ("method", "payment_token", "channel", "upi_id")}


def _modification(data) -> services.Modification:
    return services.Modification(
        pickup=data["pickup_datetime"],
        return_=data["return_datetime"],
        branch=data["pickup_branch"],
        add_ons=[(line["add_on"], line["quantity"]) for line in data["add_ons"]],
        vehicle=data["vehicle"],
    )


class BookingCancelView(APIView):
    """Book.Cancel and Book.Cancel.Release (Exp 3 Booking.cancel_booking())."""

    permission_classes = [IsCustomer]

    @extend_schema(
        tags=[TAG],
        summary="The refund if this booking is cancelled now (Book.Cancel, BR-8)",
        responses={200: CancellationQuoteSerializer, 409: BookingErrorSerializer},
    )
    def get(self, request, pk: int):
        _own_booking(request, pk)
        try:
            quote = services.cancellation_quote(request.user.customer, pk)
        except REFUSALS as exc:
            return refusal(exc)
        return Response(CancellationQuoteSerializer(quote).data)

    @extend_schema(
        tags=[TAG],
        summary="Cancel a booking before collection (Book.Cancel, Book.Cancel.Release)",
        description=(
            "SE-9: the password is required. `expected_refund` is the total refund the "
            "customer was shown; 409 `refund_changed` if BR-8 now gives another amount. "
            "The vehicle is released, the booking Cancelled, the rental share (BR-8) and the "
            "whole deposit refunded through the payments service (a refund above the "
            "automatic approval limit waits for an Administrator, UC 13), and the customer "
            "and the branch notified. An unpaid cash-at-collection booking is cancelled "
            "with no refund. 409 `invalid_state` for an Active or other booking."
        ),
        request=CancelBookingSerializer,
        responses={
            200: BookingDetailSerializer,
            400: DetailSerializer,
            409: BookingErrorSerializer,
        },
    )
    def post(self, request, pk: int):
        _own_booking(request, pk)
        serializer = CancelBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        require_password(request, data["password"], entity_label="bookings.Booking", entity_id=pk)
        try:
            booking = services.cancel_booking(
                request.user.customer,
                pk,
                expected_refund=data["expected_refund"],
                request=request,
            )
        except REFUSALS as exc:
            return refusal(exc)
        return _detail(booking, request)


class BookingModifyQuoteView(APIView):
    """Exp 2 UC 4 step 3: availability and the new price; nothing is saved."""

    permission_classes = [IsCustomer]

    @extend_schema(
        tags=[TAG],
        summary="Price a change of period, branch or add-ons (Book.Modify, Book.Modify.Price)",
        description=(
            "Rechecks BR-5 and the licence (BR-2) and reprices at the booking's own tariff "
            "(BR-13). `extra_charge` is charged at once; `refund_amount` is the excess "
            "refunded under BR-8. When the vehicle is not free, `vehicle_free` is false and "
            "`alternatives` lists vehicles of the same category at the same tariff (UC 4 "
            "extension 3a). 409 `modification_cutoff` less than 12 hours before pickup."
        ),
        request=ModificationRequestSerializer,
        responses={
            200: ModificationQuoteSerializer,
            400: BookingErrorSerializer,
            409: BookingErrorSerializer,
        },
    )
    def post(self, request, pk: int):
        _own_booking(request, pk)
        serializer = ModificationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            quote = services.modification_quote(
                request.user.customer, pk, _modification(serializer.validated_data)
            )
        except REFUSALS as exc:
            return refusal(exc)
        return Response(ModificationQuoteSerializer(quote).data)


class BookingModifyView(APIView):
    """Book.Modify and Book.Modify.Price (Exp 3 Booking.modify_booking())."""

    permission_classes = [IsCustomer]

    @extend_schema(
        tags=[TAG],
        summary="Modify a confirmed booking (Book.Modify, Book.Modify.Price)",
        description=(
            "SE-9: the password is required. `expected_charge` and `expected_refund` are the "
            "amounts the customer was shown; 409 `price_changed` otherwise. An extra charge "
            "is authorised at once by card or on-line (402 `payment_declined` changes "
            "nothing); an excess is refunded under BR-8. 409 `vehicle_unavailable`, "
            "`modification_cutoff` or `invalid_state`. The same idempotency key never "
            "charges or refunds twice (Pay.Idempotent)."
        ),
        request=ModifyBookingSerializer,
        responses={
            200: BookingDetailSerializer,
            400: DetailSerializer,
            402: BookingErrorSerializer,
            409: BookingErrorSerializer,
        },
    )
    def post(self, request, pk: int):
        _own_booking(request, pk)
        serializer = ModifyBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        require_password(request, data["password"], entity_label="bookings.Booking", entity_id=pk)
        try:
            booking = services.modify_booking(
                request.user.customer,
                pk,
                _modification(data),
                expected_charge=data["expected_charge"],
                expected_refund=data["expected_refund"],
                idempotency_key=data["idempotency_key"],
                payment=_payment(data),
                request=request,
            )
        except REFUSALS as exc:
            return refusal(exc)
        return _detail(booking, request)


class BookingExtendQuoteView(APIView):
    """Book.Extend: the extra charge for a later return; nothing is saved."""

    permission_classes = [IsCustomer]

    @extend_schema(
        tags=[TAG],
        summary="Price an extension of an active rental (Book.Extend, BR-5)",
        request=ExtensionRequestSerializer,
        responses={
            200: ExtensionQuoteSerializer,
            400: BookingErrorSerializer,
            409: BookingErrorSerializer,
        },
    )
    def post(self, request, pk: int):
        _own_booking(request, pk)
        serializer = ExtensionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            quote = services.extension_quote(
                request.user.customer, pk, serializer.validated_data["return_datetime"]
            )
        except REFUSALS as exc:
            return refusal(exc)
        return Response(ExtensionQuoteSerializer(quote).data)


class BookingExtendView(APIView):
    """Book.Extend (Exp 3 Booking.extend_booking())."""

    permission_classes = [IsCustomer]

    @extend_schema(
        tags=[TAG],
        summary="Extend an active rental (Book.Extend)",
        description=(
            "SE-9: the password is required. Only an Active booking, when no booking of the "
            "vehicle conflicts (409 `vehicle_unavailable`) and the whole rental stays within "
            "30 days (BR-5, 400). The extra charge is authorised before the new return time "
            "takes effect (402 `payment_declined` changes nothing); 409 `price_changed` if it "
            "differs from `expected_charge`."
        ),
        request=ExtendBookingSerializer,
        responses={
            200: BookingDetailSerializer,
            400: DetailSerializer,
            402: BookingErrorSerializer,
            409: BookingErrorSerializer,
        },
    )
    def post(self, request, pk: int):
        _own_booking(request, pk)
        serializer = ExtendBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        require_password(request, data["password"], entity_label="bookings.Booking", entity_id=pk)
        try:
            booking = services.extend_booking(
                request.user.customer,
                pk,
                data["return_datetime"],
                expected_charge=data["expected_charge"],
                idempotency_key=data["idempotency_key"],
                payment=_payment(data),
                request=request,
            )
        except REFUSALS as exc:
            return refusal(exc)
        return _detail(booking, request)
