"""Pricing API serializers. Money is Decimal, sent as strings (CO-6)."""

from rest_framework import serializers

from apps.fleet.models import Vehicle
from apps.fleet.services.availability import RentalPeriodError, check_period

from .models import AddOn


def _money(**kwargs) -> serializers.DecimalField:
    return serializers.DecimalField(max_digits=12, decimal_places=2, **kwargs)


class AddOnSerializer(serializers.ModelSerializer):
    # Plain text: the choice set already has a schema name (CategoriesEnum).
    vehicle_type = serializers.CharField(
        read_only=True, help_text="Car or Two-Wheeler; blank when offered with any vehicle."
    )

    class Meta:
        model = AddOn
        fields = ["id", "name", "daily_rate", "vehicle_type"]


class AddOnRequestSerializer(serializers.Serializer):
    add_on = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)


class QuoteRequestSerializer(serializers.Serializer):
    """Book.Quote.Display: a vehicle, a period (BR-5), add-ons (Book.Addons) and a code (D17)."""

    vehicle = serializers.PrimaryKeyRelatedField(
        queryset=Vehicle.objects.select_related("category")
    )
    pickup_datetime = serializers.DateTimeField()
    return_datetime = serializers.DateTimeField()
    add_ons = AddOnRequestSerializer(many=True, required=False, default=list)
    discount_code = serializers.CharField(
        max_length=32, required=False, allow_blank=True, default=""
    )

    def validate(self, attrs):
        try:
            check_period(attrs["pickup_datetime"], attrs["return_datetime"])
        except RentalPeriodError as exc:
            raise serializers.ValidationError({exc.field: [str(exc)]}) from exc
        return attrs


class AddOnChargeSerializer(serializers.Serializer):
    add_on_id = serializers.IntegerField()
    name = serializers.CharField()
    quantity = serializers.IntegerField()
    daily_rate = _money()
    days = serializers.IntegerField()
    amount = _money()


class CancellationRefundSerializer(serializers.Serializer):
    notice_hours_at_least = serializers.IntegerField()
    refund_percent = serializers.DecimalField(max_digits=5, decimal_places=2)


class QuoteTermsSerializer(serializers.Serializer):
    """Book.Quote.Terms."""

    free_km_allowance_per_day = serializers.IntegerField()
    excess_km_rate = _money()
    late_return_grace_minutes = serializers.IntegerField()
    late_return_hourly_rate = _money()
    late_return_daily_cap = _money()
    late_return_full_day_after_hours = serializers.IntegerField()
    fuel_shortfall_service_charge_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    cancellation_refunds = CancellationRefundSerializer(many=True)
    no_show_retained_percent = serializers.DecimalField(max_digits=5, decimal_places=2)


class QuoteSerializer(serializers.Serializer):
    """Book.Quote.Display: every charge itemised (UI-4); the deposit apart (Pay.Deposit)."""

    tariff_id = serializers.IntegerField()
    billing_unit = serializers.ChoiceField(choices=["day", "hour"])
    billing_count = serializers.IntegerField()
    unit_rate = _money()
    base_charge = _money()
    add_ons = AddOnChargeSerializer(many=True)
    add_ons_total = _money()
    rental_charge = _money()
    discount_code = serializers.CharField(allow_blank=True)
    discount_amount = _money()
    taxable_amount = _money()
    tax_rate_percent = serializers.DecimalField(max_digits=5, decimal_places=2)
    tax_amount = _money()
    total_payable = _money()
    security_deposit = _money()
    free_helmets_per_rider = serializers.IntegerField()
    terms = QuoteTermsSerializer()


class EstimateSerializer(serializers.Serializer):
    """Search.Price: base charge plus tax for the period, an estimate (PR9)."""

    billing_unit = serializers.ChoiceField(choices=["day", "hour"])
    billing_count = serializers.IntegerField()
    total_payable = _money()
    security_deposit = _money()
