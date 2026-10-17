"""SI-1.2, Exp 3 Payment.capture(): capture_charges() and its ledger (Pay.Ledger)."""

from decimal import Decimal

import pytest

from apps.core.models import AuditLog
from apps.payments import services
from apps.payments.models import LedgerEntry, Payment
from apps.payments.tests.conftest import cash_confirmed, deposit_of, held, original
from integrations.payment_gateway.interface import GatewayResponse
from integrations.payment_gateway.mock import MockPaymentGateway

pytestmark = pytest.mark.django_db

E = LedgerEntry.EntryType
LINES = [
    services.ChargeLine("Excess kilometres, 40 km at 10.00 (BR-11)", Decimal("400.00")),
    services.ChargeLine("Fuel shortfall (BR-12)", Decimal("250.50")),
]


def captures(booking):
    return Payment.objects.filter(booking=booking, transaction_type=Payment.TransactionType.CAPTURE)


def test_each_charge_is_recorded_and_the_authorisation_is_captured(paid, staff):
    entries = services.capture_charges(paid, LINES, staff, idempotency_key="capture-0001")

    assert [(e.entry_type, e.amount) for e in entries] == [
        (E.CHARGE, Decimal("400.00")),
        (E.CHARGE, Decimal("250.50")),
        (E.CAPTURE, Decimal("4248.00")),  # the rental
        (E.CAPTURE, Decimal("5000.00")),  # the deposit, refunded later with refund_deposit()
    ]
    assert {e.method for e in entries} == {"Card"}
    assert all(e.initiated_by == staff for e in entries)
    rental, deposit = original(paid), deposit_of(paid)
    assert services.captured_amount(rental) == rental.amount
    assert services.captured_amount(deposit) == deposit.amount
    capture = captures(paid).get(original_payment=rental)
    assert capture.gateway_reference == rental.gateway_reference
    assert entries[2].payment == capture
    assert AuditLog.objects.filter(action="Payment Captured").count() == 2


def test_the_same_key_returns_the_first_capture_and_never_charges_twice(paid, staff):
    first = services.capture_charges(paid, LINES, staff, idempotency_key="capture-0001")
    again = services.capture_charges(paid, LINES, staff, idempotency_key="capture-0001")
    assert [e.pk for e in again] == [e.pk for e in first]
    assert captures(paid).count() == 2
    assert LedgerEntry.objects.filter(booking=paid, entry_type=E.CHARGE).count() == 3  # 1 + 2


def test_another_key_after_a_capture_is_refused(paid, staff):
    services.capture_charges(paid, [], staff, idempotency_key="capture-0001")
    with pytest.raises(services.PaymentError) as refused:
        services.capture_charges(paid, LINES, staff, idempotency_key="capture-0002")
    assert refused.value.code == "already_captured"
    assert refused.value.status == 409


def test_a_booking_that_was_never_paid_has_nothing_to_capture(
    customer, car, pickup, return_, staff
):
    booking = held(customer, car, pickup, return_)
    with pytest.raises(services.PaymentError) as refused:
        services.capture_charges(booking, [], staff)
    assert refused.value.code == "not_paid"


def test_a_charge_needs_a_description_and_a_positive_decimal_amount(paid, staff):
    with pytest.raises(services.PaymentError) as zero:
        services.capture_charges(paid, [services.ChargeLine("Damage", Decimal("0"))], staff)
    assert zero.value.code == "invalid_amount"
    with pytest.raises(TypeError):  # CO-6: never float
        services.capture_charges(paid, [services.ChargeLine("Damage", 10.5)], staff)
    with pytest.raises(services.PaymentError) as blank:
        services.capture_charges(paid, [services.ChargeLine(" ", Decimal("1.00"))], staff)
    assert blank.value.code == "invalid_line"
    assert not LedgerEntry.objects.filter(booking=paid, entry_type=E.CAPTURE).exists()


def test_cash_is_already_in_hand_so_only_the_charges_are_recorded(
    customer, car, pickup, return_, staff
):
    booking = cash_confirmed(customer, car, pickup, return_, staff)
    before = captures(booking).count()
    entries = services.capture_charges(booking, LINES[:1], staff, idempotency_key="capture-cash")
    assert [(e.entry_type, e.method) for e in entries] == [(E.CHARGE, "Cash")]
    assert captures(booking).count() == before


def test_a_refused_capture_changes_nothing(paid, staff, monkeypatch):
    monkeypatch.setattr(
        MockPaymentGateway,
        "capture",
        lambda self, txn, amount, key: GatewayResponse(False, txn, amount, "Expired."),
    )
    with pytest.raises(services.PaymentError) as refused:
        services.capture_charges(paid, LINES, staff, idempotency_key="capture-0001")
    assert refused.value.code == "capture_failed"
    assert refused.value.status == 402
    assert not LedgerEntry.objects.filter(
        booking=paid, idempotency_key__startswith="charges:"
    ).exists()
