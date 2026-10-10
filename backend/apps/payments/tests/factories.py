"""factory-boy factories for payments."""

import itertools
from decimal import Decimal

import factory

from apps.accounts.tests.factories import BranchStaffFactory
from apps.bookings.tests.factories import BookingFactory
from apps.payments.models import (
    CardPayment,
    CashPayment,
    Invoice,
    InvoiceAdjustment,
    InvoiceLine,
    LedgerEntry,
    OnlinePayment,
    Payment,
)

# One counter for every Payment subclass factory: they share the payment table,
# and factory-boy keeps a separate sequence per factory class.
_payment_numbers = itertools.count(1)


class _PaymentFields(factory.django.DjangoModelFactory):
    transaction_id = factory.LazyFunction(lambda: f"TXN{next(_payment_numbers):010d}")
    amount = Decimal("1800.00")
    status = Payment.Status.SUCCEEDED
    booking = factory.SubFactory(BookingFactory)
    transaction_type = Payment.TransactionType.AUTHORIZE
    purpose = Payment.Purpose.RENTAL
    idempotency_key = factory.LazyAttribute(lambda o: f"idem-{o.transaction_id}")


class PaymentFactory(_PaymentFields):
    class Meta:
        model = Payment


class CardPaymentFactory(_PaymentFields):
    class Meta:
        model = CardPayment

    card_token = factory.Sequence(lambda n: f"tok_{n:012d}")
    card_brand = "Visa"
    gateway_reference = factory.Sequence(lambda n: f"pay_{n:012d}")


class CashPaymentFactory(_PaymentFields):
    class Meta:
        model = CashPayment

    received_by = factory.SubFactory(
        BranchStaffFactory, branch=factory.SelfAttribute("..booking.pickup_branch")
    )


class OnlinePaymentFactory(_PaymentFields):
    class Meta:
        model = OnlinePayment

    channel = OnlinePayment.Channel.UPI
    upi_id = "customer@okbank"
    gateway_reference = factory.Sequence(lambda n: f"pay_{n:012d}")


class InvoiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Invoice

    invoice_number = factory.Sequence(lambda n: f"INV-2026-{n:06d}")
    tax_amount = Decimal("324.00")
    total_amount = Decimal("2124.00")
    booking = factory.SubFactory(BookingFactory)
    agency_name = "Test Agency"


class InvoiceLineFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = InvoiceLine

    invoice = factory.SubFactory(InvoiceFactory)
    line_type = InvoiceLine.LineType.RENTAL
    description = "Rental, 1 day"
    quantity = Decimal("1.00")
    unit_price = Decimal("1800.00")
    amount = Decimal("1800.00")


class InvoiceAdjustmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = InvoiceAdjustment

    adjustment_number = factory.Sequence(lambda n: f"CN-2026-{n:06d}")
    invoice = factory.SubFactory(InvoiceFactory)
    adjustment_type = InvoiceAdjustment.AdjustmentType.CREDIT_NOTE
    reason = "Charged for an extra hour in error."
    amount = Decimal("150.00")


class LedgerEntryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LedgerEntry

    booking = factory.SubFactory(BookingFactory)
    entry_type = LedgerEntry.EntryType.CHARGE
    amount = Decimal("1800.00")
    method = LedgerEntry.Method.CARD
