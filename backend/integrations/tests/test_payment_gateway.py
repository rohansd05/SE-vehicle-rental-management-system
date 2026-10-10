"""Mock payment gateway and factory."""

from decimal import Decimal

import pytest
from django.core.exceptions import ImproperlyConfigured

from integrations.payment_gateway import get_payment_gateway
from integrations.payment_gateway.mock import MockPaymentGateway


@pytest.fixture
def gateway() -> MockPaymentGateway:
    return MockPaymentGateway()


def test_factory_returns_mock_in_tests():
    assert isinstance(get_payment_gateway(), MockPaymentGateway)


def test_factory_rejects_unknown_backend(settings):
    settings.PAYMENT_GATEWAY_BACKEND = "nope"
    with pytest.raises(ImproperlyConfigured):
        get_payment_gateway()


def test_authorize_capture_refund_happy_path(gateway):
    auth = gateway.authorize(Decimal("5000.00"), "INR", "tok_ok", "k1")
    assert auth.success
    assert auth.transaction_id == "mock_txn_000001"

    capture = gateway.capture(auth.transaction_id, Decimal("5000.00"), "k2")
    assert capture.success

    refund = gateway.refund(auth.transaction_id, Decimal("1200.50"), "k3")
    assert refund.success
    assert refund.amount == Decimal("1200.50")


def test_decline_token_is_declined(gateway):
    response = gateway.authorize(Decimal("100.00"), "INR", MockPaymentGateway.DECLINE_TOKEN, "k")
    assert not response.success


def test_same_idempotency_key_returns_same_response(gateway):
    first = gateway.authorize(Decimal("100.00"), "INR", "tok_ok", "same")
    second = gateway.authorize(Decimal("100.00"), "INR", "tok_ok", "same")
    assert first == second
    assert gateway.authorize(Decimal("1.00"), "INR", "tok_ok", "other").transaction_id == (
        "mock_txn_000002"
    )

    gateway.capture(first.transaction_id, Decimal("100.00"), "cap")
    assert gateway.capture(first.transaction_id, Decimal("100.00"), "cap").success
    gateway.refund(first.transaction_id, Decimal("100.00"), "ref")
    assert gateway.refund(first.transaction_id, Decimal("100.00"), "ref").success


def test_capture_and_refund_limits(gateway):
    auth = gateway.authorize(Decimal("100.00"), "INR", "tok_ok", "a")
    assert not gateway.capture(auth.transaction_id, Decimal("100.01"), "c1").success
    assert not gateway.capture("mock_txn_999999", Decimal("1.00"), "c2").success
    assert gateway.capture(auth.transaction_id, Decimal("60.00"), "c3").success
    assert not gateway.refund(auth.transaction_id, Decimal("60.01"), "r1").success
    assert not gateway.refund("mock_txn_999999", Decimal("1.00"), "r2").success


def test_amounts_must_be_positive_decimals(gateway):
    with pytest.raises(TypeError):
        gateway.authorize(100.0, "INR", "tok_ok", "f")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        gateway.authorize(Decimal("0"), "INR", "tok_ok", "z")
