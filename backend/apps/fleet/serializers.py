"""Fleet API serializers for the catalogue and availability search (SRS 3.2)."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.files import signed_file_url
from apps.pricing.serializers import EstimateSerializer, QuoteTermsSerializer
from apps.pricing.services import (
    PricingError,
    current_tariff,
    estimate,
    quote_terms,
    security_deposit_for,
)

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


class TariffSummarySerializer(serializers.Serializer):
    """Search.Detail "the applicable tariff" (PR3: the weekly rate is not applied, so not shown)."""

    hourly_rate = serializers.DecimalField(max_digits=12, decimal_places=2)
    daily_rate = serializers.DecimalField(max_digits=12, decimal_places=2)
    free_km_allowance_per_day = serializers.IntegerField(source="free_km_allowance")
    excess_km_rate = serializers.DecimalField(max_digits=12, decimal_places=2)


class VehicleDetailSerializer(AvailableVehicleSerializer):
    """Search.Detail: photos, specification, tariff, deposit, policies, rating, last service."""

    status = serializers.CharField(read_only=True)
    photos = serializers.SerializerMethodField()
    tariff = serializers.SerializerMethodField()
    security_deposit = serializers.SerializerMethodField()
    terms = serializers.SerializerMethodField()

    class Meta(AvailableVehicleSerializer.Meta):
        fields = [
            *(name for name in AvailableVehicleSerializer.Meta.fields if name != "estimate"),
            "status",
            "photos",
            "tariff",
            "security_deposit",
            "terms",
        ]

    def _tariff(self, vehicle: Vehicle):
        cache = self.context.setdefault("_tariffs", {})
        if vehicle.category_id not in cache:
            try:
                cache[vehicle.category_id] = current_tariff(vehicle.category)
            except PricingError:
                cache[vehicle.category_id] = None
        return cache[vehicle.category_id]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_photos(self, vehicle: Vehicle) -> list[str]:
        """Signed links (SI-3: only the object key is stored)."""
        request = self.context.get("request")
        return [signed_file_url(photo.image, request) for photo in vehicle.photos.all()]

    @extend_schema_field(TariffSummarySerializer(allow_null=True))
    def get_tariff(self, vehicle: Vehicle) -> dict | None:
        tariff = self._tariff(vehicle)
        return TariffSummarySerializer(tariff).data if tariff else None

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=2))
    def get_security_deposit(self, vehicle: Vehicle) -> str:
        """BR-3 (PR4)."""
        return serializers.DecimalField(max_digits=12, decimal_places=2).to_representation(
            security_deposit_for(vehicle.vehicle_type)
        )

    @extend_schema_field(QuoteTermsSerializer(allow_null=True))
    def get_terms(self, vehicle: Vehicle) -> dict | None:
        """Search.Detail "the fuel and cancellation policies"; Book.Quote.Terms."""
        tariff = self._tariff(vehicle)
        return QuoteTermsSerializer(quote_terms(tariff)).data if tariff else None
