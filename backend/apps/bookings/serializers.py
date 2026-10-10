"""Bookings API serializers. Money is Decimal, sent as strings (CO-6)."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.fleet.models import Vehicle
from apps.pricing.serializers import AddOnRequestSerializer, QuoteSerializer

from .lifecycle import booking_quote
from .models import Booking


class CreateBookingSerializer(serializers.Serializer):
    """Book.Create: one vehicle, the period, add-ons, a discount code and the terms (BK5)."""

    vehicle = serializers.PrimaryKeyRelatedField(
        queryset=Vehicle.objects.select_related("category", "home_branch")
    )
    pickup_datetime = serializers.DateTimeField()
    return_datetime = serializers.DateTimeField()
    add_ons = AddOnRequestSerializer(many=True, required=False, default=list)
    discount_code = serializers.CharField(
        max_length=32, required=False, allow_blank=True, default=""
    )
    terms_accepted = serializers.BooleanField(help_text="Book.Quote.Terms: must be true.")
    safety_notice_acknowledged = serializers.BooleanField(
        default=False, help_text="SA-1: must be true for a two-wheeler."
    )


class PayBookingSerializer(serializers.Serializer):
    """Pay.Authorize with a gateway token (CO-2: never card details); SE-9 re-authentication."""

    payment_token = serializers.CharField(
        max_length=255,
        help_text="Token from the gateway's hosted fields. Sandbox: tok_visa, tok_decline.",
    )
    idempotency_key = serializers.RegexField(
        r"^[A-Za-z0-9_-]{8,40}$",
        help_text="Pay.Idempotent: one key per payment attempt; repeating it never charges twice.",
    )
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, help_text="SE-9: re-authentication before payment."
    )


class BookingVehicleSerializer(serializers.ModelSerializer):
    vehicle_type = serializers.CharField(read_only=True)
    category = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Vehicle
        fields = ["id", "brand", "model", "registration_no", "vehicle_type", "category"]


class BookingAddOnLineSerializer(serializers.Serializer):
    add_on_id = serializers.IntegerField()
    name = serializers.CharField(source="add_on.name")
    quantity = serializers.IntegerField()
    daily_rate = serializers.DecimalField(max_digits=12, decimal_places=2)


class BookingSerializer(serializers.ModelSerializer):
    """A booking as its customer, branch staff or an Administrator sees it (History.Privacy)."""

    vehicle = BookingVehicleSerializer(read_only=True)
    pickup_branch = serializers.CharField(source="pickup_branch.branch_name", read_only=True)
    pickup_branch_id = serializers.IntegerField(read_only=True)
    add_ons = BookingAddOnLineSerializer(many=True, read_only=True)
    discount_code = serializers.CharField(source="discount_code.code", default="", read_only=True)
    pickup_code = serializers.SerializerMethodField()
    invoice_number = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id",
            "booking_reference",
            "status",
            "vehicle",
            "pickup_branch",
            "pickup_branch_id",
            "pickup_datetime",
            "return_datetime",
            "hold_expires_at",
            "confirmed_at",
            "pickup_code",
            "add_ons",
            "total_amount",
            "security_deposit",
            "discount_code",
            "discount_amount",
            "terms_accepted_at",
            "safety_notice_acknowledged_at",
            "invoice_number",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_blank=True))
    def get_pickup_code(self, booking: Booking) -> str:
        """Book.Done.Store: the code is the customer's to present; staff never see it here."""
        request = self.context.get("request")
        user = getattr(request, "user", None)
        is_owner = (
            user is not None
            and getattr(getattr(user, "customer", None), "pk", None) == booking.customer_id
        )
        return booking.pickup_code if is_owner else ""

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_invoice_number(self, booking: Booking) -> str | None:
        invoice = getattr(booking, "invoice", None)
        return invoice.invoice_number if invoice else None


class BookingDetailSerializer(BookingSerializer):
    """Adds the itemised price (Book.Quote.Display) and the payment transaction (Pay.Confirm.OK)."""

    price = serializers.SerializerMethodField()
    transaction_id = serializers.SerializerMethodField()

    class Meta(BookingSerializer.Meta):
        fields = [*BookingSerializer.Meta.fields, "price", "transaction_id"]
        read_only_fields = fields

    @extend_schema_field(QuoteSerializer)
    def get_price(self, booking: Booking) -> dict:
        return QuoteSerializer(booking_quote(booking)).data

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_transaction_id(self, booking: Booking) -> str | None:
        payment = booking.payments.filter(status="Succeeded", purpose="Security Deposit").first()
        return payment.transaction_id if payment else None


class BookingErrorSerializer(serializers.Serializer):
    """A refusal with a stable code, e.g. licence_not_verified, vehicle_unavailable."""

    detail = serializers.CharField()
    code = serializers.CharField()
