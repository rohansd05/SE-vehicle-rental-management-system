"""Return.Charges: the pure settlement calculation (BR-10, BR-11, BR-12, BR-14; Pay.Dues).

No database: settlement.py reads only its arguments and the business-rule
settings (Maintainability-2: settlement logic at 100% coverage).
"""

from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.rentals import settlement
from apps.rentals.settlement import ExtraCharge, SettlementError

D = Decimal
HOURLY, DAILY = D("150.00"), D("1800.00")
PICKUP = datetime(2026, 10, 16, 10, 0, tzinfo=timezone.get_fixed_timezone(330))
DUE = PICKUP + timedelta(days=1)  # a one-day rental


def tariff(**overrides):
    values = {
        "hourly_rate": HOURLY,
        "daily_rate": DAILY,
        "free_km_allowance": 250,
        "excess_km_rate": D("10.00"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def settle(**overrides):
    values = {
        "tariff": tariff(),
        "pickup": PICKUP,
        "return_due": DUE,
        "returned_at": DUE,
        "odometer_out": 12000,
        "odometer_in": 12100,
        "fuel_out": D("100.00"),
        "fuel_in": D("100.00"),
        "fuel_type": "Petrol",
        "fuel_capacity": D("40.00"),
        "fuel_price": D("100.00"),
        "deposit": D("5000.00"),
    }
    values.update(overrides)
    return settlement.calculate_settlement(**values)


# ─── BR-10 late return ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("late", "amount"),
    [
        (timedelta(minutes=-30), None),  # early
        (timedelta(minutes=15), None),  # the grace period
        (timedelta(minutes=16), D("150.00")),  # past the grace: one hour
        (timedelta(hours=1, minutes=10), D("150.00")),  # N2-P1: the 10-minute part is in grace
        (timedelta(hours=1, minutes=20), D("300.00")),
        (timedelta(hours=3), D("450.00")),
        (timedelta(hours=6), D("900.00")),  # exactly 6 hours is still hourly
        (timedelta(hours=6, minutes=1), D("1800.00")),  # over 6 hours: a full day
        (timedelta(hours=24), D("1800.00")),
        (timedelta(hours=24, minutes=30), D("1950.00")),  # a day and an hour
        (timedelta(hours=30, minutes=10), D("3600.00")),  # a day, then over 6 hours: a day
    ],
)
def test_late_return_br10(late, amount):
    line = settlement.late_return(late, HOURLY, DAILY)
    assert (line.amount if line else None) == amount
    if line:
        assert line.kind == "late_return" and line.description.endswith("(BR-10)")


def test_late_hours_are_capped_at_one_days_rate():
    line = settlement.late_return(timedelta(hours=5), D("400.00"), DAILY)
    assert line.amount == DAILY
    assert "capped at one day's rate" in line.description


def test_late_return_describes_the_delay_and_the_rates():
    line = settlement.late_return(timedelta(days=1, hours=2, minutes=5), HOURLY, DAILY)
    assert line.description == (
        "Late return, 1 d 2 h 5 min after the return time: 1 day at 1800.00 + "
        "2 hours at 150.00 (BR-10)"
    )


def test_a_zero_tariff_charges_no_late_return():
    assert settlement.late_return(timedelta(hours=3), D("0.00"), D("0.00")) is None


# ─── BR-11 excess kilometres ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("distance", "amount"), [(200, None), (250, None), (251, D("10.00")), (400, D("1500.00"))]
)
def test_excess_km_br11(distance, amount):
    line = settlement.excess_km(distance, 250, D("10.00"))
    assert (line.amount if line else None) == amount


def test_excess_km_names_the_allowance_and_rate():
    line = settlement.excess_km(400, 250, D("10.00"))
    assert line.description == (
        "Excess kilometres, 150 km over the 250 km allowance at 10.00 per km (BR-11)"
    )


def test_a_zero_excess_rate_charges_nothing():
    assert settlement.excess_km(400, 250, D("0.00")) is None


# ─── BR-12 fuel or charge shortfall ───────────────────────────────────────


def fuel(issued="100", returned="75", **overrides):
    values = {"fuel_type": "Petrol", "capacity": D("40.00"), "price": D("100.00")}
    values.update(overrides)
    return settlement.fuel_shortfall(D(issued), D(returned), **values)


def test_fuel_shortfall_at_the_price_plus_20_percent_br12():
    line = fuel()  # 25% of 40 L = 10 L at 100.00, plus 20%
    assert line.amount == D("1200.00")
    assert line.description == (
        "Fuel or charge shortfall, 25% of 40 L (10.00 L) at 100.00 plus 20% (BR-12)"
    )


@pytest.mark.parametrize("returned", ["100", "110"])
def test_no_shortfall_no_charge(returned):
    assert fuel(returned=returned, capacity=None, price=None) is None


@pytest.mark.parametrize(
    ("fuel_type", "unit"), [("Electric", "kWh"), ("CNG", "kg"), ("Diesel", "L"), ("Other", "units")]
)
def test_the_unit_follows_the_fuel_type(fuel_type, unit):
    assert f"(10.00 {unit})" in fuel(fuel_type=fuel_type).description


def test_a_missing_capacity_is_refused():
    with pytest.raises(SettlementError) as raised:
        fuel(capacity=None)
    assert raised.value.code == "fuel_capacity_unknown"


def test_a_missing_fuel_price_is_refused():
    with pytest.raises(SettlementError) as raised:
        fuel(price=None)
    assert raised.value.code == "fuel_price_unknown"
    assert "petrol price" in str(raised.value)


def test_a_zero_fuel_price_charges_nothing():
    assert fuel(price=D("0.00")) is None


# ─── Return.Odometer plausibility ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("out_for", "limit"),
    [
        (timedelta(hours=3), 1000),
        (timedelta(hours=24), 1000),
        (timedelta(hours=24, minutes=1), 2000),
        (timedelta(days=3), 3000),
        (timedelta(0), 1000),
    ],
)
def test_plausibility_limit_per_started_day(out_for, limit):
    assert settlement.plausibility_limit(PICKUP, PICKUP + out_for) == limit


# ─── The whole settlement ─────────────────────────────────────────────────


def test_an_on_time_return_within_the_allowance_costs_nothing():
    result = settle()
    assert result.lines == ()
    assert (result.total, result.deposit_used, result.refund, result.due) == (
        D("0.00"),
        D("0.00"),
        D("5000.00"),
        D("0.00"),
    )
    assert result.distance == 100 and result.free_km == 250


def test_every_charge_is_a_separate_line_then_the_tax():
    result = settle(
        returned_at=DUE + timedelta(hours=3),
        odometer_in=12400,
        fuel_in=D("75.00"),
        accessories=[ExtraCharge("Accessory not returned: Child seat × 1", D("1500.00"))],
        damage=[ExtraCharge("Damage: dent", D("2000.00"), "Rear door dented")],
    )
    kinds = [line.kind for line in result.lines]
    assert kinds == ["late_return", "excess_km", "fuel_shortfall", "accessory", "damage", "tax"]
    amounts = [line.amount for line in result.lines]
    assert amounts[:5] == [D("450.00"), D("1500.00"), D("1200.00"), D("1500.00"), D("2000.00")]
    assert amounts[5] == D("1197.00")  # 18% of 6650.00 (D14 placeholder rate)
    assert result.lines[4].justification == "Rear door dented"
    assert result.total == D("7847.00")
    # Return.Settle: the deposit is used up and the rest is a due (Pay.Dues).
    assert (result.deposit_used, result.refund, result.due) == (
        D("5000.00"),
        D("0.00"),
        D("2847.00"),
    )


def test_charges_below_the_deposit_leave_a_balance_to_refund_br14():
    result = settle(odometer_in=12400, tax_rate_percent=D("0"))
    assert result.total == D("1500.00")
    assert (result.deposit_used, result.refund, result.due) == (
        D("1500.00"),
        D("3500.00"),
        D("0.00"),
    )
    assert [line.kind for line in result.lines] == ["excess_km"]  # no tax line at 0%


def test_staff_charges_of_zero_are_left_out():
    result = settle(accessories=[ExtraCharge("Accessory not returned: Helmet × 1", D("0.00"))])
    assert result.lines == ()


def test_the_allowance_and_lateness_follow_the_current_return_time():
    """R2 extended the booking to two days: 500 km free and no late charge at day two."""
    extended = DUE + timedelta(days=1)
    result = settle(return_due=extended, returned_at=extended, odometer_in=12450)
    assert result.free_km == 500
    assert result.lines == ()


def test_a_reading_below_the_handover_reading_is_rejected():
    with pytest.raises(SettlementError) as raised:
        settle(odometer_in=11999)
    assert raised.value.code == "odometer_lower"
    assert "12000 km" in str(raised.value)
