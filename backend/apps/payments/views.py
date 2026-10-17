"""Payments API views (SRS 3.4 Pay.*; SI-1.4; UC 13 Approve Refund).

Every view declares permission_classes explicitly (SE-4) and stays thin:
the rules are in services.py, which audits every step (SE-10). Records are
scoped on the server (SE-5): a customer sees only their own refunds, Branch
Staff and Branch Managers their branch's, an Administrator all; anything
outside the caller's scope is a 404. Every endpoint that moves money asks
for the caller's password (SE-9) and takes an idempotency key
(Pay.Idempotent); the gateway notification is checked by its signature.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.models import Booking
from apps.bookings.serializers import BookingErrorSerializer
from apps.core.permissions import (
    IsAdministrator,
    IsBranchManager,
    IsBranchStaff,
    IsCustomer,
    scope_queryset,
)

from . import services
from .models import Payment, RefundRequest
from .reauth import require_password
from .serializers import (
    CaptureSerializer,
    DueSerializer,
    LedgerEntryResultSerializer,
    NotificationResultSerializer,
    PayDueSerializer,
    PayOutCashRefundSerializer,
    ReauthenticatedSerializer,
    RefundCreateSerializer,
    RefundSerializer,
    RejectRefundSerializer,
)

TAG = "Payments"
# UC 8 Return Vehicle and Pay.Refund are Branch Staff's; an Administrator may too.
SETTLERS = IsBranchStaff | IsAdministrator
ERRORS = {400: BookingErrorSerializer, 402: BookingErrorSerializer, 409: BookingErrorSerializer}


def refusal(exc: services.PaymentError) -> Response:
    return Response({"detail": str(exc), "code": exc.code}, status=exc.status)


def _refunds():
    return RefundRequest.objects.select_related(
        "original_payment__booking__customer__user", "requested_by", "decided_by", "refund"
    )


def scoped_refunds(user):
    return scope_queryset(
        _refunds(),
        user,
        customer_lookup="original_payment__booking__customer_id",
        branch_lookup="original_payment__booking__pickup_branch_id",
    )


def _refund_response(refund, code=status.HTTP_200_OK) -> Response:
    return Response(RefundSerializer(_refunds().get(pk=refund.pk)).data, status=code)


class DueView(APIView):
    """Pay.Dues, BR-4: see the outstanding due and clear it on-line at any time."""

    permission_classes = [IsCustomer]

    @extend_schema(tags=[TAG], summary="My outstanding due (Pay.Dues)", responses=DueSerializer)
    def get(self, request):
        due = request.user.customer.outstanding_due
        return Response(DueSerializer({"outstanding_due": due}).data)

    @extend_schema(
        tags=[TAG],
        summary="Pay the whole outstanding due on-line (Pay.Dues)",
        description=(
            "SE-9: the password is required. Card or an on-line channel (UPI, net banking, "
            "wallet; D6). On success the due is zero and booking is allowed again at once "
            "(BR-4). 402 `payment_declined`; 409 `no_due`. The same idempotency key never "
            "charges twice."
        ),
        request=PayDueSerializer,
        responses={200: DueSerializer, **ERRORS},
    )
    def post(self, request):
        serializer = PayDueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        customer = request.user.customer
        require_password(
            request, data["password"], entity_label="accounts.Customer", entity_id=customer.pk
        )
        try:
            payment = services.pay_due(
                customer,
                payment_token=data["payment_token"],
                idempotency_key=data["idempotency_key"],
                channel=data["channel"],
                upi_id=data["upi_id"],
                request=request,
            )
        except services.PaymentError as exc:
            return refusal(exc)
        customer.refresh_from_db(fields=["outstanding_due"])
        return Response(
            DueSerializer(
                {
                    "outstanding_due": customer.outstanding_due,
                    "transaction_id": payment.transaction_id,
                }
            ).data
        )


class BookingCaptureView(APIView):
    """SI-1.2, Exp 3 Payment.capture(): settle a booking's charges when they are final."""

    permission_classes = [SETTLERS]

    @extend_schema(
        tags=[TAG],
        summary="Capture a booking's payment with its final charges (SI-1.2)",
        description=(
            "Records each charge line and captures the uncaptured rental and deposit "
            "authorisation. Once per booking: the same key returns the first result; another "
            "key is 409 `already_captured`. 409 `not_paid`; 402 `capture_failed`."
        ),
        request=CaptureSerializer,
        responses={200: LedgerEntryResultSerializer(many=True), **ERRORS},
    )
    def post(self, request, pk: int):
        bookings = scope_queryset(
            Booking.objects.all(), request.user, branch_lookup="pickup_branch_id"
        )
        booking = get_object_or_404(bookings, pk=pk)
        serializer = CaptureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        require_password(request, data["password"], entity_label="bookings.Booking", entity_id=pk)
        lines = [services.ChargeLine(line["description"], line["amount"]) for line in data["lines"]]
        try:
            entries = services.capture_charges(
                booking,
                lines,
                request.user,
                idempotency_key=data["idempotency_key"],
                request=request,
            )
        except services.PaymentError as exc:
            return refusal(exc)
        return Response(LedgerEntryResultSerializer(entries, many=True).data)


class PaymentRefundView(APIView):
    """Pay.Refund, Exp 3 Payment.refund(): refund part or all of one payment."""

    permission_classes = [SETTLERS]

    @extend_schema(
        tags=[TAG],
        summary="Refund a payment to its original instrument (Pay.Refund)",
        description=(
            "Above REFUND_AUTO_APPROVAL_LIMIT the refund waits as Pending Approval for an "
            "Administrator (UC 13); otherwise it is issued at once. A cash refund is paid out "
            "by the branch staff member who asks for it. The same idempotency key returns the "
            "first refund (Pay.Idempotent)."
        ),
        request=RefundCreateSerializer,
        responses={201: RefundSerializer, **ERRORS},
    )
    def post(self, request, pk: int):
        payments = scope_queryset(
            Payment.objects.all(), request.user, branch_lookup="booking__pickup_branch_id"
        )
        payment = get_object_or_404(payments, pk=pk)
        serializer = RefundCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        require_password(request, data["password"], entity_label="payments.Payment", entity_id=pk)
        try:
            refund = services.refund_payment(
                payment,
                data["amount"],
                data["reason"],
                request.user,
                idempotency_key=data["idempotency_key"],
                request=request,
            )
        except services.PaymentError as exc:
            return refusal(exc)
        return _refund_response(refund, status.HTTP_201_CREATED)


class RefundListView(ListAPIView):
    """UC 13 step 1: the refunds waiting for approval (Administrator), and refunds in scope."""

    permission_classes = [IsAdministrator | IsBranchStaff | IsBranchManager | IsCustomer]
    serializer_class = RefundSerializer
    filterset_fields = ["status"]

    def get_queryset(self):
        return scoped_refunds(self.request.user)

    @extend_schema(
        tags=[TAG],
        summary="List refunds, oldest request first (UC 13)",
        parameters=[OpenApiParameter("status", enum=RefundRequest.Status.values)],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class RefundApproveView(APIView):
    """UC 13 step 3: approve; the refund is issued to the original instrument."""

    permission_classes = [IsAdministrator]

    @extend_schema(
        tags=[TAG],
        summary="Approve a refund and issue it (UC 13)",
        description="SE-9: the password is required. 409 `not_pending`; 402 `capture_failed`.",
        request=ReauthenticatedSerializer,
        responses={200: RefundSerializer, **ERRORS},
    )
    def post(self, request, pk: int):
        refund = get_object_or_404(scoped_refunds(request.user), pk=pk)
        serializer = ReauthenticatedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        require_password(
            request,
            serializer.validated_data["password"],
            entity_label="payments.RefundRequest",
            entity_id=pk,
        )
        try:
            refund = services.approve_refund(refund, request.user, request=request)
        except services.PaymentError as exc:
            return refusal(exc)
        return _refund_response(refund)


class RefundRejectView(APIView):
    """UC 13 extension 2a: reject with a reason; the customer is notified."""

    permission_classes = [IsAdministrator]

    @extend_schema(
        tags=[TAG],
        summary="Reject a refund with a reason (UC 13)",
        request=RejectRefundSerializer,
        responses={200: RefundSerializer, **ERRORS},
    )
    def post(self, request, pk: int):
        refund = get_object_or_404(scoped_refunds(request.user), pk=pk)
        serializer = RejectRefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        require_password(
            request, data["password"], entity_label="payments.RefundRequest", entity_id=pk
        )
        try:
            refund = services.reject_refund(refund, request.user, data["reason"], request=request)
        except services.PaymentError as exc:
            return refusal(exc)
        return _refund_response(refund)


class RefundPayOutView(APIView):
    """Pay.Refund: a named branch staff member pays an approved cash refund out."""

    permission_classes = [IsBranchStaff]

    @extend_schema(
        tags=[TAG],
        summary="Record an approved cash refund as paid out (Pay.Refund)",
        request=PayOutCashRefundSerializer,
        responses={200: RefundSerializer, **ERRORS},
    )
    def post(self, request, pk: int):
        refund = get_object_or_404(scoped_refunds(request.user), pk=pk)
        serializer = PayOutCashRefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        require_password(
            request,
            serializer.validated_data["password"],
            entity_label="payments.RefundRequest",
            entity_id=pk,
        )
        try:
            refund = services.pay_out_cash_refund(refund, request.user, request=request)
        except services.PaymentError as exc:
            return refusal(exc)
        return _refund_response(refund)


class GatewayNotificationView(APIView):
    """SI-1.4: asynchronous payment and refund notifications from the gateway.

    No user signs in here: the gateway's signature (X-Gateway-Signature) is
    the credential, checked before anything is read.
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        tags=[TAG],
        summary="Receive a signed gateway notification (SI-1.4)",
        description=(
            "Body: JSON with `id`, `type` (e.g. refund.processed, refund.failed) and "
            "`transaction_id`. A repeated `id` changes nothing (Pay.Idempotent). 403 "
            "`invalid_signature`."
        ),
        request={"application/json": {"type": "object"}},
        responses={200: NotificationResultSerializer, 400: BookingErrorSerializer},
    )
    def post(self, request):
        signature = request.headers.get("X-Gateway-Signature", "")
        try:
            notification, created = services.handle_notification(
                request.body, signature, request=request
            )
        except services.PaymentError as exc:
            return refusal(exc)
        return Response({"event_id": notification.event_id, "duplicate": not created})
