"""Return.Charges and Return.Settle: the itemised settlement of a return.

Exp 4 sequence 2: Tariff.calculate_price() "excess km, fuel, late return
(BR-10 to BR-12)" returns the itemised settlement; DFD process 6.3 Compute
Settlement Charges. calculate_settlement() is pure: it reads only its
arguments and the business-rule settings, never the database or the clock,
so every case is tested directly (Maintainability-2: settlement at 100%).

Every figure comes from the booking as it is now (R2 may have extended or
modified it): the current return time, the tariff the booking was priced at
(BR-13) and its free-kilometre allowance. The rental itself, extensions
included, was paid before the return and is never charged here.

Team proposals (the SRS is silent; docs/traceability-return.md, N2-P1 to P6):
- N2-P1: after BR-10's grace, the hours of a late return are counted as
  BR-6 counts them (PR2): whole hours, a part-hour billed only past the
  15-minute grace.
- N2-P2: BR-11's allowance is free_km_allowance per rental day, the days
  counted as add-ons are (PR8: under 24 hours is one day).
- N2-P3: BR-12's shortfall is the drop in percent of the vehicle's
  fuel_capacity, priced at the FuelPrice in force at the return time.
- N2-P4: tax at TAX_RATE_PERCENT (D14) is added on the return charges, as
  BR-6 adds taxes to usage-based charges; it is its own line.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

from apps.core.choices import FuelType
from apps.pricing.services import billing_period

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
HOUR = timedelta(hours=1)
DAY = timedelta(hours=24)
FUEL_UNITS = {
    FuelType.PETROL: "L",
    FuelType.DIESEL: "L",
    FuelType.CNG: "kg",
    FuelType.ELECTRIC: "kWh",
}


class SettlementError(ValueError):
    """The settlement cannot be computed; `code` is stable for the client."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ExtraCharge:
    """A charge the staff member enters: an accessory not returned, or damage."""

    description: str
    amount: Decimal
    justification: str = ""


@dataclass(frozen=True)
class ChargeItem:
    """One line of the settlement (Return.Charges: "as separate items")."""

    kind: str  # late_return, excess_km, fuel_shortfall, accessory, damage, tax
    description: str
    amount: Decimal
    justification: str = ""


@dataclass(frozen=True)
class Settlement:
    lines: tuple[ChargeItem, ...]
    total: Decimal  # every line, tax included
    deposit: Decimal
    deposit_used: Decimal  # Return.Settle: deducted from the security deposit
    refund: Decimal  # BR-14: the balance refunded
    due: Decimal  # Pay.Dues: the charges above the deposit
    distance: int  # Return.Complete: the total distance travelled
    free_km: int


def _money(value: Decimal) -> Decimal:
    """PR5: round half-up to the paisa."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _plural(count: int, unit: str) -> str:
    return f"{count} {unit}{'' if count == 1 else 's'}"


def _duration(length: timedelta) -> str:
    minutes = int(length.total_seconds() // 60)
    days, minutes = divmod(minutes, 24 * 60)
    hours, minutes = divmod(minutes, 60)
    parts = [(days, "d"), (hours, "h"), (minutes, "min")]
    return " ".join(f"{count} {unit}" for count, unit in parts if count)


def late_return(late: timedelta, hourly_rate: Decimal, daily_rate: Decimal) -> ChargeItem | None:
    """BR-10: 15 minutes' grace, then the hourly rate, capped at one day's rate for each
    24-hour period; a delay of more than 6 hours in a period is billed as a full day."""
    if late <= settings.LATE_RETURN_GRACE:
        return None
    full_days, rest = divmod(late, settings.LATE_RETURN_DAILY_CAP_PERIOD)
    days, hours = full_days, 0
    if rest > settings.LATE_RETURN_FULL_DAY_AFTER:
        days += 1
    else:
        whole, part = divmod(rest, HOUR)
        hours = whole + (1 if part > settings.LATE_RETURN_GRACE else 0)  # N2-P1
    hours_charge = min(hourly_rate * hours, daily_rate)
    amount = _money(daily_rate * days + hours_charge)
    if amount <= 0:
        return None  # a zero tariff rate
    terms = []
    if days:
        terms.append(f"{_plural(days, 'day')} at {daily_rate}")
    if hours:
        capped = " (capped at one day's rate)" if hours_charge < hourly_rate * hours else ""
        terms.append(f"{_plural(hours, 'hour')} at {hourly_rate}{capped}")
    return ChargeItem(
        "late_return",
        f"Late return, {_duration(late)} after the return time: {' + '.join(terms)} (BR-10)",
        amount,
    )


def excess_km(distance: int, free_km: int, rate: Decimal) -> ChargeItem | None:
    """BR-11: distance beyond the booking's free allowance, at the excess-kilometre rate."""
    excess = distance - free_km
    amount = _money(rate * excess) if excess > 0 else ZERO
    if amount <= 0:
        return None
    return ChargeItem(
        "excess_km",
        f"Excess kilometres, {excess} km over the {free_km} km allowance at {rate} per km (BR-11)",
        amount,
    )


def fuel_shortfall(
    issued: Decimal,
    returned: Decimal,
    *,
    fuel_type: str,
    capacity: Decimal | None,
    price: Decimal | None,
) -> ChargeItem | None:
    """BR-12: a shortfall at the prevailing fuel or electricity price plus 20 percent."""
    shortfall = issued - returned
    if shortfall <= 0:
        return None
    if capacity is None:
        raise SettlementError(
            "fuel_capacity_unknown",
            "The vehicle's tank or battery capacity is not on record, so the fuel or charge "
            "shortfall cannot be charged (BR-12). Ask an Administrator to add it.",
        )
    if price is None:
        raise SettlementError(
            "fuel_price_unknown",
            f"No {fuel_type.lower()} price is in force, so the fuel or charge shortfall cannot be "
            "charged (BR-12). Ask an Administrator to add one.",
        )
    unit = FUEL_UNITS.get(fuel_type, "units")
    quantity = capacity * shortfall / 100
    surcharge = settings.FUEL_SHORTFALL_SERVICE_CHARGE_PERCENT
    amount = _money(quantity * price * (100 + surcharge) / 100)
    if amount <= 0:
        return None  # a zero capacity or price
    return ChargeItem(
        "fuel_shortfall",
        f"Fuel or charge shortfall, {shortfall.normalize():f}% of {capacity.normalize():f} {unit} "
        f"({_money(quantity)} {unit}) at {price} plus {surcharge.normalize():f}% (BR-12)",
        amount,
    )


def plausibility_limit(handed_over_at: datetime, returned_at: datetime) -> int:
    """Return.Odometer: beyond this distance a supervisor must approve the reading.

    ODOMETER_PLAUSIBILITY_KM_PER_DAY for every started day the vehicle was out, at least one.
    """
    started_days = -((handed_over_at - returned_at) // DAY)  # ceiling division
    return settings.ODOMETER_PLAUSIBILITY_KM_PER_DAY * max(1, started_days)


def calculate_settlement(
    *,
    tariff,
    pickup: datetime,
    return_due: datetime,
    returned_at: datetime,
    odometer_out: int,
    odometer_in: int,
    fuel_out: Decimal,
    fuel_in: Decimal,
    fuel_type: str,
    fuel_capacity: Decimal | None,
    fuel_price: Decimal | None,
    accessories: list[ExtraCharge] | tuple[ExtraCharge, ...] = (),
    damage: list[ExtraCharge] | tuple[ExtraCharge, ...] = (),
    deposit: Decimal,
    tax_rate_percent: Decimal | None = None,
) -> Settlement:
    """Exp 3 Tariff.calculate_price() at return: BR-10, BR-11, BR-12, the staff's charges,
    tax, and how the total splits between the deposit, its refund and a due (BR-14, Pay.Dues).

    `tariff` is the booking's own (hourly_rate, daily_rate, free_km_allowance,
    excess_km_rate); `return_due` is the booking's current return time.
    """
    if odometer_in < odometer_out:
        raise SettlementError(
            "odometer_lower",
            f"The odometer reading cannot be lower than the {odometer_out} km recorded at "
            "handover (Return.Odometer).",
        )
    distance = odometer_in - odometer_out
    free_km = tariff.free_km_allowance * billing_period(pickup, return_due).add_on_days  # N2-P2
    lines = [
        line
        for line in (
            late_return(returned_at - return_due, tariff.hourly_rate, tariff.daily_rate),
            excess_km(distance, free_km, tariff.excess_km_rate),
            fuel_shortfall(
                fuel_out, fuel_in, fuel_type=fuel_type, capacity=fuel_capacity, price=fuel_price
            ),
        )
        if line is not None
    ]
    for kind, entered in (("accessory", accessories), ("damage", damage)):
        lines += [
            ChargeItem(kind, extra.description, _money(extra.amount), extra.justification)
            for extra in entered
            if extra.amount > 0
        ]
    subtotal = sum((line.amount for line in lines), ZERO)
    rate = settings.TAX_RATE_PERCENT if tax_rate_percent is None else tax_rate_percent
    tax = _money(subtotal * rate / 100)
    if tax > 0:  # N2-P4
        lines.append(
            ChargeItem("tax", f"Tax at {rate.normalize():f}% on the return charges (BR-6)", tax)
        )
    total = subtotal + tax
    used = min(total, deposit)
    return Settlement(
        lines=tuple(lines),
        total=total,
        deposit=deposit,
        deposit_used=used,
        refund=deposit - used,
        due=total - used,
        distance=distance,
        free_km=free_km,
    )
