"""Payments business logic: Pay.Authorize, Pay.Invoice and Pay.Ledger.

Exp 4 sequence 1: Payment.authorize() and Invoice.generate_invoice().

Decision (team, 11 Oct 2026): the rental amount and the security deposit are
authorised in ONE gateway call, so a decline leaves nothing to reverse. The
authorisation is recorded as two Payment rows, purpose Rental and Security
Deposit (Pay.Deposit keeps the deposit apart), sharing the gateway reference.
Invoice numbers are INV-YYYY-NNNNNN, sequential per year of issue (IST).

CO-2: only the gateway's token reaches VRMS; it is stored on CardPayment and
never copied into an audit entry (apps.core.audit.SECRET_FIELDS).

Owner: Rohan (WBS 1.4.3).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from apps.bookings.numbering import next_in_sequence
from apps.core.audit import record_audit, snapshot
from integrations.payment_gateway import get_payment_gateway

from .models import CardPayment, Invoice, InvoiceLine, LedgerEntry, Payment

ZERO = Decimal("0.00")


def _transaction_id() -> str:
    """Appendix A transaction id: ours, shown to the customer (Pay.Confirm.OK)."""
    return f"TXN-{uuid.uuid4().hex[:20].upper()}"


@dataclass(frozen=True)
class AuthorizationResult:
    success: bool
    message: str
    rental: CardPayment | None  # None when the rental amount is zero (a full discount)
    deposit: CardPayment

    @property
    def transaction_id(self) -> str:
        return (self.rental or self.deposit).transaction_id


def previous_authorization(booking, idempotency_key: str) -> AuthorizationResult | None:
    """Pay.Idempotent: the same key returns the first attempt's outcome, never a second charge."""
    rows = {
        payment.purpose: payment
        for payment in CardPayment.objects.filter(
            booking=booking, idempotency_key__startswith=f"{idempotency_key}:"
        )
    }
    deposit = rows.get(Payment.Purpose.SECURITY_DEPOSIT)
    if deposit is None:
        return None
    success = deposit.status == Payment.Status.SUCCEEDED
    return AuthorizationResult(
        success, deposit.failure_reason, rows.get(Payment.Purpose.RENTAL), deposit
    )


def authorize(
    booking,
    *,
    rental_amount: Decimal,
    deposit_amount: Decimal,
    payment_token: str,
    idempotency_key: str,
    actor,
    request=None,
) -> AuthorizationResult:
    """Exp 3 Payment.authorize(): one gateway hold for rental + deposit (SI-1.1, Pay.Authorize)."""
    previous = previous_authorization(booking, idempotency_key)
    if previous is not None:
        return previous

    response = get_payment_gateway().authorize(
        amount=rental_amount + deposit_amount,
        currency=settings.CURRENCY,
        payment_token=payment_token,
        idempotency_key=idempotency_key,
    )
    status = Payment.Status.SUCCEEDED if response.success else Payment.Status.FAILED
    reason = "" if response.success else (response.message or "The payment was declined.")[:255]

    def row(purpose: str, amount: Decimal) -> CardPayment:
        payment = CardPayment.objects.create(
            transaction_id=_transaction_id(),
            amount=amount,
            status=status,
            booking=booking,
            transaction_type=Payment.TransactionType.AUTHORIZE,
            purpose=purpose,
            idempotency_key=f"{idempotency_key}:{purpose}",
            gateway_reference=response.transaction_id,
            initiated_by=actor,
            failure_reason=reason,
            card_token=payment_token,
            card_brand="",  # the sandbox gateway reports no brand
        )
        record_audit(
            actor,
            "Payment Authorized" if response.success else "Payment Declined",
            payment,
            after=snapshot(payment),  # card_token is never copied (SECRET_FIELDS)
            request=request,
        )
        return payment

    rental = row(Payment.Purpose.RENTAL, rental_amount) if rental_amount > 0 else None
    deposit = row(Payment.Purpose.SECURITY_DEPOSIT, deposit_amount)
    return AuthorizationResult(response.success, reason, rental, deposit)


def record_booking_ledger(
    booking, auth: AuthorizationResult, *, actor, request=None
) -> list[LedgerEntry]:
    """Pay.Ledger: the rental charge and the deposit hold, each with its payment and reference."""
    entries = []
    if auth.rental is not None:
        entries.append((LedgerEntry.EntryType.CHARGE, auth.rental, "Rental charge (Book.Done)"))
    entries.append(
        (LedgerEntry.EntryType.DEPOSIT_HOLD, auth.deposit, "Security deposit held (BR-3)")
    )
    created = [
        LedgerEntry.objects.create(
            booking=booking,
            entry_type=entry_type,
            amount=payment.amount,
            method=LedgerEntry.Method.CARD,
            payment=payment,
            gateway_reference=payment.gateway_reference,
            initiated_by=actor,
            note=note,
        )
        for entry_type, payment, note in entries
    ]
    record_audit(
        actor,
        "Ledger Entries Recorded",
        booking,
        after={
            "entries": [
                {"id": e.pk, "type": e.entry_type, "amount": str(e.amount)} for e in created
            ]
        },
        request=request,
    )
    return created


def _count(number: int, unit: str) -> str:
    return f"{number} {unit}{'' if number == 1 else 's'}"


def issue_invoice(booking, quote, *, actor, request=None) -> Invoice:
    """Exp 3 Invoice.generate_invoice() (Pay.Invoice): itemised, taxed, numbered, never edited.

    The deposit is not on the invoice: it is not revenue (Pay.Deposit).
    """
    year = timezone.localdate().year
    invoice = Invoice.objects.create(
        invoice_number=next_in_sequence(Invoice, "invoice_number", f"INV-{year}-", 6),
        tax_amount=quote.tax_amount,
        total_amount=quote.total_payable,
        booking=booking,
        agency_name=settings.AGENCY_NAME,
        agency_tax_registration=settings.AGENCY_TAX_REGISTRATION,
        issued_by=actor,
    )
    lines = [
        InvoiceLine(
            invoice=invoice,
            line_type=InvoiceLine.LineType.RENTAL,
            description=f"Rental, {_count(quote.billing_count, quote.billing_unit)}",
            quantity=Decimal(quote.billing_count),
            unit_price=quote.unit_rate,
            amount=quote.base_charge,
        )
    ]
    lines += [
        InvoiceLine(
            invoice=invoice,
            line_type=InvoiceLine.LineType.ADD_ON,
            description=f"{line.name} x{line.quantity}, {_count(line.days, 'day')}",
            quantity=Decimal(line.quantity * line.days),
            unit_price=line.daily_rate,
            amount=line.amount,
        )
        for line in quote.add_ons
    ]
    if quote.discount_amount > 0:
        lines.append(
            InvoiceLine(
                invoice=invoice,
                line_type=InvoiceLine.LineType.DISCOUNT,
                description=f"Discount {quote.discount_code}",
                quantity=Decimal("1"),
                unit_price=-quote.discount_amount,
                amount=-quote.discount_amount,
            )
        )
    for line in lines:
        line.save()
    record_audit(actor, "Invoice Issued", invoice, after=snapshot(invoice), request=request)
    return invoice


def tax_rate_of(invoice: Invoice) -> Decimal:
    """The rate the invoice was taxed at, from its own figures (never today's setting)."""
    taxable = invoice.total_amount - invoice.tax_amount
    if taxable <= 0:
        return ZERO
    return (invoice.tax_amount * 100 / taxable).quantize(Decimal("0.01"))
