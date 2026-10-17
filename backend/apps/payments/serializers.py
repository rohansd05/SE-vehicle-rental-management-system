"""Payments API serializers. Money is Decimal, sent as strings (CO-6); no card data (CO-2)."""

from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import OnlinePayment, RefundRequest

IDEMPOTENCY_KEY = r"^[A-Za-z0-9_-]{8,40}$"
MONEY = {"max_digits": 12, "decimal_places": 2, "min_value": Decimal("0.01")}


def idempotency_key_field():
    return serializers.RegexField(
        IDEMPOTENCY_KEY,
        help_text="Pay.Idempotent: one key per attempt; a repeat never charges or refunds twice.",
    )


def password_field():
    return serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        help_text="SE-9: re-authentication before a payment or a refund.",
    )


class ReauthenticatedSerializer(serializers.Serializer):
    password = password_field()


class PaymentMethodSerializer(serializers.Serializer):
    """Pay.Method: a card token, or an on-line channel (D6) with its token from the hosted page."""

    method = serializers.ChoiceField(choices=["card", "online"], default="card")
    payment_token = serializers.CharField(
        max_length=255,
        help_text="From the gateway's hosted fields or page. Sandbox: tok_decline declines.",
    )
    channel = serializers.ChoiceField(
        choices=OnlinePayment.Channel.choices, required=False, allow_blank=True, default=""
    )
    upi_id = serializers.RegexField(
        r"^[A-Za-z0-9._-]{2,64}@[A-Za-z0-9]{2,32}$", required=False, allow_blank=True, default=""
    )

    def validate(self, attrs):
        if attrs["method"] == "online" and not attrs["channel"]:
            raise serializers.ValidationError({"channel": ["Choose UPI, net banking or a wallet."]})
        if attrs["method"] == "card":
            attrs["channel"] = ""
        return attrs


class PayDueSerializer(PaymentMethodSerializer):
    idempotency_key = idempotency_key_field()
    password = password_field()


class DueSerializer(serializers.Serializer):
    """Pay.Dues, BR-4: what the customer owes; above zero, no new booking is accepted."""

    outstanding_due = serializers.DecimalField(max_digits=12, decimal_places=2)
    transaction_id = serializers.CharField(required=False)


class ChargeLineSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=255)
    amount = serializers.DecimalField(**MONEY)


class CaptureSerializer(serializers.Serializer):
    lines = ChargeLineSerializer(many=True, required=False, default=list, max_length=20)
    idempotency_key = idempotency_key_field()
    password = password_field()


class LedgerEntryResultSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    entry_type = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    method = serializers.CharField()
    gateway_reference = serializers.CharField()
    note = serializers.CharField()


class RefundCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(**MONEY)
    reason = serializers.CharField(max_length=255)
    idempotency_key = idempotency_key_field()
    password = password_field()


class RejectRefundSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)
    password = password_field()


class PayOutCashRefundSerializer(serializers.Serializer):
    customer_acknowledged = serializers.BooleanField(
        help_text="Pay.Refund: the customer has acknowledged the cash. Must be true."
    )
    password = password_field()

    def validate_customer_acknowledged(self, value):
        if not value:
            raise serializers.ValidationError("The customer must acknowledge the cash refund.")
        return value


class RefundSerializer(serializers.ModelSerializer):
    """A refund request as the Administrator queue (UC 13), staff and the customer see it."""

    booking_id = serializers.IntegerField(source="original_payment.booking_id", read_only=True)
    booking_reference = serializers.CharField(
        source="original_payment.booking.booking_reference", read_only=True
    )
    customer_name = serializers.CharField(
        source="original_payment.booking.customer.user.name", read_only=True
    )
    purpose = serializers.CharField(source="original_payment.purpose", read_only=True)
    method = serializers.CharField(source="original_payment.method", read_only=True)
    original_transaction_id = serializers.CharField(
        source="original_payment.transaction_id", read_only=True
    )
    requested_by_name = serializers.CharField(
        source="requested_by.name", default="", read_only=True
    )
    decided_by_name = serializers.CharField(source="decided_by.name", default="", read_only=True)
    refund_transaction_id = serializers.SerializerMethodField()

    class Meta:
        model = RefundRequest
        fields = [
            "id",
            "booking_id",
            "booking_reference",
            "customer_name",
            "purpose",
            "method",
            "original_transaction_id",
            "amount",
            "reason",
            "status",
            "requested_by_name",
            "requested_at",
            "decided_by_name",
            "decided_at",
            "rejection_reason",
            "failure_reason",
            "refund_due_by",
            "refund_transaction_id",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_refund_transaction_id(self, refund: RefundRequest) -> str | None:
        return refund.refund.transaction_id if refund.refund_id else None


class NotificationResultSerializer(serializers.Serializer):
    event_id = serializers.CharField()
    duplicate = serializers.BooleanField()
