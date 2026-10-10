"""Fleet API views.

Every view must declare permission_classes explicitly (SE-4).

The catalogue lists and the availability search are public: SRS 3.2 lets any
visitor browse and any user search (Search.Browse). Booking needs a signed-in
customer and is enforced by the booking endpoints, not here. These views read
no user data, so they skip authentication, like the health check: an expired
token sent with a public request is never a reason to refuse it.
"""

from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from apps.bookings.services import with_average_rating

from .models import Branch, Vehicle, VehicleCategory
from .serializers import (
    AvailabilitySearchSerializer,
    AvailableVehicleSerializer,
    BranchSerializer,
    VehicleCategorySerializer,
)
from .services.availability import available_vehicles

TAG = "Search and availability"


class BranchListView(ListAPIView):
    """The pickup branches a search can start from."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = BranchSerializer
    pagination_class = None
    filter_backends: list = []
    queryset = Branch.objects.all()

    @extend_schema(tags=[TAG], summary="Branches (pickup locations)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class VehicleCategoryListView(ListAPIView):
    """Appendix A vehicle categories, for the search filter (Search.Filter)."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = VehicleCategorySerializer
    pagination_class = None
    filter_backends: list = []
    queryset = VehicleCategory.objects.all()

    @extend_schema(tags=[TAG], summary="Vehicle categories")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class VehicleSearchView(ListAPIView):
    """Search.Available: vehicles bookable for the whole requested period."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = AvailableVehicleSerializer
    filter_backends: list = []  # the query is validated by AvailabilitySearchSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # schema generation
            return Vehicle.objects.none()
        query = AvailabilitySearchSerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        vehicles = available_vehicles(
            branch=params["branch"],
            pickup=params["pickup_datetime"],
            return_=params["return_datetime"],
            category=params.get("category"),
        )
        return with_average_rating(
            vehicles.select_related("category", "home_branch", "car", "twowheeler")
        ).order_by("brand", "model", "pk")

    @extend_schema(
        tags=[TAG],
        summary="Search available vehicles (Search.Available)",
        description=(
            "Vehicles at the pickup branch that can be booked for the whole period: status "
            "Available (Appendix B), no Pending Payment, Confirmed or Active booking within the "
            "period plus the 60-minute turnaround buffer (BR-1, Book.Hold), no Scheduled or In "
            "Progress maintenance window in the period, and an availability date on or before "
            "the pickup (Fleet.Add). The period must be 4 hours to 30 days (BR-5) and start in "
            "the future; otherwise the answer is 400 with the message on the field."
        ),
        parameters=[AvailabilitySearchSerializer],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
