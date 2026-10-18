"""Staff accounts and blacklist API (Module N3; Fleet.Users, BR-4, Exp 2 use case 12),
mounted under /api/v1/admin/. Administrator only (SE-4): every view declares
IsAdministrator.

Kept apart from the sign-in and licence views (views.py, Rohan's). Views stay
thin: admin_services.py validates, writes and audits; a booking is cancelled
through R2's bookings.services.cancel_booking().
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings import services as bookings
from apps.bookings.serializers import (
    BookingErrorSerializer,
    CancelBookingSerializer,
    CancellationQuoteSerializer,
)
from apps.bookings.views import REFUSALS, refusal
from apps.core.permissions import IsAdministrator
from apps.payments.reauth import require_password

from . import admin_services
from .admin_serializers import (
    AdminCustomerDetailSerializer,
    AdminCustomerSerializer,
    OpenBookingSerializer,
    ReasonSerializer,
    StaffAccountSerializer,
    StaffCreateSerializer,
    StaffUpdateSerializer,
)
from .models import User
from .serializers import DetailSerializer

TAG = "Users and blacklist"


def _refused(exc: admin_services.UserAdminError):
    raise ValidationError({exc.field or "detail": [str(exc)]}) from exc


def _staff():
    return User.objects.filter(role__in=admin_services.STAFF_ROLES).select_related(
        "branch_staff__branch",
        "maintenance_technician__unsafe_clearance_authorisation",
        "administrator__branchmanager__branch",
    )


def _account(user: User, code=status.HTTP_200_OK) -> Response:
    return Response(StaffAccountSerializer(_staff().get(pk=user.pk)).data, status=code)


class StaffListView(ListAPIView):
    """Fleet.Users: Branch Staff, Maintenance Technician and Branch Manager accounts."""

    permission_classes = [IsAdministrator]
    serializer_class = StaffAccountSerializer
    filter_backends: list = []

    def get_queryset(self):
        params = self.request.query_params
        accounts = _staff().order_by("name", "pk")
        if params.get("role"):
            accounts = accounts.filter(role=params["role"])
        if params.get("is_active") in ("true", "false"):
            accounts = accounts.filter(is_active=params["is_active"] == "true")
        if query := params.get("q", "").strip():
            accounts = accounts.filter(
                Q(name__icontains=query) | Q(email__icontains=query) | Q(mobile_no__icontains=query)
            )
        return accounts

    @extend_schema(
        tags=[TAG],
        summary="Staff accounts (Fleet.Users)",
        parameters=[
            OpenApiParameter(
                "role",
                str,
                required=False,
                description="BRANCH_STAFF, MAINTENANCE_TECHNICIAN or BRANCH_MANAGER",
            ),
            OpenApiParameter("is_active", str, enum=["true", "false"], required=False),
            OpenApiParameter("q", str, required=False, description="Name, e-mail or mobile"),
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        tags=[TAG],
        summary="Create a staff account (Fleet.Users, UC 12 step 1)",
        description=(
            "Branch Staff and Branch Managers need a `branch`, a technician a `workshop`. "
            "The password is the first one; the user may change it after signing in."
        ),
        request=StaffCreateSerializer,
        responses={201: StaffAccountSerializer, 400: DetailSerializer},
    )
    def post(self, request):
        serializer = StaffCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = admin_services.create_staff_account(
                request.user, serializer.validated_data, request
            )
        except admin_services.UserAdminError as exc:
            _refused(exc)
        return _account(user, status.HTTP_201_CREATED)


class StaffDetailView(APIView):
    permission_classes = [IsAdministrator]

    @extend_schema(tags=[TAG], summary="A staff account", responses=StaffAccountSerializer)
    def get(self, request, pk: int):
        return _account(get_object_or_404(_staff(), pk=pk))

    @extend_schema(
        tags=[TAG],
        summary="Edit a staff account",
        request=StaffUpdateSerializer,
        responses={200: StaffAccountSerializer, 400: DetailSerializer},
    )
    def patch(self, request, pk: int):
        user = get_object_or_404(_staff(), pk=pk)
        serializer = StaffUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            admin_services.update_staff_account(
                user, request.user, serializer.validated_data, request
            )
        except admin_services.UserAdminError as exc:
            _refused(exc)
        return _account(user)


class _StaffActiveView(APIView):
    permission_classes = [IsAdministrator]
    active = True

    def post(self, request, pk: int):
        user = get_object_or_404(_staff(), pk=pk)
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            admin_services.set_account_active(
                user,
                request.user,
                active=self.active,
                reason=serializer.validated_data["reason"],
                request=request,
            )
        except admin_services.UserAdminError as exc:
            _refused(exc)
        return _account(user)


class StaffDisableView(_StaffActiveView):
    active = False

    @extend_schema(
        tags=[TAG],
        summary="Disable a staff account (Fleet.Users)",
        description="Every session ends at once and sign-in is refused; past actions stay.",
        request=ReasonSerializer,
        responses={200: StaffAccountSerializer, 400: DetailSerializer},
    )
    def post(self, request, pk: int):
        return super().post(request, pk)


class StaffEnableView(_StaffActiveView):
    active = True

    @extend_schema(
        tags=[TAG],
        summary="Re-enable a staff account (Fleet.Users)",
        request=ReasonSerializer,
        responses={200: StaffAccountSerializer, 400: DetailSerializer},
    )
    def post(self, request, pk: int):
        return super().post(request, pk)


class CustomerListView(ListAPIView):
    """BR-4: customers, to find one to blacklist, or the blacklist itself."""

    permission_classes = [IsAdministrator]
    serializer_class = AdminCustomerSerializer
    filter_backends: list = []

    def get_queryset(self):
        params = self.request.query_params
        customers = admin_services.customers_with_blacklist()
        if params.get("blacklisted") in ("true", "false"):
            customers = customers.filter(is_blacklisted=params["blacklisted"] == "true")
        if query := params.get("q", "").strip():
            customers = customers.filter(
                Q(user__name__icontains=query)
                | Q(user__email__icontains=query)
                | Q(user__mobile_no__icontains=query)
            )
        return customers

    @extend_schema(
        tags=[TAG],
        summary="Customers and the blacklist (BR-4)",
        parameters=[
            OpenApiParameter("blacklisted", str, enum=["true", "false"], required=False),
            OpenApiParameter("q", str, required=False, description="Name, e-mail or mobile"),
        ],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


def _customer_detail(pk: int, code=status.HTTP_200_OK) -> Response:
    customer = get_object_or_404(admin_services.customers_with_blacklist(), pk=pk)
    return Response(AdminCustomerDetailSerializer(customer).data, status=code)


class CustomerDetailView(APIView):
    permission_classes = [IsAdministrator]

    @extend_schema(
        tags=[TAG],
        summary="A customer with their Confirmed and Active bookings",
        responses=AdminCustomerDetailSerializer,
    )
    def get(self, request, pk: int):
        return _customer_detail(pk)


class _BlacklistView(APIView):
    permission_classes = [IsAdministrator]

    def change(self, request, pk: int, service):
        customer = get_object_or_404(admin_services.customers_with_blacklist(), pk=pk)
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            service(customer, request.user, serializer.validated_data["reason"], request)
        except admin_services.UserAdminError as exc:
            _refused(exc)
        return _customer_detail(pk)


class CustomerBlacklistView(_BlacklistView):
    @extend_schema(
        tags=[TAG],
        summary="Blacklist a customer with the reason (BR-4, UC 12 step 2)",
        description=(
            "New bookings are refused from now on. The answer lists the customer's Confirmed "
            "bookings, to decide on each (UC 12 extension 2a), and Active ones (return pending)."
        ),
        request=ReasonSerializer,
        responses={200: AdminCustomerDetailSerializer, 400: DetailSerializer},
    )
    def post(self, request, pk: int):
        return self.change(request, pk, admin_services.blacklist_customer)


class CustomerLiftBlacklistView(_BlacklistView):
    @extend_schema(
        tags=[TAG],
        summary="Take a customer off the blacklist, with the reason",
        request=ReasonSerializer,
        responses={200: AdminCustomerDetailSerializer, 400: DetailSerializer},
    )
    def post(self, request, pk: int):
        return self.change(request, pk, admin_services.lift_blacklist)


class CustomerBookingCancelView(APIView):
    """UC 12 extension 2a: cancel one Confirmed booking of a blacklisted customer,
    through R2's cancellation (BR-8)."""

    permission_classes = [IsAdministrator]

    def _customer(self, pk: int, booking_id: int):
        customer = get_object_or_404(admin_services.customers_with_blacklist(), pk=pk)
        get_object_or_404(admin_services.open_bookings(customer), pk=booking_id)
        return customer

    @extend_schema(
        tags=[TAG],
        summary="The refund if this booking is cancelled now (R2, BR-8)",
        responses={200: CancellationQuoteSerializer, 409: BookingErrorSerializer},
    )
    def get(self, request, pk: int, booking_id: int):
        customer = self._customer(pk, booking_id)
        try:
            quote = bookings.cancellation_quote(customer, booking_id)
        except REFUSALS as exc:
            return refusal(exc)
        return Response(CancellationQuoteSerializer(quote).data)

    @extend_schema(
        tags=[TAG],
        summary="Cancel the booking (R2's cancel_booking(), BR-8)",
        description=(
            "SE-9: the Administrator's password. `expected_refund` is the total shown; 409 "
            "`refund_changed` if BR-8 now gives another amount. An Active booking is never "
            "cancelled here (409 `invalid_state`)."
        ),
        request=CancelBookingSerializer,
        responses={
            200: OpenBookingSerializer,
            400: DetailSerializer,
            409: BookingErrorSerializer,
        },
    )
    def post(self, request, pk: int, booking_id: int):
        customer = self._customer(pk, booking_id)
        serializer = CancelBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        require_password(
            request, data["password"], entity_label="bookings.Booking", entity_id=booking_id
        )
        try:
            booking = admin_services.cancel_for_blacklist(
                customer,
                booking_id,
                request.user,
                expected_refund=data["expected_refund"],
                request=request,
            )
        except admin_services.UserAdminError as exc:
            _refused(exc)
        except REFUSALS as exc:
            return refusal(exc)
        return Response(OpenBookingSerializer(booking).data)
