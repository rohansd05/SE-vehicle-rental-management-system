"""Tariff, add-on and discount code administration serializers (Module N3).

Money is Decimal, sent as strings (CO-6). Kept apart from the quote
serializers (serializers.py, Rohan's).
"""

from decimal import Decimal

from rest_framework import serializers

from apps.core.choices import VehicleType
from apps.fleet.models import VehicleCategory

from .admin_services import tariff_state
from .models import AddOn, DiscountCode, Tariff

MONEY = {"max_digits": 12, "decimal_places": 2, "min_value": Decimal("0")}


class AdminTariffSerializer(serializers.ModelSerializer):
    """Fleet.Tariff.History: one tariff with whether it is in force."""

    category_name = serializers.CharField(source="vehicle_category.name", read_only=True)
    vehicle_type = serializers.CharField(source="vehicle_category.vehicle_type", read_only=True)
    defined_by = serializers.CharField(source="defined_by.user.name", read_only=True)
    state = serializers.SerializerMethodField()
    booking_count = serializers.SerializerMethodField(
        help_text="Bookings priced at this tariff; a later tariff never reprices them (BR-13)."
    )

    class Meta:
        model = Tariff
        fields = [
            "id",
            "vehicle_category",
            "category_name",
            "vehicle_type",
            "hourly_rate",
            "daily_rate",
            "weekly_rate",
            "security_deposit",
            "free_km_allowance",
            "excess_km_rate",
            "effective_from",
            "defined_by",
            "state",
            "booking_count",
        ]
        read_only_fields = fields

    def get_state(self, tariff) -> str:
        return tariff_state(tariff, self.context.get("in_force", {}))

    def get_booking_count(self, tariff) -> int:
        return tariff.bookings.count()


class TariffInputSerializer(serializers.Serializer):
    """Fleet.Tariff: the rates for a category from an effective date (now if empty).
    The security deposit is BR-3's for the category's type, not an input."""

    vehicle_category = serializers.PrimaryKeyRelatedField(queryset=VehicleCategory.objects.all())
    hourly_rate = serializers.DecimalField(**MONEY)
    daily_rate = serializers.DecimalField(**MONEY)
    weekly_rate = serializers.DecimalField(**MONEY)
    free_km_allowance = serializers.IntegerField(
        min_value=0, help_text="Kilometres per rental day."
    )
    excess_km_rate = serializers.DecimalField(**MONEY)
    effective_from = serializers.DateTimeField(required=False, allow_null=True, default=None)


class AdminAddOnSerializer(serializers.ModelSerializer):
    daily_rate = serializers.DecimalField(**MONEY)
    # Plain text, as in the fleet serializers: the choice set is the licence's
    # CategoriesEnum already, and a second enum name fails --fail-on-warn.
    vehicle_type = serializers.CharField(
        required=False, allow_blank=True, help_text="Car, Two-Wheeler, or empty for any."
    )

    class Meta:
        model = AddOn
        fields = ["id", "name", "daily_rate", "vehicle_type", "is_active"]
        read_only_fields = ["id"]

    def validate_vehicle_type(self, value: str) -> str:
        if value and value not in VehicleType.values:
            raise serializers.ValidationError("Choose Car, Two-Wheeler or any vehicle.")
        return value


class AdminDiscountCodeSerializer(serializers.ModelSerializer):
    value = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))

    class Meta:
        model = DiscountCode
        fields = [
            "id",
            "code",
            "discount_type",
            "value",
            "valid_from",
            "valid_to",
            "is_active",
            "usage_limit",
            "times_used",
        ]
        read_only_fields = ["id", "times_used"]
        # Uniqueness is checked case-insensitively by the service.
        extra_kwargs = {"code": {"validators": []}}
