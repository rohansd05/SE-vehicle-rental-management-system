"""Payments models (Exp 3 Payment hierarchy; Pay.*; CO-2; D6)."""

from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.payments.models import CardPayment, OnlinePayment, Payment
from apps.payments.tests.factories import (
    CardPaymentFactory,
    CashPaymentFactory,
    InvoiceAdjustmentFactory,
    InvoiceFactory,
    InvoiceLineFactory,
    LedgerEntryFactory,
    OnlinePaymentFactory,
    PaymentFactory,
)

pytestmark = pytest.mark.django_db

FACTORIES = [
    PaymentFactory,
    CardPaymentFactory,
    CashPaymentFactory,
    OnlinePaymentFactory,
    InvoiceFactory,
    InvoiceLineFactory,
    InvoiceAdjustmentFactory,
    LedgerEntryFactory,
]


@pytest.mark.parametrize("factory_class", FACTORIES, ids=lambda f: f.__name__)
def test_factory_creates_a_valid_row(factory_class):
    instance = factory_class()
    instance.full_clean()
    assert instance.pk is not None
    assert str(instance)


def test_payment_status_values_match_the_handoff():
    assert Payment.Status.values == ["Initiated", "Processing", "Succeeded", "Failed", "Reversed"]


def test_card_payment_stores_no_card_data():
    """CO-2: no card number, expiry date or CVV column exists."""
    columns = {f.name.lower() for f in CardPayment._meta.get_fields()}
    for forbidden in ("number", "card_number", "pan", "expiry", "expiry_date", "cvv", "cvc"):
        assert forbidden not in columns


def test_online_payment_channels_are_d6():
    assert OnlinePayment.Channel.values == ["UPI", "Net Banking", "Wallet"]
    assert OnlinePaymentFactory(channel=OnlinePayment.Channel.WALLET, upi_id="").pk


def test_all_payment_types_share_the_payment_table():
    card, cash, online = CardPaymentFactory(), CashPaymentFactory(), OnlinePaymentFactory()
    assert Payment.objects.filter(pk__in=[card.pk, cash.pk, online.pk]).count() == 3


def test_idempotency_key_is_unique():
    """Pay.Idempotent: a duplicate submission cannot create a second payment."""
    payment = PaymentFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        PaymentFactory(idempotency_key=payment.idempotency_key)


def test_payment_amount_must_be_positive():
    with pytest.raises(IntegrityError), transaction.atomic():
        PaymentFactory(amount=Decimal("0.00"))


def test_cash_payment_is_recorded_by_branch_staff():
    """BR-9: cash is recorded by a named staff member."""
    payment = CashPaymentFactory()
    assert payment.received_by.branch == payment.booking.pickup_branch


def test_refund_refers_to_the_original_payment():
    original = CardPaymentFactory()
    refund = PaymentFactory(
        booking=original.booking,
        transaction_type=Payment.TransactionType.REFUND,
        original_payment=original,
        amount=Decimal("500.00"),
    )
    assert list(original.follow_ups.all()) == [refund]


def test_one_invoice_per_booking():
    invoice = InvoiceFactory()
    with pytest.raises(IntegrityError), transaction.atomic():
        InvoiceFactory(booking=invoice.booking)


def test_discount_lines_are_negative_and_charges_positive():
    InvoiceLineFactory(line_type="Discount", amount=Decimal("-100.00"))
    with pytest.raises(IntegrityError), transaction.atomic():
        InvoiceLineFactory(line_type="Discount", amount=Decimal("100.00"))
    with pytest.raises(IntegrityError), transaction.atomic():
        InvoiceLineFactory(line_type="Damage", amount=Decimal("-1.00"))


def test_credit_note_references_the_original_invoice():
    adjustment = InvoiceAdjustmentFactory()
    assert list(adjustment.invoice.adjustments.all()) == [adjustment]
