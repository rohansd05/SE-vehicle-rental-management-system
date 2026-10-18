"""Bookings API serializers. Money is Decimal, sent as strings (CO-6)."""

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.fleet.models import Branch, Vehicle
from apps.payments.models import OnlinePayment, RefundRequest
from apps.payments.serializers import RefundSerializer
from apps.pricing.serializers import AddOnRequestSerializer, QuoteSerializer

from .lifecycle import booking_quote
from .models import Booking, Rating
from .services import rating_editable_until, rating_open_until


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
    delivery_address = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=500,
        help_text="Book.Deliver.Location: required with the doorstep delivery add-on.",
    )
    delivery_pincode = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=6,
        help_text="Six digits, within the pickup branch's serviceable areas.",
    )


class PayBookingSerializer(serializers.Serializer):
    """Pay.Method and Pay.Authorize with a gateway token (CO-2: never card details); SE-9.

    card: a token from the hosted fields. online: a D6 channel (UPI, net
    banking, wallet) and its token. cash: BR-9, paid at the branch on
    collection; no token.
    """

    method = serializers.ChoiceField(choices=["card", "online", "cash"], default="card")
    payment_token = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default="",
        help_text="Token from the gateway's hosted fields. Sandbox: tok_visa, tok_decline.",
    )
    channel = serializers.ChoiceField(
        choices=OnlinePayment.Channel.choices, required=False, allow_blank=True, default=""
    )
    upi_id = serializers.RegexField(
        r"^[A-Za-z0-9._-]{2,64}@[A-Za-z0-9]{2,32}$", required=False, allow_blank=True, default=""
    )
    idempotency_key = serializers.RegexField(
        r"^[A-Za-z0-9_-]{8,40}$",
        help_text="Pay.Idempotent: one key per payment attempt; repeating it never charges twice.",
    )
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, help_text="SE-9: re-authentication before payment."
    )

    def validate(self, attrs):
        if attrs["method"] != "cash" and not attrs["payment_token"]:
            raise serializers.ValidationError({"payment_token": ["This field is required."]})
        if attrs["method"] == "online" and not attrs["channel"]:
            raise serializers.ValidationError({"channel": ["Choose UPI, net banking or a wallet."]})
        return attrs


class RecordCashSerializer(serializers.Serializer):
    """BR-9: the cash a named branch staff member received at collection; SE-9."""

    amount_received = serializers.DecimalField(
        max_digits=12, decimal_places=2, help_text="Must equal the rental plus the deposit."
    )
    idempotency_key = serializers.RegexField(r"^[A-Za-z0-9_-]{8,40}$")
    password = serializers.CharField(write_only=True, trim_whitespace=False)


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
            "cash_on_collection",
            "confirmed_at",
            "pickup_code",
            "add_ons",
            "total_amount",
            "security_deposit",
            "discount_code",
            "discount_amount",
            "terms_accepted_at",
            "safety_notice_acknowledged_at",
            "delivery_address",  # Book.Deliver.Location; blank when collected at the branch
            "delivery_pincode",
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


class RatingSerializer(serializers.ModelSerializer):
    """Exp 2 UC 6: the review, and until when it may still be edited (extension 2a)."""

    editable_until = serializers.SerializerMethodField()

    class Meta:
        model = Rating
        fields = ["vehicle_rating", "service_rating", "comment", "created_at", "editable_until"]
        read_only_fields = fields

    @extend_schema_field(serializers.DateTimeField())
    def get_editable_until(self, rating: Rating) -> str:
        return serializers.DateTimeField().to_representation(rating_editable_until(rating))


class RateBookingSerializer(serializers.Serializer):
    """Exp 2 UC 6 step 2: vehicle and service rated separately, 1 to 5, optional comment."""

    vehicle_rating = serializers.IntegerField(min_value=1, max_value=5)
    service_rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(required=False, allow_blank=True, default="", max_length=1000)


class BookingDetailSerializer(BookingSerializer):
    """Adds the itemised price (Book.Quote.Display), the payment transaction (Pay.Confirm.OK)
    and the review (UC 6): `rating_open_until` invites a rating while it can be given."""

    price = serializers.SerializerMethodField()
    transaction_id = serializers.SerializerMethodField()
    refunds = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    rating_open_until = serializers.SerializerMethodField()

    class Meta(BookingSerializer.Meta):
        fields = [
            *BookingSerializer.Meta.fields,
            "price",
            "transaction_id",
            "refunds",
            "rating",
            "rating_open_until",
        ]
        read_only_fields = fields

    @extend_schema_field(RatingSerializer(allow_null=True))
    def get_rating(self, booking: Booking) -> dict | None:
        rating = Rating.objects.filter(booking=booking).first()
        return RatingSerializer(rating).data if rating else None

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_rating_open_until(self, booking: Booking) -> str | None:
        """UC 6 step 1: set only while an unrated Completed booking may still be rated."""
        until = rating_open_until(booking)
        if (
            until is None
            or until < timezone.now()
            or Rating.objects.filter(booking=booking).exists()
        ):
            return None
        return serializers.DateTimeField().to_representation(until)

    @extend_schema_field(QuoteSerializer)
    def get_price(self, booking: Booking) -> dict:
        return QuoteSerializer(booking_quote(booking)).data

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_transaction_id(self, booking: Booking) -> str | None:
        payment = booking.payments.filter(status="Succeeded", purpose="Security Deposit").first()
        return payment.transaction_id if payment else None

    @extend_schema_field(RefundSerializer(many=True))
    def get_refunds(self, booking: Booking) -> list:
        """Pay.Refund: every refund of the booking with its status (History.View)."""
        refunds = RefundRequest.objects.filter(original_payment__booking=booking).select_related(
            "original_payment__booking__customer__user", "requested_by", "decided_by", "refund"
        )
        return RefundSerializer(refunds, many=True).data


class CashDueBookingSerializer(BookingSerializer):
    """BR-9: a booking waiting for cash at collection, as its branch staff see it."""

    customer_name = serializers.CharField(source="customer.user.name", read_only=True)
    customer_mobile = serializers.CharField(source="customer.user.mobile_no", read_only=True)
    amount_due = serializers.SerializerMethodField()

    class Meta(BookingSerializer.Meta):
        fields = [*BookingSerializer.Meta.fields, "customer_name", "customer_mobile", "amount_due"]
        read_only_fields = fields

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=2))
    def get_amount_due(self, booking: Booking) -> str:
        return f"{booking.total_amount + booking.security_deposit:.2f}"


class BookingErrorSerializer(serializers.Serializer):
    """A refusal with a stable code, e.g. licence_not_verified, vehicle_unavailable."""

    detail = serializers.CharField()
    code = serializers.CharField()


# ─── Module R2: modify, cancel, extend (UC 4; Book.Modify, Book.Cancel, Book.Extend) ─


class CancellationQuoteSerializer(serializers.Serializer):
    """Book.Cancel: the refund computed per BR-8, shown before the customer confirms."""

    notice_hours = serializers.IntegerField()
    refund_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    rental_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    rental_refund = serializers.DecimalField(max_digits=12, decimal_places=2)
    deposit_refund = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_refund = serializers.DecimalField(max_digits=12, decimal_places=2)
    awaits_approval = serializers.BooleanField(
        help_text="UC 13: part of the refund is above the automatic approval limit."
    )


class CancelBookingSerializer(serializers.Serializer):
    expected_refund = serializers.DecimalField(
        max_digits=12, decimal_places=2, help_text="The total refund the customer was shown."
    )
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class ExtraPaymentSerializer(serializers.Serializer):
    """Pay.Method for an extra charge (card or on-line, D6); SE-9. A token is needed only
    when the change costs more; the server says so (`payment_required`)."""

    method = serializers.ChoiceField(choices=["card", "online"], default="card")
    payment_token = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    channel = serializers.ChoiceField(
        choices=OnlinePayment.Channel.choices, required=False, allow_blank=True, default=""
    )
    upi_id = serializers.RegexField(
        r"^[A-Za-z0-9._-]{2,64}@[A-Za-z0-9]{2,32}$", required=False, allow_blank=True, default=""
    )
    idempotency_key = serializers.RegexField(r"^[A-Za-z0-9_-]{8,40}$")
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        if attrs["method"] == "online" and attrs["payment_token"] and not attrs["channel"]:
            raise serializers.ValidationError({"channel": ["Choose UPI, net banking or a wallet."]})
        return attrs


class ModificationRequestSerializer(serializers.Serializer):
    """Book.Modify: the new period, pickup branch and add-ons; `vehicle` takes the
    alternative offered when the booked vehicle is not free (UC 4 extension 3a)."""

    pickup_datetime = serializers.DateTimeField()
    return_datetime = serializers.DateTimeField()
    pickup_branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    add_ons = AddOnRequestSerializer(many=True, required=False, default=list)
    vehicle = serializers.PrimaryKeyRelatedField(
        queryset=Vehicle.objects.select_related("category"),
        required=False,
        allow_null=True,
        default=None,
    )


class ModifyBookingSerializer(ModificationRequestSerializer, ExtraPaymentSerializer):
    expected_charge = serializers.DecimalField(max_digits=12, decimal_places=2)
    expected_refund = serializers.DecimalField(max_digits=12, decimal_places=2)


class ModificationQuoteSerializer(serializers.Serializer):
    price = QuoteSerializer()
    vehicle = BookingVehicleSerializer()
    vehicle_free = serializers.BooleanField()
    alternatives = BookingVehicleSerializer(many=True)
    previous_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    new_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    extra_charge = serializers.DecimalField(max_digits=12, decimal_places=2)
    refund_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    refund_amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class ExtensionRequestSerializer(serializers.Serializer):
    return_datetime = serializers.DateTimeField()


class ExtendBookingSerializer(ExtensionRequestSerializer, ExtraPaymentSerializer):
    expected_charge = serializers.DecimalField(max_digits=12, decimal_places=2)


class ExtensionQuoteSerializer(serializers.Serializer):
    price = QuoteSerializer()
    return_datetime = serializers.DateTimeField()
    previous_total = serializers.DecimalField(max_digits=12, decimal_places=2)
    extra_charge = serializers.DecimalField(max_digits=12, decimal_places=2)
