"""Pricing business logic: Exp 3 Tariff.calculate_price() (BR-3, BR-5, BR-6, BR-7, D14, D17).

calculate_price() is pure: it reads only the objects passed in and the
business-rule settings, never the database or the clock, so every BR-6 case
can be tested directly. The functions below it look up what it needs (the
tariff in force, the add-ons, a discount code) and check them.

Book.Quote.Display: base rental charge, each add-on charge, the taxes, any
discount and the total payable, with the refundable deposit apart. Usage-based
charges (BR-10 to BR-12) arise only at return, so a quote never includes them
(Search.Price: "an estimate that excludes usage-based charges").

Team decisions, 11 Oct 2026 (the SRS is silent or ambiguous):
- PR1: the discount comes off first; tax is charged on (base + add-ons - discount).
- PR2: 24 hours or more is billed in whole days, a part-day counting as a whole
  day (24 h = 1 day, 24 h 10 min = 2 days). Under 24 hours: whole hours, a
  part-hour billed only when it exceeds the 15-minute grace (BR-6).
- PR3: the tariff's weekly rate is not applied; BR-6 bills only days and hours.
- PR4: the deposit is BR-3's amount for the vehicle type, not the tariff's
  security_deposit field.
Proposed, awaiting team approval:
- PR5: amounts are rounded half-up to the paisa (tax, percentage discount).
- PR6: a fixed discount is capped at the rental charge, so nothing goes negative.
- PR7: the hourly charge is not capped at the daily rate (BR-10's cap is for
  late returns only).
- PR8: add-ons are charged per billed day; a rental under 24 hours is one day.
- PR9: the search estimate is base + tax, without add-ons or discount.
- PR10: a quote checks a discount code's window, active flag and usage limit
  but does not use it up; confirmation does (Stage 3).

Owner: Rohan (CLAUDE.md ownership).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone

from apps.core.choices import VehicleType

from .models import AddOn, DiscountCode, Tariff

if TYPE_CHECKING:
    from apps.fleet.models import Vehicle, VehicleCategory

CENT = Decimal("0.01")
HOUR = timedelta(hours=1)


class PricingError(ValueError):
    """The quote cannot be made; `field` names the request field the message belongs to."""

    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(message)


def _money(value: Decimal) -> Decimal:
    """PR5: round half-up to the paisa."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


# ─── Billing period (BR-6, PR2) ───────────────────────────────────────────


@dataclass(frozen=True)
class BillingPeriod:
    unit: str  # "day" or "hour"
    count: int

    @property
    def add_on_days(self) -> int:
        """PR8: add-ons are charged per billed day; under 24 hours is one day."""
        return self.count if self.unit == "day" else 1


def billing_period(pickup: datetime, return_: datetime) -> BillingPeriod:
    """BR-6 with PR2: whole days from 24 hours, otherwise whole hours after a 15-minute grace."""
    length = return_ - pickup
    if length >= settings.DAILY_BILLING_THRESHOLD:
        full, part = divmod(length, settings.DAILY_BILLING_THRESHOLD)
        return BillingPeriod("day", full + (1 if part else 0))
    full, part = divmod(length, HOUR)
    return BillingPeriod("hour", full + (1 if part > settings.PART_HOUR_GRACE else 0))


def security_deposit_for(vehicle_type: str) -> Decimal:
    """BR-3 with PR4: Rs 2,000 for a two-wheeler, Rs 5,000 for a car."""
    if vehicle_type == VehicleType.TWO_WHEELER:
        return settings.SECURITY_DEPOSIT_TWO_WHEELER
    return settings.SECURITY_DEPOSIT_CAR


# ─── The engine ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AddOnCharge:
    """One add-on line: quantity x daily rate x billed days (BR-7, PR8)."""

    add_on_id: int
    name: str
    quantity: int
    daily_rate: Decimal
    days: int
    amount: Decimal


@dataclass(frozen=True)
class Quote:
    """Book.Quote.Display. total_payable excludes the deposit (Pay.Deposit)."""

    tariff_id: int
    billing_unit: str
    billing_count: int
    unit_rate: Decimal
    base_charge: Decimal
    add_ons: tuple[AddOnCharge, ...]
    add_ons_total: Decimal
    rental_charge: Decimal  # base + add-ons
    discount_code: str
    discount_amount: Decimal
    taxable_amount: Decimal  # PR1: rental charge less the discount
    tax_rate_percent: Decimal
    tax_amount: Decimal
    total_payable: Decimal
    security_deposit: Decimal
    free_helmets_per_rider: int  # BR-7: 0 for a car
    terms: dict = field(default_factory=dict)


def calculate_price(
    *,
    tariff: Tariff,
    vehicle_type: str,
    pickup: datetime,
    return_: datetime,
    add_ons: tuple[tuple[AddOn, int], ...] | list[tuple[AddOn, int]] = (),
    discount: DiscountCode | None = None,
    tax_rate_percent: Decimal | None = None,
) -> Quote:
    """Exp 3 Tariff.calculate_price(): BR-6 = tariff + add-ons + taxes - discount.

    Pure: no database access and no clock. `add_ons` pairs each AddOn with a
    quantity; `tax_rate_percent` defaults to TAX_RATE_PERCENT (D14).
    """
    rate = settings.TAX_RATE_PERCENT if tax_rate_percent is None else tax_rate_percent
    period = billing_period(pickup, return_)
    unit_rate = tariff.daily_rate if period.unit == "day" else tariff.hourly_rate
    base = _money(unit_rate * period.count)

    lines = tuple(
        AddOnCharge(
            add_on_id=add_on.pk,
            name=add_on.name,
            quantity=quantity,
            daily_rate=add_on.daily_rate,
            days=period.add_on_days,
            amount=_money(add_on.daily_rate * quantity * period.add_on_days),
        )
        for add_on, quantity in add_ons
    )
    add_ons_total = sum((line.amount for line in lines), Decimal("0.00"))
    rental_charge = base + add_ons_total

    discount_amount = Decimal("0.00")
    if discount is not None:
        if discount.discount_type == DiscountCode.DiscountType.PERCENT:
            discount_amount = _money(rental_charge * discount.value / 100)
        else:
            discount_amount = min(discount.value, rental_charge)  # PR6

    taxable = rental_charge - discount_amount  # PR1
    tax = _money(taxable * rate / 100)
    two_wheeler = vehicle_type == VehicleType.TWO_WHEELER
    return Quote(
        tariff_id=tariff.pk,
        billing_unit=period.unit,
        billing_count=period.count,
        unit_rate=unit_rate,
        base_charge=base,
        add_ons=lines,
        add_ons_total=add_ons_total,
        rental_charge=rental_charge,
        discount_code=discount.code if discount is not None else "",
        discount_amount=discount_amount,
        taxable_amount=taxable,
        tax_rate_percent=rate,
        tax_amount=tax,
        total_payable=taxable + tax,
        security_deposit=security_deposit_for(vehicle_type),
        free_helmets_per_rider=settings.FREE_HELMETS_PER_RIDER if two_wheeler else 0,
        terms=quote_terms(tariff),
    )


def quote_terms(tariff: Tariff) -> dict:
    """Book.Quote.Terms: the figures the customer accepts before paying."""
    return {
        "free_km_allowance_per_day": tariff.free_km_allowance,  # unit proposed (P5)
        "excess_km_rate": tariff.excess_km_rate,  # BR-11
        "late_return_grace_minutes": int(settings.LATE_RETURN_GRACE.total_seconds() // 60),
        "late_return_hourly_rate": tariff.hourly_rate,  # BR-10
        "late_return_daily_cap": tariff.daily_rate,  # BR-10
        "late_return_full_day_after_hours": int(
            settings.LATE_RETURN_FULL_DAY_AFTER.total_seconds() // 3600
        ),
        "fuel_shortfall_service_charge_percent": settings.FUEL_SHORTFALL_SERVICE_CHARGE_PERCENT,
        "cancellation_refunds": [  # BR-8
            {
                "notice_hours_at_least": int(
                    settings.CANCELLATION_FULL_REFUND_NOTICE.total_seconds() // 3600
                ),
                "refund_percent": settings.CANCELLATION_REFUND_PERCENT_FULL,
            },
            {
                "notice_hours_at_least": int(
                    settings.CANCELLATION_PARTIAL_REFUND_NOTICE.total_seconds() // 3600
                ),
                "refund_percent": settings.CANCELLATION_REFUND_PERCENT_PARTIAL,
            },
            {
                "notice_hours_at_least": 0,
                "refund_percent": settings.CANCELLATION_REFUND_PERCENT_LATE,
            },
        ],
        "no_show_retained_percent": settings.NO_SHOW_RETAINED_PERCENT,
    }


# ─── Looking up what the engine needs ─────────────────────────────────────


def current_tariff(category: VehicleCategory, at: datetime | None = None) -> Tariff:
    """Fleet.Tariff.History / BR-13: the category's tariff in force at `at` (default now)."""
    at = at or timezone.now()
    tariff = (
        Tariff.objects.filter(vehicle_category=category, effective_from__lte=at)
        .order_by("-effective_from")
        .first()
    )
    if tariff is None:
        raise PricingError("vehicle", "This vehicle has no tariff in force yet.")
    return tariff


def tariffs_in_force(at: datetime | None = None) -> dict[int, Tariff]:
    """The tariff in force for every category, in one query (for the search estimate)."""
    at = at or timezone.now()
    tariffs = (
        Tariff.objects.filter(effective_from__lte=at)
        .order_by("vehicle_category_id", "-effective_from")
        .distinct("vehicle_category_id")
    )
    return {tariff.vehicle_category_id: tariff for tariff in tariffs}


def resolve_add_ons(requested: list[tuple[int, int]], vehicle_type: str) -> list[tuple[AddOn, int]]:
    """Book.Addons: active add-ons that suit the vehicle type, each chosen once."""
    ids = [add_on_id for add_on_id, _ in requested]
    if len(ids) != len(set(ids)):
        raise PricingError("add_ons", "Choose each add-on only once.")
    found = AddOn.objects.in_bulk(ids)
    chosen = []
    for add_on_id, quantity in requested:
        add_on = found.get(add_on_id)
        if add_on is None or not add_on.is_active:
            raise PricingError("add_ons", "One of the chosen add-ons is not available.")
        if add_on.vehicle_type and add_on.vehicle_type != vehicle_type:
            raise PricingError(
                "add_ons", f"{add_on.name} is only offered with a {add_on.vehicle_type.lower()}."
            )
        chosen.append((add_on, quantity))
    return chosen


def resolve_discount(code: str, at: datetime | None = None) -> DiscountCode | None:
    """D17: a code is usable while active, inside its window and under its usage limit."""
    code = code.strip()
    if not code:
        return None
    at = at or timezone.now()
    discount = DiscountCode.objects.filter(code__iexact=code).first()
    if discount is None:
        raise PricingError("discount_code", "This discount code does not exist.")
    if not discount.is_active or not (discount.valid_from <= at < discount.valid_to):
        raise PricingError("discount_code", "This discount code is not valid now.")
    if discount.usage_limit is not None and discount.times_used >= discount.usage_limit:
        raise PricingError("discount_code", "This discount code has been used up.")
    return discount


def quote(
    vehicle: Vehicle,
    pickup: datetime,
    return_: datetime,
    *,
    add_ons: list[tuple[int, int]] | None = None,
    discount_code: str = "",
    at: datetime | None = None,
) -> Quote:
    """Book.Quote.Display for one vehicle, at the tariff in force now (BR-13).

    Raises PricingError (with the field at fault) for an unusable add-on or
    code, or when the category has no tariff. The period is checked by the
    caller (BR-5, fleet.services.availability.check_period).
    """
    vehicle_type = vehicle.category.vehicle_type
    return calculate_price(
        tariff=current_tariff(vehicle.category, at),
        vehicle_type=vehicle_type,
        pickup=pickup,
        return_=return_,
        add_ons=resolve_add_ons(add_ons or [], vehicle_type),
        discount=resolve_discount(discount_code, at),
    )


def estimate(tariff: Tariff, vehicle_type: str, pickup: datetime, return_: datetime) -> Quote:
    """Search.Price (PR9): base charge plus tax, no add-ons or discount."""
    return calculate_price(tariff=tariff, vehicle_type=vehicle_type, pickup=pickup, return_=return_)
