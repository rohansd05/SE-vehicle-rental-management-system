"""Fleet API serializers for the catalogue and availability search (SRS 3.2)."""

from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.core.choices import FuelType, VehicleType
from apps.core.files import signed_file_url
from apps.pricing.serializers import EstimateSerializer, QuoteTermsSerializer
from apps.pricing.services import (
    PricingError,
    current_tariff,
    quote_terms,
    security_deposit_for,
)

from .models import Branch, Car, TwoWheeler, Vehicle, VehicleCategory
from .services.availability import RentalPeriodError, check_period, service_overdue
from .services.catalogue import SORTS, SearchFilters


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


def _money(**kwargs) -> serializers.DecimalField:
    return serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False, **kwargs
    )


class AvailabilitySearchSerializer(serializers.Serializer):
    """Search.Available: a pickup branch, a rental period and the Search.Filter criteria.

    Date-times are ISO 8601; send them in UTC (CO-6). The period must satisfy
    BR-5. Prices are the estimate for the period (Search.Price) at the tariff in
    force on the pickup date.
    """

    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    pickup_datetime = serializers.DateTimeField()
    return_datetime = serializers.DateTimeField()
    category = serializers.PrimaryKeyRelatedField(
        queryset=VehicleCategory.objects.all(), required=False, allow_null=True
    )
    vehicle_type = serializers.ChoiceField(choices=VehicleType.choices, required=False)
    brand = serializers.CharField(required=False, max_length=64)
    model = serializers.CharField(required=False, max_length=64)
    fuel_type = serializers.ChoiceField(choices=FuelType.choices, required=False)
    transmission = serializers.ChoiceField(choices=Car.Transmission.choices, required=False)
    min_seats = serializers.IntegerField(required=False, min_value=1, max_value=20)
    min_price = _money()
    max_price = _money()
    min_rating = serializers.DecimalField(
        max_digits=3, decimal_places=1, min_value=1, max_value=5, required=False
    )
    sort = serializers.ChoiceField(
        choices=SORTS, required=False, help_text="price (lowest first), -price, or rating."
    )

    def validate(self, attrs):
        try:
            check_period(attrs["pickup_datetime"], attrs["return_datetime"])
        except RentalPeriodError as exc:
            raise serializers.ValidationError({exc.field: [str(exc)]}) from exc
        low, high = attrs.get("min_price"), attrs.get("max_price")
        if low is not None and high is not None and low > high:
            raise serializers.ValidationError(
                {"max_price": ["The highest price must not be below the lowest."]}
            )
        return attrs

    def filters(self) -> SearchFilters:
        data = self.validated_data
        return SearchFilters(
            vehicle_type=data.get("vehicle_type", ""),
            category=data.get("category"),
            brand=data.get("brand", ""),
            model=data.get("model", ""),
            fuel_type=data.get("fuel_type", ""),
            transmission=data.get("transmission", ""),
            min_seats=data.get("min_seats"),
            min_price=data.get("min_price"),
            max_price=data.get("max_price"),
            min_rating=data.get("min_rating"),
            sort=data.get("sort", ""),
        )


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
    # D13, UC 6: computed from ratings of completed bookings, never stored.
    average_rating = serializers.DecimalField(
        max_digits=4, decimal_places=2, read_only=True, allow_null=True
    )
    rating_count = serializers.IntegerField(read_only=True)
    # Search.Detail "date on which the vehicle was last serviced": the latest closed job.
    last_service_date = serializers.DateField(
        source="last_serviced", read_only=True, allow_null=True
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
            "rating_count",
            "last_service_date",
            "estimate",
        ]

    @extend_schema_field(EstimateSerializer(allow_null=True))
    def get_estimate(self, vehicle: Vehicle) -> dict | None:
        """Search.Price: base + tax for the searched period (PR9), from the context."""
        result = self.context["estimates"].get(vehicle.category_id)
        return EstimateSerializer(result).data if result else None

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


class SearchAlternativeSerializer(serializers.Serializer):
    """Exp 2 UC 2 extension 3a: a branch or a nearby period with matching vehicles."""

    branch = serializers.IntegerField(source="branch.branch_id")
    branch_name = serializers.CharField(source="branch.branch_name")
    pickup_datetime = serializers.DateTimeField()
    return_datetime = serializers.DateTimeField()
    vehicles = serializers.IntegerField()


class TariffSummarySerializer(serializers.Serializer):
    """Search.Detail "the applicable tariff" (PR3: the weekly rate is not applied, so not shown)."""

    hourly_rate = serializers.DecimalField(max_digits=12, decimal_places=2)
    daily_rate = serializers.DecimalField(max_digits=12, decimal_places=2)
    free_km_allowance_per_day = serializers.IntegerField(source="free_km_allowance")
    excess_km_rate = serializers.DecimalField(max_digits=12, decimal_places=2)


class VehicleDetailSerializer(AvailableVehicleSerializer):
    """Search.Detail: photos, specification, tariff, deposit, policies, rating, last service."""

    status = serializers.CharField(read_only=True)
    # SA-2: shown as "Not bookable: service overdue"; never searched or booked.
    service_overdue = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()
    tariff = serializers.SerializerMethodField()
    security_deposit = serializers.SerializerMethodField()
    terms = serializers.SerializerMethodField()

    class Meta(AvailableVehicleSerializer.Meta):
        fields = [
            *(name for name in AvailableVehicleSerializer.Meta.fields if name != "estimate"),
            "status",
            "service_overdue",
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

    @extend_schema_field(serializers.BooleanField())
    def get_service_overdue(self, vehicle: Vehicle) -> bool:
        return service_overdue(vehicle)

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
