"""The catalogue search (SRS 3.2 Search.Filter, Search.Price, Search.Detail; Exp 2 UC 2).

search() narrows Search.Available (availability.available_vehicles(): status,
BR-1 buffer, maintenance windows, SA-2) by the Search.Filter criteria: vehicle
type, category, brand and model, fuel, transmission, seats, price range and
minimum rating, sorted by price or rating.

Price (Search.Price, BR-6): the estimate at the tariff in force on the pickup
date (BR-13 tariffs have effective dates), from calculate_price() unchanged;
one estimate per category, because it depends only on the tariff and the
period. Rating (D13, UC 6): the average and count of the vehicle's ratings,
computed on every query and never stored. Last serviced (Search.Detail): the
latest closed maintenance job, else the service on record when the vehicle
was added.

alternatives() is UC 2 extension 3a: when nothing matches, the other branches
with a match for the same period, then the same branch on the nearest dates.

Owner: Rohan (Module R4).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Case, DecimalField, F, OuterRef, QuerySet, Subquery, Value, When
from django.db.models.functions import Coalesce

from apps.bookings.services import with_average_rating
from apps.fleet.models import Branch, Vehicle, VehicleCategory
from apps.maintenance.models import MaintenanceJob
from apps.pricing.services import Quote, estimate, tariffs_in_force

from .availability import RentalPeriodError, available_vehicles, check_period

SORTS = ("price", "-price", "rating")


@dataclass(frozen=True)
class SearchFilters:
    """Search.Filter. Empty values do not filter."""

    vehicle_type: str = ""
    category: VehicleCategory | None = None
    brand: str = ""
    model: str = ""
    fuel_type: str = ""
    transmission: str = ""  # cars only
    min_seats: int | None = None  # cars only
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    min_rating: Decimal | None = None
    sort: str = ""  # one of SORTS; otherwise brand and model


@dataclass(frozen=True)
class Alternative:
    """UC 2 extension 3a: a branch or a period with `vehicles` matching vehicles."""

    branch: Branch
    pickup_datetime: datetime
    return_datetime: datetime
    vehicles: int


def estimates_for(pickup: datetime, return_: datetime) -> dict[int, Quote]:
    """Search.Price for each category: base + tax at the tariff in force on the pickup date."""
    return {
        category_id: estimate(tariff, tariff.vehicle_category.vehicle_type, pickup, return_)
        for category_id, tariff in tariffs_in_force(pickup).items()
    }


def with_catalogue_facts(vehicles: QuerySet[Vehicle]) -> QuerySet[Vehicle]:
    """Annotate `average_rating`, `rating_count` (D13) and `last_serviced` (Search.Detail)."""
    closed = (
        MaintenanceJob.objects.filter(
            vehicle=OuterRef("pk"),
            status=MaintenanceJob.Status.COMPLETED,
            service_date__isnull=False,
        )
        .order_by("-service_date")
        .values("service_date")[:1]
    )
    return with_average_rating(vehicles).annotate(
        last_serviced=Coalesce(Subquery(closed), F("last_service_date"))
    )


def _filtered(
    vehicles: QuerySet[Vehicle], filters: SearchFilters, estimates: dict[int, Quote]
) -> QuerySet[Vehicle]:
    if filters.vehicle_type:
        vehicles = vehicles.filter(category__vehicle_type=filters.vehicle_type)
    if filters.brand:
        vehicles = vehicles.filter(brand__icontains=filters.brand)
    if filters.model:
        vehicles = vehicles.filter(model__icontains=filters.model)
    if filters.fuel_type:
        vehicles = vehicles.filter(fuel_type=filters.fuel_type)
    if filters.transmission:
        vehicles = vehicles.filter(car__transmission=filters.transmission)
    if filters.min_seats:
        vehicles = vehicles.filter(car__seating_capacity__gte=filters.min_seats)
    if filters.min_price is not None or filters.max_price is not None:
        low, high = filters.min_price, filters.max_price
        vehicles = vehicles.filter(
            category_id__in=[
                category_id
                for category_id, quote in estimates.items()
                if (low is None or quote.total_payable >= low)
                and (high is None or quote.total_payable <= high)
            ]
        )
    vehicles = with_catalogue_facts(vehicles)
    if filters.min_rating is not None:
        vehicles = vehicles.filter(average_rating__gte=filters.min_rating)
    return vehicles


def _ordered(
    vehicles: QuerySet[Vehicle], sort: str, estimates: dict[int, Quote]
) -> QuerySet[Vehicle]:
    """Search.Filter "sort them by price or rating"; unpriced or unrated vehicles come last."""
    tie = ("brand", "model", "pk")
    if sort in ("price", "-price"):
        price = Case(
            *(When(category_id=cid, then=Value(q.total_payable)) for cid, q in estimates.items()),
            default=None,
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        vehicles = vehicles.annotate(estimated_price=price)
        key = F("estimated_price")
        first = key.asc(nulls_last=True) if sort == "price" else key.desc(nulls_last=True)
        return vehicles.order_by(first, *tie)
    if sort == "rating":
        return vehicles.order_by(
            F("average_rating").desc(nulls_last=True), F("rating_count").desc(), *tie
        )
    return vehicles.order_by(*tie)


def search(
    *, branch: Branch, pickup: datetime, return_: datetime, filters: SearchFilters
) -> tuple[QuerySet[Vehicle], dict[int, Quote]]:
    """Search.Available narrowed by Search.Filter, with each category's estimate (Search.Price).

    Raises RentalPeriodError for a period BR-5 does not allow.
    """
    estimates = estimates_for(pickup, return_)
    vehicles = available_vehicles(
        branch=branch, pickup=pickup, return_=return_, category=filters.category
    ).select_related("category", "home_branch", "car", "twowheeler")
    return _ordered(_filtered(vehicles, filters, estimates), filters.sort, estimates), estimates


def _matches(branch: Branch, pickup: datetime, return_: datetime, filters: SearchFilters) -> int:
    vehicles = available_vehicles(
        branch=branch, pickup=pickup, return_=return_, category=filters.category
    )
    return _filtered(vehicles, filters, estimates_for(pickup, return_)).count()


def _nearby_periods(pickup: datetime, return_: datetime):
    """The same period moved by 1, -1, 2, -2, ... days, as far as BR-5 and the clock allow."""
    for days in range(1, settings.SEARCH_ALTERNATIVE_DAYS + 1):
        for shift in (timedelta(days=days), timedelta(days=-days)):
            try:
                check_period(pickup + shift, return_ + shift)
            except RentalPeriodError:
                continue  # a pickup moved into the past
            yield pickup + shift, return_ + shift


def alternatives(
    *, branch: Branch, pickup: datetime, return_: datetime, filters: SearchFilters
) -> list[Alternative]:
    """UC 2 extension 3a: "offers the nearest alternatives by branch or by date"."""
    check_period(pickup, return_)
    found = []
    for other in Branch.objects.exclude(pk=branch.pk).order_by("branch_name"):
        count = _matches(other, pickup, return_, filters)
        if count:
            found.append(Alternative(other, pickup, return_, count))
    dates = 0
    for moved_pickup, moved_return in _nearby_periods(pickup, return_):
        if dates == settings.SEARCH_ALTERNATIVE_DATES_SHOWN:
            break
        count = _matches(branch, moved_pickup, moved_return, filters)
        if count:
            found.append(Alternative(branch, moved_pickup, moved_return, count))
            dates += 1
    return found
