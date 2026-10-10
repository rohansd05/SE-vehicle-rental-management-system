"""Payments services and the invoice PDF (Pay.Authorize, Pay.Invoice, Pay.Ledger, Pay.Deposit)."""

from decimal import Decimal

import pytest

from apps.bookings.numbering import SequenceExhaustedError, next_in_sequence
from apps.bookings.tests.factories import BookingFactory
from apps.core.models import AuditLog
from apps.payments import services
from apps.payments.models import CardPayment, Invoice
from apps.payments.pdf import render_invoice_pdf
from apps.payments.tests.factories import InvoiceFactory, InvoiceLineFactory

pytestmark = pytest.mark.django_db


def test_no_previous_authorisation_for_a_new_key():
    assert services.previous_authorization(BookingFactory(), "fresh-key") is None


def test_the_token_is_never_copied_into_the_audit_log():
    """CO-2."""
    booking = BookingFactory()
    services.authorize(
        booking,
        rental_amount=Decimal("100.00"),
        deposit_amount=Decimal("5000.00"),
        payment_token="tok_secret_value",
        idempotency_key="audit-key-1",
        actor=None,
    )
    assert CardPayment.objects.filter(booking=booking).count() == 2
    for entry in AuditLog.objects.filter(action="Payment Authorized"):
        assert "tok_secret_value" not in str(entry.after)


def test_the_tax_rate_is_read_back_from_the_invoice():
    invoice = InvoiceFactory(tax_amount=Decimal("648.00"), total_amount=Decimal("4248.00"))
    assert services.tax_rate_of(invoice) == Decimal("18.00")
    zero = InvoiceFactory(tax_amount=Decimal("0.00"), total_amount=Decimal("0.00"))
    assert services.tax_rate_of(zero) == Decimal("0.00")


def test_the_pdf_renders_the_issued_invoice():
    invoice = InvoiceFactory()
    InvoiceLineFactory(invoice=invoice)
    pdf = render_invoice_pdf(Invoice.objects.get(pk=invoice.pk))
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_numbers_run_in_sequence_inside_a_transaction():
    from django.db import transaction

    with transaction.atomic():
        assert next_in_sequence(Invoice, "invoice_number", "INV-2099-", 6) == "INV-2099-000001"
        InvoiceFactory(invoice_number="INV-2099-000041")
        assert next_in_sequence(Invoice, "invoice_number", "INV-2099-", 6) == "INV-2099-000042"


def test_a_sequence_needs_a_transaction():
    with pytest.raises(RuntimeError):
        # pytest-django wraps tests in a transaction; leave it to see the guard.
        from django.db import connection

        connection.in_atomic_block, saved = False, connection.in_atomic_block
        try:
            next_in_sequence(Invoice, "invoice_number", "INV-2099-", 6)
        finally:
            connection.in_atomic_block = saved


def test_an_exhausted_sequence_is_refused():
    from django.db import transaction

    InvoiceFactory(invoice_number="INV-2099-9")
    with transaction.atomic(), pytest.raises(SequenceExhaustedError):
        next_in_sequence(Invoice, "invoice_number", "INV-2099-", 1)
