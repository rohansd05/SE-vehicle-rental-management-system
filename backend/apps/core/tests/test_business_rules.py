"""Business-rule constants match SRS Section 5.5 (traceability)."""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings


def test_br1_turnaround_buffer():
    assert settings.BOOKING_TURNAROUND_BUFFER == timedelta(minutes=60)


def test_br2_minimum_ages():
    assert (settings.MINIMUM_AGE_TWO_WHEELER, settings.MINIMUM_AGE_CAR) == (18, 21)


def test_br3_security_deposits_are_decimal():
    assert settings.SECURITY_DEPOSIT_TWO_WHEELER == Decimal("2000.00")
    assert settings.SECURITY_DEPOSIT_CAR == Decimal("5000.00")


def test_br5_rental_period_limits():
    assert settings.RENTAL_PERIOD_MINIMUM == timedelta(hours=4)
    assert settings.RENTAL_PERIOD_MAXIMUM == timedelta(days=30)


def test_br8_cancellation_slabs():
    assert settings.CANCELLATION_FULL_REFUND_NOTICE == timedelta(hours=48)
    assert settings.CANCELLATION_PARTIAL_REFUND_NOTICE == timedelta(hours=12)
    assert (
        settings.CANCELLATION_REFUND_PERCENT_FULL,
        settings.CANCELLATION_REFUND_PERCENT_PARTIAL,
        settings.CANCELLATION_REFUND_PERCENT_LATE,
        settings.NO_SHOW_RETAINED_PERCENT,
    ) == (Decimal("100"), Decimal("75"), Decimal("50"), Decimal("50"))


def test_br10_and_br12_late_return_and_fuel():
    assert settings.LATE_RETURN_GRACE == timedelta(minutes=15)
    assert settings.LATE_RETURN_FULL_DAY_AFTER == timedelta(hours=6)
    assert settings.FUEL_SHORTFALL_SERVICE_CHARGE_PERCENT == Decimal("20")


def test_br15_service_intervals():
    assert settings.PREVENTIVE_SERVICE_INTERVAL_KM_CAR == 5000
    assert settings.PREVENTIVE_SERVICE_INTERVAL_MONTHS_CAR == 6
    assert settings.PREVENTIVE_SERVICE_INTERVAL_KM_TWO_WHEELER == 3000
    assert settings.PREVENTIVE_SERVICE_INTERVAL_MONTHS_TWO_WHEELER == 4


def test_fixed_values_from_the_handoff():
    assert settings.PAYMENT_HOLD_DURATION == timedelta(minutes=15)
    assert settings.MODIFICATION_CUTOFF == timedelta(hours=12)
    assert settings.NO_SHOW_AFTER == timedelta(hours=2)
    assert settings.PICKUP_CODE_LENGTH == 6
