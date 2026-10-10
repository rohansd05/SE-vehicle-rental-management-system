"""BR-3, BR-6, BR-7, D14, D17 and PR1-PR9: the pure pricing engine.

No test here is marked django_db, so any database access would fail it:
calculate_price() works on the objects it is given.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from django.test import override_settings

from apps.core.choices import VehicleType
from apps.pricing.models import AddOn, DiscountCode, Tariff
from apps.pricing.services import (
    BillingPeriod,
    billing_period,
    calculate_price,
    estimate,
    security_deposit_for,
)

CAR = VehicleType.CAR
TWO_WHEELER = VehicleType.TWO_WHEELER
PICKUP = datetime(2026, 10, 20, 4, 30, tzinfo=UTC)


def tariff(**overrides) -> Tariff:
    values = {
        "pk": 7,
        "hourly_rate": Decimal("150.00"),
        "daily_rate": Decimal("1800.00"),
        "weekly_rate": Decimal("11000.00"),
        "security_deposit": Decimal("9999.00"),  # PR4: never used for the deposit
        "free_km_allowance": 250,
        "excess_km_rate": Decimal("12.00"),
    }
    values.update(overrides)
    return Tariff(**values)


def add_on(pk: int, name: str, rate: str) -> AddOn:
    return AddOn(pk=pk, name=name, daily_rate=Decimal(rate))


def code(kind: str, value: str, name: str = "SAVE") -> DiscountCode:
    return DiscountCode(code=name, discount_type=kind, value=Decimal(value))


def price(length: timedelta, *, vehicle_type=CAR, **kwargs):
    return calculate_price(
        tariff=kwargs.pop("tariff", tariff()),
        vehicle_type=vehicle_type,
        pickup=PICKUP,
        return_=PICKUP + length,
        **kwargs,
    )


# ─── Billing period: BR-6 with PR2 ────────────────────────────────────────


@pytest.mark.parametrize(
    ("length", "expected"),
    [
        (timedelta(hours=4), BillingPeriod("hour", 4)),
        (timedelta(hours=4, minutes=15), BillingPeriod("hour", 4)),  # inside the grace
        (timedelta(hours=4, minutes=16), BillingPeriod("hour", 5)),  # past the grace
        (timedelta(hours=23, minutes=10), BillingPeriod("hour", 23)),
        (timedelta(hours=23, minutes=59), BillingPeriod("hour", 24)),
        (timedelta(hours=24), BillingPeriod("day", 1)),  # PR2: 24 h is one day
        (timedelta(hours=24, minutes=10), BillingPeriod("day", 2)),  # PR2: a part-day is a day
        (timedelta(days=2), BillingPeriod("day", 2)),
        (timedelta(days=7), BillingPeriod("day", 7)),
        (timedelta(days=30), BillingPeriod("day", 30)),
    ],
)
def test_billing_period(length, expected):
    assert billing_period(PICKUP, PICKUP + length) == expected


def test_add_ons_count_billed_days_and_one_day_under_24_hours():
    """PR8."""
    assert BillingPeriod("day", 3).add_on_days == 3
    assert BillingPeriod("hour", 9).add_on_days == 1


# ─── Base charge ──────────────────────────────────────────────────────────


def test_an_hourly_rental_is_charged_at_the_hourly_rate():
    quote = price(timedelta(hours=5))
    assert (quote.billing_unit, quote.billing_count, quote.unit_rate) == (
        "hour",
        5,
        Decimal("150.00"),
    )
    assert quote.base_charge == Decimal("750.00")
    assert quote.tax_amount == Decimal("135.00")
    assert quote.total_payable == Decimal("885.00")


def test_a_rental_of_days_is_charged_at_the_daily_rate():
    quote = price(timedelta(days=2))
    assert quote.base_charge == Decimal("3600.00")
    assert quote.tax_amount == Decimal("648.00")
    assert quote.total_payable == Decimal("4248.00")


def test_the_weekly_rate_is_never_applied():
    """PR3: seven days are seven daily rates, not the weekly rate."""
    assert price(timedelta(days=7)).base_charge == Decimal("12600.00")


def test_the_hourly_charge_is_not_capped_at_the_daily_rate():
    """PR7: 23 hours cost more than a day's rate; BR-10's cap is for late returns only."""
    assert price(timedelta(hours=23)).base_charge == Decimal("3450.00")


# ─── Add-ons: BR-7, PR8 ───────────────────────────────────────────────────


def test_add_ons_are_charged_per_billed_day_and_quantity():
    seat, helmet = add_on(1, "Child seat", "100.00"), add_on(2, "Additional helmet", "50.00")
    quote = price(timedelta(days=2), add_ons=[(seat, 1), (helmet, 2)])
    assert [(line.name, line.quantity, line.days, line.amount) for line in quote.add_ons] == [
        ("Child seat", 1, 2, Decimal("200.00")),
        ("Additional helmet", 2, 2, Decimal("200.00")),
    ]
    assert quote.add_ons_total == Decimal("400.00")
    assert quote.rental_charge == Decimal("4000.00")
    assert quote.total_payable == Decimal("4720.00")


def test_an_add_on_on_an_hourly_rental_is_one_day():
    quote = price(timedelta(hours=6), add_ons=[(add_on(1, "Child seat", "100.00"), 1)])
    assert quote.add_ons[0].days == 1
    assert quote.add_ons_total == Decimal("100.00")


def test_no_add_ons_means_a_zero_add_on_total():
    quote = price(timedelta(days=1))
    assert quote.add_ons == ()
    assert quote.add_ons_total == Decimal("0.00")


# ─── Discount (D17) and tax (D14): PR1, PR5, PR6 ──────────────────────────


def test_a_percent_discount_comes_off_before_tax():
    """PR1: tax is charged on the rental charge less the discount."""
    quote = price(
        timedelta(days=2),
        add_ons=[(add_on(1, "Child seat", "100.00"), 1)],
        discount=code(DiscountCode.DiscountType.PERCENT, "10.00", "WELCOME10"),
    )
    assert quote.rental_charge == Decimal("3800.00")
    assert quote.discount_code == "WELCOME10"
    assert quote.discount_amount == Decimal("380.00")
    assert quote.taxable_amount == Decimal("3420.00")
    assert quote.tax_amount == Decimal("615.60")
    assert quote.total_payable == Decimal("4035.60")


def test_a_fixed_discount_comes_off_in_full():
    quote = price(timedelta(days=1), discount=code(DiscountCode.DiscountType.FIXED, "500.00"))
    assert quote.discount_amount == Decimal("500.00")
    assert quote.taxable_amount == Decimal("1300.00")
    assert quote.total_payable == Decimal("1534.00")


def test_a_fixed_discount_is_capped_at_the_rental_charge():
    """PR6: the total is never negative."""
    quote = price(timedelta(hours=4), discount=code(DiscountCode.DiscountType.FIXED, "5000.00"))
    assert quote.discount_amount == Decimal("600.00")
    assert (quote.taxable_amount, quote.tax_amount, quote.total_payable) == (
        Decimal("0.00"),
        Decimal("0.00"),
        Decimal("0.00"),
    )


def test_amounts_are_rounded_half_up_to_the_paisa():
    """PR5: 10% of 1234.55 is 123.455 -> 123.46; 18% of 1111.09 is 199.9962 -> 200.00."""
    quote = price(
        timedelta(hours=5),
        tariff=tariff(hourly_rate=Decimal("246.91")),
        discount=code(DiscountCode.DiscountType.PERCENT, "10.00"),
    )
    assert quote.rental_charge == Decimal("1234.55")
    assert quote.discount_amount == Decimal("123.46")
    assert quote.tax_amount == Decimal("200.00")
    assert quote.total_payable == Decimal("1311.09")


def test_no_discount_means_no_code_and_zero():
    quote = price(timedelta(days=1))
    assert (quote.discount_code, quote.discount_amount) == ("", Decimal("0.00"))


@override_settings(TAX_RATE_PERCENT=Decimal("5.00"))
def test_the_tax_rate_comes_from_the_business_rules_settings():
    """D14 is a placeholder; the engine must follow the setting, never a literal 18."""
    quote = price(timedelta(days=1))
    assert quote.tax_rate_percent == Decimal("5.00")
    assert quote.tax_amount == Decimal("90.00")


def test_an_explicit_tax_rate_wins():
    assert price(timedelta(days=1), tax_rate_percent=Decimal("0")).tax_amount == Decimal("0.00")


# ─── Deposit (BR-3, PR4) and helmets (BR-7) ───────────────────────────────


def test_the_deposit_is_br3s_amount_for_the_vehicle_type():
    assert price(timedelta(days=1), vehicle_type=CAR).security_deposit == Decimal("5000.00")
    assert price(timedelta(days=1), vehicle_type=TWO_WHEELER).security_deposit == Decimal(
        "2000.00"
    )


@override_settings(SECURITY_DEPOSIT_CAR=Decimal("6000.00"))
def test_the_deposit_comes_from_the_settings():
    assert security_deposit_for(CAR) == Decimal("6000.00")


def test_the_deposit_is_not_part_of_the_total():
    """Pay.Deposit: held apart, never revenue."""
    quote = price(timedelta(days=1))
    assert quote.total_payable == quote.taxable_amount + quote.tax_amount


def test_one_free_helmet_per_rider_with_a_two_wheeler_only():
    assert price(timedelta(days=1), vehicle_type=TWO_WHEELER).free_helmets_per_rider == 1
    assert price(timedelta(days=1), vehicle_type=CAR).free_helmets_per_rider == 0


# ─── Terms (Book.Quote.Terms), estimate (Search.Price), money types ───────


def test_the_quote_carries_the_rental_terms():
    terms = price(timedelta(days=1)).terms
    assert terms["free_km_allowance_per_day"] == 250
    assert terms["excess_km_rate"] == Decimal("12.00")
    assert terms["late_return_grace_minutes"] == 15
    assert terms["late_return_hourly_rate"] == Decimal("150.00")
    assert terms["late_return_daily_cap"] == Decimal("1800.00")
    assert terms["late_return_full_day_after_hours"] == 6
    assert terms["fuel_shortfall_service_charge_percent"] == Decimal("20")
    assert terms["cancellation_refunds"] == [
        {"notice_hours_at_least": 48, "refund_percent": Decimal("100")},
        {"notice_hours_at_least": 12, "refund_percent": Decimal("75")},
        {"notice_hours_at_least": 0, "refund_percent": Decimal("50")},
    ]
    assert terms["no_show_retained_percent"] == Decimal("50")


def test_the_estimate_is_base_plus_tax():
    """PR9."""
    result = estimate(tariff(), CAR, PICKUP, PICKUP + timedelta(days=2))
    assert result.add_ons == ()
    assert result.discount_amount == Decimal("0.00")
    assert result.total_payable == Decimal("4248.00")


def test_every_amount_is_a_decimal():
    """CO-6: never a float."""
    quote = price(
        timedelta(days=2),
        add_ons=[(add_on(1, "Child seat", "100.00"), 1)],
        discount=code(DiscountCode.DiscountType.PERCENT, "10.00"),
    )
    amounts = [
        quote.unit_rate,
        quote.base_charge,
        quote.add_ons_total,
        quote.rental_charge,
        quote.discount_amount,
        quote.taxable_amount,
        quote.tax_rate_percent,
        quote.tax_amount,
        quote.total_payable,
        quote.security_deposit,
        quote.add_ons[0].amount,
    ]
    assert all(isinstance(amount, Decimal) for amount in amounts)
