"""The lookups behind a quote: tariff in force (BR-13), add-ons (Book.Addons), codes (D17)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from apps.core.choices import VehicleType
from apps.fleet.tests.factories import CarFactory, TwoWheelerFactory, VehicleCategoryFactory
from apps.pricing.services import (
    PricingError,
    current_tariff,
    quote,
    resolve_add_ons,
    resolve_discount,
    tariffs_in_force,
)
from apps.pricing.tests.factories import AddOnFactory, DiscountCodeFactory, TariffFactory

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 11, 6, 0, tzinfo=UTC)
PICKUP = datetime(2026, 10, 20, 4, 30, tzinfo=UTC)
CAR = VehicleType.CAR
TWO_WHEELER = VehicleType.TWO_WHEELER


# ─── Tariff in force (Fleet.Tariff.History, BR-13) ────────────────────────


def test_the_latest_tariff_already_in_force_is_used():
    category = VehicleCategoryFactory(name="Hatchback")
    TariffFactory(vehicle_category=category, effective_from=NOW - timedelta(days=60))
    newer = TariffFactory(vehicle_category=category, effective_from=NOW - timedelta(days=1))
    TariffFactory(vehicle_category=category, effective_from=NOW + timedelta(days=5))
    assert current_tariff(category, NOW) == newer


def test_a_category_without_a_tariff_in_force_cannot_be_quoted():
    category = VehicleCategoryFactory(name="SUV")
    TariffFactory(vehicle_category=category, effective_from=NOW + timedelta(days=5))
    with pytest.raises(PricingError) as error:
        current_tariff(category, NOW)
    assert error.value.field == "vehicle"


def test_current_tariff_defaults_to_now():
    tariff = TariffFactory()
    assert current_tariff(tariff.vehicle_category) == tariff


def test_tariffs_in_force_gives_one_per_category():
    hatch, suv, sedan = (
        VehicleCategoryFactory(name=name) for name in ("Hatchback", "SUV", "Sedan")
    )
    TariffFactory(vehicle_category=hatch, effective_from=NOW - timedelta(days=60))
    hatch_now = TariffFactory(vehicle_category=hatch, effective_from=NOW - timedelta(days=1))
    suv_now = TariffFactory(vehicle_category=suv, effective_from=NOW - timedelta(days=9))
    TariffFactory(vehicle_category=sedan, effective_from=NOW + timedelta(days=1))
    assert tariffs_in_force(NOW) == {hatch.pk: hatch_now, suv.pk: suv_now}


def test_tariffs_in_force_defaults_to_now():
    tariff = TariffFactory()
    assert tariffs_in_force() == {tariff.vehicle_category_id: tariff}


# ─── Add-ons (Book.Addons, BR-7) ──────────────────────────────────────────


def test_add_ons_for_the_vehicle_type_or_any_type_are_accepted():
    helmet = AddOnFactory(name="Additional helmet", vehicle_type=TWO_WHEELER)
    delivery = AddOnFactory(name="Doorstep delivery", vehicle_type="")
    chosen = resolve_add_ons([(helmet.pk, 2), (delivery.pk, 1)], TWO_WHEELER)
    assert chosen == [(helmet, 2), (delivery, 1)]


@pytest.mark.parametrize(
    ("make", "message"),
    [
        (lambda: [(999999, 1)], "not available"),
        (lambda: [(AddOnFactory(is_active=False).pk, 1)], "not available"),
        (
            lambda: [(AddOnFactory(name="Child seat", vehicle_type=CAR).pk, 1)],
            "only offered with a car",
        ),
    ],
    ids=["unknown", "inactive", "wrong-vehicle-type"],
)
def test_an_unusable_add_on_is_refused(make, message):
    with pytest.raises(PricingError, match=message) as error:
        resolve_add_ons(make(), TWO_WHEELER)
    assert error.value.field == "add_ons"


def test_an_add_on_chosen_twice_is_refused():
    seat = AddOnFactory()
    with pytest.raises(PricingError, match="only once"):
        resolve_add_ons([(seat.pk, 1), (seat.pk, 2)], CAR)


# ─── Discount codes (D17) ─────────────────────────────────────────────────


def test_a_blank_code_means_no_discount():
    assert resolve_discount("  ") is None


def test_a_code_is_matched_regardless_of_case():
    discount = DiscountCodeFactory(code="WELCOME10")
    assert resolve_discount(" welcome10 ") == discount


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"is_active": False}, "not valid now"),
        (
            {"valid_from": NOW + timedelta(hours=1), "valid_to": NOW + timedelta(days=1)},
            "not valid now",
        ),
        ({"valid_from": NOW - timedelta(days=2), "valid_to": NOW}, "not valid now"),  # end excluded
        ({"usage_limit": 3, "times_used": 3}, "used up"),
    ],
    ids=["inactive", "not-started", "ended", "used-up"],
)
def test_an_unusable_code_is_refused(kwargs, message):
    defaults = {"valid_from": NOW - timedelta(days=1), "valid_to": NOW + timedelta(days=1)}
    DiscountCodeFactory(code="SAVE", **{**defaults, **kwargs})
    with pytest.raises(PricingError, match=message) as error:
        resolve_discount("SAVE", NOW)
    assert error.value.field == "discount_code"


def test_an_unknown_code_is_refused():
    with pytest.raises(PricingError, match="does not exist"):
        resolve_discount("NOPE", NOW)


def test_a_code_under_its_limit_or_unlimited_is_accepted():
    limited = DiscountCodeFactory(code="LIMITED", usage_limit=3, times_used=2)
    unlimited = DiscountCodeFactory(code="ALWAYS")
    assert resolve_discount("LIMITED") == limited
    assert resolve_discount("ALWAYS") == unlimited


# ─── quote(): everything together ─────────────────────────────────────────


def test_quote_prices_a_vehicle_at_its_tariff_with_add_ons_and_a_code():
    scooter = TwoWheelerFactory()
    tariff = TariffFactory(
        vehicle_category=scooter.category,
        hourly_rate=Decimal("60.00"),
        daily_rate=Decimal("500.00"),
    )
    helmet = AddOnFactory(
        name="Additional helmet", daily_rate=Decimal("50.00"), vehicle_type=TWO_WHEELER
    )
    DiscountCodeFactory(code="FLAT100", discount_type="Fixed", value=Decimal("100.00"))

    result = quote(
        scooter,
        PICKUP,
        PICKUP + timedelta(days=3),
        add_ons=[(helmet.pk, 1)],
        discount_code="flat100",
    )
    assert result.tariff_id == tariff.pk
    assert result.base_charge == Decimal("1500.00")
    assert result.add_ons_total == Decimal("150.00")
    assert result.discount_amount == Decimal("100.00")
    assert result.tax_amount == Decimal("279.00")  # 18% of 1550.00
    assert result.total_payable == Decimal("1829.00")
    assert result.security_deposit == Decimal("2000.00")
    assert result.free_helmets_per_rider == 1


def test_quote_without_extras():
    car = CarFactory()
    TariffFactory(vehicle_category=car.category)
    result = quote(car, PICKUP, PICKUP + timedelta(hours=6))
    assert (result.billing_unit, result.billing_count, result.total_payable) == (
        "hour",
        6,
        Decimal("1062.00"),
    )
