"""Fleet API serializers for the catalogue and availability search (SRS 3.2)."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.pricing.serializers import EstimateSerializer
from apps.pricing.services import estimate

from .models import Branch, Car, TwoWheeler, Vehicle, VehicleCategory
from .services.availability import RentalPeriodError, check_period


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["branch_id", "branch_name", "address"]


class VehicleCategorySerializer(serializers.ModelSerializer):
    # Plain text, as in the other vehicle serializers: the choice set is the
    # licence's CategoriesEnum already, and a second enum name for it fails
    # the schema export (--fail-on-warn).
    vehicle_type = serializers.CharField(read_only=True)

    class Meta:
        model = VehicleCategory
        fields = ["id", "name", "vehicle_type"]


class AvailabilitySearchSerializer(serializers.Serializer):
    """Search.Available: a pickup branch, a rental period and an optional category.

    Date-times are ISO 8601; send them in UTC (CO-6). The period must satisfy
    BR-5.
    """

    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    pickup_datetime = serializers.DateTimeField()
    return_datetime = serializers.DateTimeField()
    category = serializers.PrimaryKeyRelatedField(
        queryset=VehicleCategory.objects.all(), required=False, allow_null=True
    )

    def validate(self, attrs):
        try:
            check_period(attrs["pickup_datetime"], attrs["return_datetime"])
        except RentalPeriodError as exc:
            raise serializers.ValidationError({exc.field: [str(exc)]}) from exc
        return attrs


class AvailableVehicleSerializer(serializers.ModelSerializer):
    """One search result: the specification a customer chooses by (Search.Filter fields)."""

    vehicle_type = serializers.CharField(read_only=True)
    category = serializers.CharField(source="category.name", read_only=True)
    category_id = serializers.IntegerField(read_only=True)
    home_branch = serializers.CharField(source="home_branch.branch_name", read_only=True)
    home_branch_id = serializers.IntegerField(read_only=True)
    transmission = serializers.SerializerMethodField()
    seating_capacity = serializers.SerializerMethodField()
    engine_cc = serializers.SerializerMethodField()
    # D13: computed from ratings of completed bookings, never stored.
    average_rating = serializers.DecimalField(
        max_digits=4, decimal_places=2, read_only=True, allow_null=True
    )
    # Search.Price: null when the category has no tariff in force.
    estimate = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "brand",
            "model",
            "year",
            "colour",
            "fuel_type",
            "vehicle_type",
            "category",
            "category_id",
            "home_branch",
            "home_branch_id",
            "transmission",
            "seating_capacity",
            "engine_cc",
            "average_rating",
            "last_service_date",  # Search.Detail "date on which the vehicle was last serviced"
            "estimate",
        ]

    @extend_schema_field(EstimateSerializer(allow_null=True))
    def get_estimate(self, vehicle: Vehicle) -> dict | None:
        """Search.Price: base + tax for the searched period (PR9), from the context."""
        tariff = self.context["tariffs"].get(vehicle.category_id)
        if tariff is None:
            return None
        result = estimate(
            tariff, vehicle.vehicle_type, self.context["pickup"], self.context["return_"]
        )
        return EstimateSerializer(result).data

    @staticmethod
    def _car(vehicle: Vehicle) -> Car | None:
        try:
            return vehicle.car
        except Car.DoesNotExist:
            return None

    @staticmethod
    def _two_wheeler(vehicle: Vehicle) -> TwoWheeler | None:
        try:
            return vehicle.twowheeler
        except TwoWheeler.DoesNotExist:
            return None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_transmission(self, vehicle: Vehicle) -> str | None:
        car = self._car(vehicle)
        return car.transmission if car else None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_seating_capacity(self, vehicle: Vehicle) -> int | None:
        car = self._car(vehicle)
        return car.seating_capacity if car else None

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_engine_cc(self, vehicle: Vehicle) -> int | None:
        two_wheeler = self._two_wheeler(vehicle)
        return two_wheeler.engine_cc if two_wheeler else None
