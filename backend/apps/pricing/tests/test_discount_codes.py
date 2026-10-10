"""DiscountCode constraints (D17)."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.bookings.tests.factories import BookingFactory
from apps.pricing.models import DiscountCode
from apps.pricing.tests.factories import DiscountCodeFactory

pytestmark = pytest.mark.django_db


def test_factory_creates_a_valid_code():
    code = DiscountCodeFactory()
    code.full_clean()
    assert str(code) == code.code


def test_codes_are_unique_regardless_of_case():
    DiscountCodeFactory(code="WELCOME10")
    with pytest.raises(IntegrityError), transaction.atomic():
        DiscountCodeFactory(code="welcome10")


@pytest.mark.parametrize("value", ["100.01", "150.00"])
def test_percent_cannot_exceed_100(value):
    with pytest.raises(IntegrityError), transaction.atomic():
        DiscountCodeFactory(value=Decimal(value))


def test_percent_of_exactly_100_is_allowed():
    assert DiscountCodeFactory(value=Decimal("100.00")).pk


def test_fixed_amount_may_exceed_100():
    code = DiscountCodeFactory(discount_type=DiscountCode.DiscountType.FIXED, value=Decimal("500"))
    assert code.pk


@pytest.mark.parametrize("value", ["0", "-5"])
def test_value_must_be_positive(value):
    with pytest.raises(IntegrityError), transaction.atomic():
        DiscountCodeFactory(value=Decimal(value))


def test_validity_window_must_end_after_it_starts():
    code = DiscountCodeFactory.build()
    with pytest.raises(IntegrityError), transaction.atomic():
        DiscountCodeFactory(valid_from=code.valid_to, valid_to=code.valid_to - timedelta(days=1))


def test_times_used_cannot_exceed_the_usage_limit():
    DiscountCodeFactory(usage_limit=3, times_used=3)
    with pytest.raises(IntegrityError), transaction.atomic():
        DiscountCodeFactory(usage_limit=3, times_used=4)
    assert DiscountCodeFactory(usage_limit=None, times_used=1000).pk


def test_booking_records_the_code_and_amount():
    code = DiscountCodeFactory()
    booking = BookingFactory(discount_code=code, discount_amount=Decimal("180.00"))
    assert list(code.bookings.all()) == [booking]
    with pytest.raises(IntegrityError), transaction.atomic():
        BookingFactory(discount_amount=Decimal("-1.00"))
