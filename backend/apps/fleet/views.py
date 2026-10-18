"""Fleet API views.

Every view must declare permission_classes explicitly (SE-4).

The catalogue lists and the availability search are public: SRS 3.2 lets any
visitor browse and any user search (Search.Browse). Booking needs a signed-in
customer and is enforced by the booking endpoints, not here. These views read
no user data, so they skip authentication, like the health check: an expired
token sent with a public request is never a reason to refuse it.
"""

from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Branch, Vehicle, VehicleCategory
from .serializers import (
    AvailabilitySearchSerializer,
    AvailableVehicleSerializer,
    BranchSerializer,
    SearchAlternativeSerializer,
    VehicleCategorySerializer,
    VehicleDetailSerializer,
)
from .services import catalogue

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
        vehicles, self.estimates = catalogue.search(
            branch=params["branch"],
            pickup=params["pickup_datetime"],
            return_=params["return_datetime"],
            filters=query.filters(),
        )
        return vehicles

    def get_serializer_context(self):
        # Search.Price: each category's estimate at the tariff in force on the pickup date.
        return {**super().get_serializer_context(), "estimates": getattr(self, "estimates", {})}

    @extend_schema(
        tags=[TAG],
        summary="Search available vehicles (Search.Available)",
        description=(
            "Vehicles at the pickup branch that can be booked for the whole period: status "
            "Available (Appendix B; so never Under Maintenance, Unsafe or Retired), no Pending "
            "Payment, Confirmed or Active booking within the period plus the 60-minute "
            "turnaround buffer (BR-1, Book.Hold), no Scheduled or In Progress maintenance "
            "window in the period, not overdue for its preventive service by date or distance "
            "(SA-2, BR-15), and an availability date on or before the pickup (Fleet.Add). The "
            "period must be 4 hours to 30 days (BR-5) and start in the future; otherwise the "
            "answer is 400 with the message on the field. Search.Filter narrows the results "
            "and `sort` orders them by price or rating. Each result carries `estimate` "
            "(Search.Price): the base charge plus tax at the tariff in force on the pickup "
            "date, excluding add-ons, discounts and usage-based charges; null if no tariff is "
            "in force. `min_price`/`max_price` apply to that estimate."
        ),
        parameters=[AvailabilitySearchSerializer],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class SearchAlternativesView(APIView):
    """Exp 2 UC 2 extension 3a: no vehicle matches, so offer the nearest alternatives."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        tags=[TAG],
        summary="Nearest alternatives when nothing matches (UC 2 extension 3a)",
        description=(
            "The same query as the search. Returns the other branches with matching vehicles "
            "for the same period (by name), then the same branch for the same length of "
            "rental moved by up to SEARCH_ALTERNATIVE_DAYS days either way, nearest first, at "
            "most SEARCH_ALTERNATIVE_DATES_SHOWN of them. Each entry gives how many vehicles "
            "match there."
        ),
        parameters=[AvailabilitySearchSerializer],
        responses={200: SearchAlternativeSerializer(many=True)},
    )
    def get(self, request):
        query = AvailabilitySearchSerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data
        found = catalogue.alternatives(
            branch=params["branch"],
            pickup=params["pickup_datetime"],
            return_=params["return_datetime"],
            filters=query.filters(),
        )
        return Response(SearchAlternativeSerializer(found, many=True).data)


class VehicleDetailView(RetrieveAPIView):
    """Search.Detail, public like the catalogue (Search.Browse). Retired is gone (Fleet.Retire)."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    serializer_class = VehicleDetailSerializer

    def get_queryset(self):
        return catalogue.with_catalogue_facts(
            Vehicle.objects.exclude(status=Vehicle.Status.RETIRED)
            .select_related("category", "home_branch", "car", "twowheeler")
            .prefetch_related("photos")
        )

    @extend_schema(
        tags=[TAG],
        summary="A vehicle in detail (Search.Detail)",
        description=(
            "Photographs (signed links), specification, the tariff in force, the BR-3 deposit, "
            "the rental terms (Book.Quote.Terms), the average rating and how many ratings it "
            "has, and the last service date from the maintenance history. `service_overdue` "
            "(SA-2) marks a vehicle that cannot be booked until it is serviced. `tariff` and "
            "`terms` are null while the category has no tariff in force."
        ),
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
