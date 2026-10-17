"""Payments business logic (SRS 3.4 Pay.*; SI-1; Exp 4 sequences 1 and 2; UC 13).

Public functions (described for callers in docs/payments-api.md):

- authorize(), record_cash(), record_booking_ledger(), issue_invoice():
  Book Vehicle (Exp 4 sequence 1, Payment.authorize(), Invoice.generate_invoice()).
- capture_charges(), refund_payment(), refund_deposit(): settlement at the
  end of a rental or on cancellation (SI-1.2, SI-1.3, Pay.Refund, BR-14);
  Payment.capture() and Payment.refund() of Exp 3.
- approve_refund(), reject_refund(), pay_out_cash_refund(): UC 13 Approve Refund.
- record_due(), pay_due(): Pay.Dues, BR-4.
- issue_credit_note(): Pay.Invoice corrections.
- handle_notification(): SI-1.4 gateway notifications.

Decision (team, 11 Oct 2026): the rental amount and the security deposit are
authorised in ONE gateway call, so a decline leaves nothing to reverse. The
authorisation is recorded as two Payment rows, purpose Rental and Security
Deposit (Pay.Deposit keeps the deposit apart), sharing the gateway reference.
Invoice numbers are INV-YYYY-NNNNNN, credit notes CN-YYYY-NNNNNN, both
sequential per year of issue (IST).

A capture or refund is a Payment row whose original_payment is the
authorisation (or the cash payment) it settles, so each refund goes back to
the original instrument (Pay.Refund). Money is refunded only once captured:
an authorisation that was never captured is captured first (SI-1.2, SI-1.3).

CO-2: only the gateway's token reaches VRMS; it is stored on CardPayment and
never copied into an audit entry (apps.core.audit.SECRET_FIELDS).

Owner: Rohan (WBS 1.4.3).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import Customer, User
from apps.bookings.numbering import next_in_sequence
from apps.core.audit import record_audit, snapshot
from apps.notifications.services import queue_email
from integrations.payment_gateway import get_payment_gateway

from .models import (
    CardPayment,
    CashPayment,
    GatewayNotification,
    Invoice,
    InvoiceAdjustment,
    InvoiceLine,
    LedgerEntry,
    OnlinePayment,
    Payment,
    RefundRequest,
)

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
Type = Payment.TransactionType
Purpose = Payment.Purpose
RefundStatus = RefundRequest.Status
Adjustment = InvoiceAdjustment.AdjustmentType


class PaymentError(Exception):
    """A refusal the client can act on: `code` is stable, `status` is the HTTP status."""

    status = 400
    code = "invalid"

    def __init__(self, message: str, *, code: str | None = None, status: int | None = None):
        super().__init__(message)
        if code:
            self.code = code
        if status:
            self.status = status


def _transaction_id() -> str:
    """Appendix A transaction id: ours, shown to the customer (Pay.Confirm.OK)."""
    return f"TXN-{uuid.uuid4().hex[:20].upper()}"


def _money(amount) -> Decimal:
    if not isinstance(amount, Decimal):
        raise TypeError("Monetary amounts must be Decimal, never float (CO-6).")
    if amount <= 0:
        raise PaymentError("The amount must be more than zero.", code="invalid_amount")
    return amount.quantize(CENT)


# ─── Pay.Authorize and BR-9 cash (Book Vehicle) ───────────────────────────


@dataclass(frozen=True)
class AuthorizationResult:
    success: bool
    message: str
    rental: Payment | None  # None when the rental amount is zero (a full discount)
    # None for an extra rental charge with no deposit (Book.Modify.Price, Book.Extend).
    deposit: Payment | None

    @property
    def transaction_id(self) -> str:
        return (self.rental or self.deposit).transaction_id


def previous_authorization(booking, idempotency_key: str) -> AuthorizationResult | None:
    """Pay.Idempotent: the same key returns the first attempt's outcome, never a second charge."""
    rows = {
        payment.purpose: payment
        for payment in Payment.objects.filter(
            booking=booking,
            original_payment__isnull=True,
            idempotency_key__startswith=f"{idempotency_key}:",
        )
    }
    deposit = rows.get(Purpose.SECURITY_DEPOSIT)
    first = deposit or rows.get(Purpose.RENTAL)
    if first is None:
        return None
    success = first.status == Payment.Status.SUCCEEDED
    return AuthorizationResult(success, first.failure_reason, rows.get(Purpose.RENTAL), deposit)


def _instrument_row(channel: str, upi_id: str, payment_token: str, **fields) -> Payment:
    """Exp 3: an OnlinePayment for a D6 channel (UPI, net banking, wallet), else a CardPayment."""
    if channel:
        upi = upi_id if channel == OnlinePayment.Channel.UPI else ""
        return OnlinePayment.objects.create(channel=channel, upi_id=upi, **fields)
    return CardPayment.objects.create(card_token=payment_token, card_brand="", **fields)


def authorize(
    booking,
    *,
    rental_amount: Decimal,
    deposit_amount: Decimal,
    payment_token: str,
    idempotency_key: str,
    actor,
    request=None,
    channel: str = "",
    upi_id: str = "",
) -> AuthorizationResult:
    """Exp 3 Payment.authorize(): one gateway hold for rental + deposit (SI-1.1, Pay.Authorize).

    Pay.Method: a card (`payment_token` from the hosted fields) or, with
    `channel`, an on-line transfer or wallet (D6). A `deposit_amount` of zero
    authorises an extra rental charge alone (Book.Modify.Price, Book.Extend).
    """
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

    def row(purpose: str, amount: Decimal) -> Payment:
        payment = _instrument_row(
            channel,
            upi_id,
            payment_token,
            transaction_id=_transaction_id(),
            amount=amount,
            status=status,
            booking=booking,
            transaction_type=Type.AUTHORIZE,
            purpose=purpose,
            idempotency_key=f"{idempotency_key}:{purpose}",
            gateway_reference=response.transaction_id,
            initiated_by=actor,
            failure_reason=reason,
        )
        record_audit(
            actor,
            "Payment Authorized" if response.success else "Payment Declined",
            payment,
            after=snapshot(payment),  # card_token is never copied (SECRET_FIELDS)
            request=request,
        )
        return payment

    rental = row(Purpose.RENTAL, rental_amount) if rental_amount > 0 else None
    deposit = row(Purpose.SECURITY_DEPOSIT, deposit_amount) if deposit_amount > 0 else None
    return AuthorizationResult(response.success, reason, rental, deposit)


def record_cash(
    booking,
    *,
    staff,
    rental_amount: Decimal,
    deposit_amount: Decimal,
    idempotency_key: str,
    request=None,
) -> AuthorizationResult:
    """BR-9: cash received at the branch, recorded by the named staff member `staff` (BranchStaff).

    Cash in hand is already captured, so the rows are Capture transactions.
    """
    previous = previous_authorization(booking, idempotency_key)
    if previous is not None:
        return previous

    def row(purpose: str, amount: Decimal) -> CashPayment:
        payment = CashPayment.objects.create(
            transaction_id=_transaction_id(),
            amount=amount,
            status=Payment.Status.SUCCEEDED,
            booking=booking,
            transaction_type=Type.CAPTURE,
            purpose=purpose,
            idempotency_key=f"{idempotency_key}:{purpose}",
            initiated_by=staff.user,
            received_by=staff,
        )
        record_audit(
            staff.user, "Cash Payment Recorded", payment, after=snapshot(payment), request=request
        )
        return payment

    rental = row(Purpose.RENTAL, rental_amount) if rental_amount > 0 else None
    deposit = row(Purpose.SECURITY_DEPOSIT, deposit_amount)
    return AuthorizationResult(True, "", rental, deposit)


def record_booking_ledger(
    booking,
    auth: AuthorizationResult,
    *,
    actor,
    request=None,
    note: str = "Rental charge (Book.Done)",
) -> list[LedgerEntry]:
    """Pay.Ledger: the rental charge and the deposit hold (and, for cash, its capture)."""
    entries = []
    if auth.rental is not None:
        entries.append((LedgerEntry.EntryType.CHARGE, auth.rental, note))
    if auth.deposit is not None:
        entries.append(
            (LedgerEntry.EntryType.DEPOSIT_HOLD, auth.deposit, "Security deposit held (BR-3)")
        )
    for payment in (auth.rental, auth.deposit):
        if payment is not None and payment.transaction_type == Type.CAPTURE:
            entries.append((LedgerEntry.EntryType.CAPTURE, payment, "Cash received (BR-9)"))
    created = [
        LedgerEntry.objects.create(
            booking=booking,
            entry_type=entry_type,
            amount=payment.amount,
            method=payment.method,
            payment=payment,
            gateway_reference=payment.gateway_reference,
            initiated_by=actor,
            note=note,
        )
        for entry_type, payment, note in entries
    ]
    _audit_entries(actor, booking, created, request)
    return created


def _audit_entries(actor, booking, entries: list[LedgerEntry], request) -> None:
    record_audit(
        actor,
        "Ledger Entries Recorded",
        booking,
        after={
            "entries": [
                {"id": e.pk, "type": e.entry_type, "amount": str(e.amount)} for e in entries
            ]
        },
        request=request,
    )


# ─── Invoices and credit notes (Pay.Invoice) ──────────────────────────────


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


def issue_credit_note(
    invoice: Invoice, amount: Decimal, reason: str, *, issued_by, request=None
) -> InvoiceAdjustment:
    """Pay.Invoice: an issued invoice is never modified; a credit note references it.

    `amount` includes tax; the tax part is taken at the invoice's own rate.
    The credit notes on one invoice never exceed its total plus its debit notes.
    """
    amount = _money(amount)

    def adjusted(kind: str) -> Decimal:
        return _total(invoice.adjustments.filter(adjustment_type=kind))

    if adjusted(Adjustment.CREDIT_NOTE) + amount > invoice.total_amount + adjusted(
        Adjustment.DEBIT_NOTE
    ):
        raise PaymentError(
            "A credit note cannot exceed what is left of the invoice.", code="exceeds_invoice"
        )
    return _adjust(invoice, Adjustment.CREDIT_NOTE, amount, reason, issued_by, request)


def issue_debit_note(
    invoice: Invoice, amount: Decimal, reason: str, *, issued_by, request=None
) -> InvoiceAdjustment:
    """Pay.Invoice: an extra charge after issue (Book.Modify.Price, Book.Extend) is a debit
    note that references the invoice, never an edit of it. `amount` includes tax."""
    return _adjust(invoice, Adjustment.DEBIT_NOTE, _money(amount), reason, issued_by, request)


def _adjust(invoice, kind: str, amount: Decimal, reason: str, issued_by, request):
    rate = tax_rate_of(invoice)
    prefix = "CN" if kind == Adjustment.CREDIT_NOTE else "DN"
    note = InvoiceAdjustment.objects.create(
        adjustment_number=next_in_sequence(
            InvoiceAdjustment, "adjustment_number", f"{prefix}-{timezone.localdate().year}-", 6
        ),
        invoice=invoice,
        adjustment_type=kind,
        reason=reason,
        amount=amount,
        tax_amount=(amount * rate / (100 + rate)).quantize(CENT),
        issued_by=issued_by,
    )
    record_audit(issued_by, f"{kind} Issued", note, after=snapshot(note), request=request)
    return note


# ─── Capture (SI-1.2, Exp 3 Payment.capture()) ────────────────────────────


@dataclass(frozen=True)
class ChargeLine:
    """A usage-based charge settled at the end of a rental (Return.Charges, BR-10 to BR-12)."""

    description: str
    amount: Decimal


def _total(queryset) -> Decimal:
    return queryset.aggregate(total=Sum("amount"))["total"] or ZERO


def captured_amount(payment: Payment) -> Decimal:
    """Money actually taken for `payment`: cash in hand, or its succeeded captures."""
    if payment.transaction_type == Type.CAPTURE:
        return payment.amount
    return _total(
        payment.follow_ups.filter(transaction_type=Type.CAPTURE, status=Payment.Status.SUCCEEDED)
    )


def refunded_amount(payment: Payment) -> Decimal:
    return _total(
        payment.follow_ups.filter(transaction_type=Type.REFUND, status=Payment.Status.SUCCEEDED)
    )


def refundable_amount(payment: Payment) -> Decimal:
    """What may still be refunded: the payment less refunds issued or waiting (Pay.Refund)."""
    waiting = _total(
        payment.refund_requests.filter(
            status__in=[RefundStatus.PENDING_APPROVAL, RefundStatus.APPROVED]
        )
    )
    return payment.amount - refunded_amount(payment) - waiting


def _booking_originals(booking) -> list[Payment]:
    """The succeeded rental and deposit payments a booking was confirmed with."""
    return list(
        Payment.objects.filter(
            booking=booking,
            original_payment__isnull=True,
            status=Payment.Status.SUCCEEDED,
            purpose__in=[Purpose.RENTAL, Purpose.SECURITY_DEPOSIT],
        ).order_by("pk")
    )


def _capture(payment: Payment, amount: Decimal, *, actor, key: str, request) -> LedgerEntry:
    """One gateway capture of `payment` and its ledger entry (Pay.Ledger "capture").

    shortcut: a refused capture raises and rolls the caller back, so the
    refusal is not stored; keep the failed row if the team wants it audited.
    """
    response = get_payment_gateway().capture(payment.gateway_reference, amount, key)
    if not response.success:
        raise PaymentError(
            f"The payment gateway refused the capture: {response.message}",
            code="capture_failed",
            status=402,
        )
    row = Payment.objects.create(
        transaction_id=_transaction_id(),
        amount=amount,
        status=Payment.Status.SUCCEEDED,
        booking=payment.booking,
        transaction_type=Type.CAPTURE,
        purpose=payment.purpose,
        idempotency_key=key,
        gateway_reference=payment.gateway_reference,
        initiated_by=actor,
        original_payment=payment,
    )
    record_audit(actor, "Payment Captured", row, after=snapshot(row), request=request)
    return LedgerEntry.objects.create(
        booking=payment.booking,
        entry_type=LedgerEntry.EntryType.CAPTURE,
        amount=amount,
        method=payment.method,
        payment=row,
        gateway_reference=row.gateway_reference,
        initiated_by=actor,
        note=f"{payment.purpose} captured (SI-1.2)",
        idempotency_key=key,
    )


def capture_charges(
    booking,
    lines: Sequence[ChargeLine],
    initiated_by,
    *,
    idempotency_key: str | None = None,
    request=None,
) -> list[LedgerEntry]:
    """SI-1.2: when the final charges are known, capture what was authorised.

    Records a Charge entry for each line and captures every uncaptured part
    of the booking's rental and deposit authorisation (cash is already in
    hand). The deposit balance is then given back with refund_deposit(), and
    charges above the deposit become a due with record_due() (Return.Settle).
    Runs once per booking: the same key returns the first run's entries; a
    different key is refused (Pay.Idempotent).
    """
    from apps.bookings.models import Booking

    key = idempotency_key or uuid.uuid4().hex
    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(pk=booking.pk)
        previous = list(
            LedgerEntry.objects.filter(
                booking=booking, idempotency_key__startswith=f"charges:{key}:"
            )
        )
        if previous:
            return previous
        if LedgerEntry.objects.filter(
            booking=booking, idempotency_key__startswith="charges:"
        ).exists():
            raise PaymentError(
                "The charges of this booking have already been captured.",
                code="already_captured",
                status=409,
            )
        originals = _booking_originals(booking)
        if not originals:
            raise PaymentError(
                "This booking has no payment to capture.", code="not_paid", status=409
            )
        numbers = iter(range(1, 10_000))
        entries = []
        for line in lines:
            if not line.description.strip():
                raise PaymentError("Every charge needs a description.", code="invalid_line")
            entries.append(
                LedgerEntry.objects.create(
                    booking=booking,
                    entry_type=LedgerEntry.EntryType.CHARGE,
                    amount=_money(line.amount),
                    method=originals[0].method,
                    initiated_by=initiated_by,
                    note=line.description.strip()[:255],
                    idempotency_key=f"charges:{key}:{next(numbers)}",
                )
            )
        for payment in originals:
            remaining = payment.amount - captured_amount(payment)
            if remaining > 0:
                entries.append(
                    _capture(
                        payment,
                        remaining,
                        actor=initiated_by,
                        key=f"charges:{key}:{next(numbers)}",
                        request=request,
                    )
                )
        _audit_entries(initiated_by, booking, entries, request)
    return entries


# ─── Refunds (SI-1.3, Pay.Refund, BR-14, UC 13) ───────────────────────────

REFUND_TRANSITIONS: dict[str, frozenset[str]] = {
    RefundStatus.PENDING_APPROVAL: frozenset(
        {RefundStatus.APPROVED, RefundStatus.ISSUED, RefundStatus.REJECTED, RefundStatus.FAILED}
    ),
    RefundStatus.APPROVED: frozenset({RefundStatus.ISSUED}),
    RefundStatus.ISSUED: frozenset({RefundStatus.FAILED}),  # SI-1.4: the gateway reports a failure
    RefundStatus.REJECTED: frozenset(),
    RefundStatus.FAILED: frozenset(),
}


def _set_refund_status(
    refund: RefundRequest, new: str, *, actor, reason: str, request, update_fields=()
) -> None:
    """Every refund status change is checked against REFUND_TRANSITIONS and audited (SE-10)."""
    current = refund.status
    if new not in REFUND_TRANSITIONS[current]:
        raise PaymentError(
            f"A refund cannot move from {current} to {new}.", code="invalid_state", status=409
        )
    refund.status = new
    refund.save(update_fields=["status", "updated_at", *update_fields])
    record_audit(
        actor,
        "Refund Status Changed",
        refund,
        before={"status": current},
        after={"status": new, "reason": reason},
        request=request,
    )


def _ensure_captured(payment: Payment, amount: Decimal, *, actor, key: str, request) -> None:
    """Refunds return captured money only (SI-1.3): capture the shortfall first."""
    available = captured_amount(payment) - refunded_amount(payment)
    if available < amount:
        _capture(payment, amount - available, actor=actor, key=key, request=request)


def _staff_profile(user):
    if user is not None and getattr(user, "role", None) == User.Role.BRANCH_STAFF:
        return getattr(user, "branch_staff", None)
    return None


def _notify_customer(refund: RefundRequest, template: str, **extra) -> None:
    """Notify.*: refund status changes reach the customer by e-mail, through Celery."""
    booking = refund.original_payment.booking
    queue_email(
        booking.customer.user,
        template,
        {
            "name": booking.customer.user.name,
            "booking": booking.booking_reference,
            "amount": f"{settings.CURRENCY} {refund.amount:,.2f}",
            **extra,
        },
        booking=booking,
    )


def _issue(refund: RefundRequest, *, actor, request) -> None:
    """Pay.Refund: to the original instrument, or as cash paid out by a named staff member."""
    payment = refund.original_payment
    key = refund.idempotency_key
    fields = {
        "transaction_id": _transaction_id(),
        "amount": refund.amount,
        "status": Payment.Status.SUCCEEDED,
        "booking": payment.booking,
        "transaction_type": Type.REFUND,
        "purpose": payment.purpose,
        "idempotency_key": f"{key}:refund",
        "initiated_by": actor,
        "original_payment": payment,
    }
    if payment.method == "Cash":
        staff = _staff_profile(actor)
        if staff is None:
            _set_refund_status(
                refund,
                RefundStatus.APPROVED,
                actor=actor,
                reason="To be paid out in cash at the branch by a named staff member (Pay.Refund).",
                request=request,
            )
            return
        # The staff member pays the cash out with the customer present, who acknowledges it.
        row = CashPayment.objects.create(
            **fields, received_by=staff, customer_acknowledged_at=timezone.now()
        )
    else:
        _ensure_captured(payment, refund.amount, actor=actor, key=f"{key}:capture", request=request)
        response = get_payment_gateway().refund(
            payment.gateway_reference, refund.amount, f"{key}:refund"
        )
        if not response.success:
            refund.failure_reason = (response.message or "The gateway refused the refund.")[:255]
            _set_refund_status(
                refund,
                RefundStatus.FAILED,
                actor=actor,
                reason=refund.failure_reason,
                request=request,
                update_fields=("failure_reason",),
            )
            return
        row = Payment.objects.create(**fields, gateway_reference=response.transaction_id)
    record_audit(actor, "Payment Refunded", row, after=snapshot(row), request=request)
    refund.refund = row
    _set_refund_status(
        refund,
        RefundStatus.ISSUED,
        actor=actor,
        reason=f"Refund issued, transaction {row.transaction_id}.",
        request=request,
        update_fields=("refund",),
    )
    is_deposit = payment.purpose == Purpose.SECURITY_DEPOSIT
    entry = LedgerEntry.objects.create(
        booking=payment.booking,
        entry_type=LedgerEntry.EntryType.DEPOSIT_RELEASE
        if is_deposit
        else LedgerEntry.EntryType.REFUND,
        amount=refund.amount,
        method=payment.method,
        payment=row,
        gateway_reference=row.gateway_reference,
        initiated_by=actor,
        note=refund.reason[:255],
    )
    _audit_entries(actor, payment.booking, [entry], request)
    invoice = getattr(payment.booking, "invoice", None)
    if not is_deposit and invoice is not None:  # the deposit is never on the invoice
        issue_credit_note(invoice, refund.amount, refund.reason, issued_by=actor, request=request)
    due_by = f" It reaches you by {refund.refund_due_by:%d %b %Y}." if refund.refund_due_by else ""
    _notify_customer(refund, "refund_issued", due_by=due_by)


def refund_payment(
    payment: Payment,
    amount: Decimal,
    reason: str,
    initiated_by,
    *,
    idempotency_key: str | None = None,
    refund_due_by: date | None = None,
    request=None,
) -> RefundRequest:
    """Exp 3 Payment.refund() (Pay.Refund, SI-1.3): refund `amount` of `payment` to its instrument.

    UC 13: above REFUND_AUTO_APPROVAL_LIMIT the refund waits as Pending
    Approval for an Administrator; otherwise it is issued at once. A cash
    refund is paid out by `initiated_by` when that is a branch staff member,
    otherwise it waits as Approved for one. The same key returns the first
    request and never refunds twice (Pay.Idempotent).
    """
    key = idempotency_key or uuid.uuid4().hex
    amount = _money(amount)
    if not reason.strip():
        raise PaymentError("Give the reason for the refund.", code="reason_required")
    with transaction.atomic():
        existing = RefundRequest.objects.filter(idempotency_key=key).first()
        if existing is not None:
            if existing.original_payment_id != payment.pk or existing.amount != amount:
                raise PaymentError(
                    "This idempotency key was already used for another refund.",
                    code="idempotency_key_reused",
                    status=409,
                )
            return existing
        payment = Payment.objects.select_for_update().get(pk=payment.pk)  # one refund at a time
        if (
            payment.status != Payment.Status.SUCCEEDED
            or payment.original_payment_id is not None
            or payment.booking_id is None
        ):
            raise PaymentError(
                "Only a successful booking payment can be refunded.", code="not_refundable"
            )
        if amount > refundable_amount(payment):
            raise PaymentError(
                f"At most {settings.CURRENCY} {refundable_amount(payment)} of this payment can "
                "still be refunded.",
                code="exceeds_refundable",
            )
        refund = RefundRequest.objects.create(
            original_payment=payment,
            amount=amount,
            reason=reason.strip()[:255],
            status=RefundStatus.PENDING_APPROVAL,
            requested_by=initiated_by,
            refund_due_by=refund_due_by,
            idempotency_key=key,
        )
        record_audit(
            initiated_by, "Refund Requested", refund, after=snapshot(refund), request=request
        )
        if amount <= settings.REFUND_AUTO_APPROVAL_LIMIT:
            _issue(refund, actor=initiated_by, request=request)
    return refund


def add_working_days(start: date, days: int) -> date:
    """BR-14: `days` working days after `start`.

    shortcut: Monday to Friday only, no public holidays; add a holiday
    calendar if the team adopts one.
    """
    current = start
    while days > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days -= 1
    return current


def refund_deposit(
    booking, amount: Decimal, initiated_by, *, idempotency_key: str | None = None, request=None
) -> RefundRequest:
    """BR-14: refund the deposit balance to the original instrument within 7 working days.

    One deposit refund per booking: without a key, a second call returns the
    first refund (and refuses a different amount).
    """
    deposit = next(
        (p for p in _booking_originals(booking) if p.purpose == Purpose.SECURITY_DEPOSIT), None
    )
    if deposit is None:
        raise PaymentError(
            "This booking has no security deposit to refund.", code="not_paid", status=409
        )
    due_by = add_working_days(timezone.localdate(), settings.DEPOSIT_REFUND_WORKING_DAYS)
    return refund_payment(
        deposit,
        amount,
        "Security deposit balance (BR-14)",
        initiated_by,
        idempotency_key=idempotency_key or f"deposit-refund-{booking.pk}",
        refund_due_by=due_by,
        request=request,
    )


def _locked_refund(refund: RefundRequest) -> RefundRequest:
    return (
        RefundRequest.objects.select_for_update(of=("self",))
        .select_related("original_payment__booking__customer__user")
        .get(pk=refund.pk)
    )


def approve_refund(refund: RefundRequest, approver, *, request=None) -> RefundRequest:
    """UC 13 step 3: the Administrator approves; the refund is issued and the approver recorded."""
    if getattr(approver, "role", None) != User.Role.ADMINISTRATOR:
        raise PaymentError("Only an Administrator approves refunds.", code="forbidden", status=403)
    with transaction.atomic():
        refund = _locked_refund(refund)
        if refund.status != RefundStatus.PENDING_APPROVAL:
            raise PaymentError(
                "This refund is not waiting for approval.", code="not_pending", status=409
            )
        refund.decided_by = approver
        refund.decided_at = timezone.now()
        refund.save(update_fields=["decided_by", "decided_at", "updated_at"])
        record_audit(approver, "Refund Approved", refund, after=snapshot(refund), request=request)
        _issue(refund, actor=approver, request=request)
    return refund


def reject_refund(refund: RefundRequest, approver, reason: str, *, request=None) -> RefundRequest:
    """UC 13 extension 2a: the reason is recorded and the customer notified (Celery)."""
    if getattr(approver, "role", None) != User.Role.ADMINISTRATOR:
        raise PaymentError("Only an Administrator rejects refunds.", code="forbidden", status=403)
    if not reason.strip():
        raise PaymentError("Give the reason for rejecting the refund.", code="reason_required")
    with transaction.atomic():
        refund = _locked_refund(refund)
        if refund.status != RefundStatus.PENDING_APPROVAL:
            raise PaymentError(
                "This refund is not waiting for approval.", code="not_pending", status=409
            )
        refund.decided_by = approver
        refund.decided_at = timezone.now()
        refund.rejection_reason = reason.strip()
        _set_refund_status(
            refund,
            RefundStatus.REJECTED,
            actor=approver,
            reason=refund.rejection_reason,
            request=request,
            update_fields=("decided_by", "decided_at", "rejection_reason"),
        )
        _notify_customer(refund, "refund_rejected", reason=refund.rejection_reason)
    return refund


def pay_out_cash_refund(refund: RefundRequest, staff_user, *, request=None) -> RefundRequest:
    """Pay.Refund: an Approved cash refund paid out and acknowledged at the branch."""
    if _staff_profile(staff_user) is None:
        raise PaymentError(
            "A named branch staff member pays out cash.", code="forbidden", status=403
        )
    with transaction.atomic():
        refund = _locked_refund(refund)
        if refund.status != RefundStatus.APPROVED:
            raise PaymentError(
                "This refund is not waiting to be paid in cash.", code="invalid_state", status=409
            )
        _issue(refund, actor=staff_user, request=request)
    return refund


# ─── Dues (Pay.Dues, BR-4) ────────────────────────────────────────────────


def record_due(
    customer: Customer, amount: Decimal, reason: str, *, initiated_by=None, request=None
) -> Decimal:
    """Pay.Dues: add `amount` to the customer's due; BR-4 then blocks new bookings."""
    amount = _money(amount)
    if not reason.strip():
        raise PaymentError("Give the reason for the due.", code="reason_required")
    with transaction.atomic():
        locked = Customer.objects.select_for_update().get(pk=customer.pk)
        before = locked.outstanding_due
        locked.outstanding_due = before + amount
        locked.save(update_fields=["outstanding_due", "updated_at"])
        record_audit(
            initiated_by,
            "Due Recorded",
            locked,
            before={"outstanding_due": before},
            after={
                "outstanding_due": locked.outstanding_due,
                "amount": amount,
                "reason": reason.strip(),
            },
            request=request,
        )
    customer.outstanding_due = locked.outstanding_due
    return locked.outstanding_due


def pay_due(
    customer: Customer,
    *,
    payment_token: str,
    idempotency_key: str,
    channel: str = "",
    upi_id: str = "",
    request=None,
) -> Payment:
    """Pay.Dues: clear the whole due on-line; the BR-4 restriction lifts at once.

    The gateway authorises and captures the due in one go. The same key
    returns the first payment and never charges twice (Pay.Idempotent).
    """
    actor = customer.user
    key = f"{idempotency_key}:due"
    outcome: PaymentError | None = None
    with transaction.atomic():
        locked = Customer.objects.select_for_update().get(pk=customer.pk)
        previous = Payment.objects.filter(idempotency_key=key).first()
        if previous is not None:
            if previous.initiated_by_id != actor.pk:
                raise PaymentError(
                    "This idempotency key was already used.",
                    code="idempotency_key_reused",
                    status=409,
                )
            if previous.status != Payment.Status.SUCCEEDED:
                raise PaymentError(previous.failure_reason, code="payment_declined", status=402)
            return previous
        due = locked.outstanding_due
        if due <= 0:
            raise PaymentError("You have no outstanding due.", code="no_due", status=409)
        gateway = get_payment_gateway()
        response = gateway.authorize(due, settings.CURRENCY, payment_token, key)
        if response.success:
            captured = gateway.capture(response.transaction_id, due, f"{key}:capture")
            if not captured.success:
                response = captured
        status = Payment.Status.SUCCEEDED if response.success else Payment.Status.FAILED
        reason = "" if response.success else (response.message or "The payment was declined.")[:255]
        payment = _instrument_row(
            channel,
            upi_id,
            payment_token,
            transaction_id=_transaction_id(),
            amount=due,
            status=status,
            booking=None,
            transaction_type=Type.CAPTURE,
            purpose=Purpose.DUE,
            idempotency_key=key,
            gateway_reference=response.transaction_id,
            initiated_by=actor,
            failure_reason=reason,
        )
        record_audit(
            actor,
            "Due Paid" if response.success else "Due Payment Declined",
            payment,
            after=snapshot(payment),
            request=request,
        )
        if response.success:
            locked.outstanding_due = ZERO
            locked.save(update_fields=["outstanding_due", "updated_at"])
            record_audit(
                actor,
                "Due Cleared",
                locked,
                before={"outstanding_due": due},
                after={"outstanding_due": ZERO, "payment": payment.transaction_id},
                request=request,
            )
            customer.outstanding_due = ZERO
        else:
            outcome = PaymentError(
                f"Your payment was declined: {reason}", code="payment_declined", status=402
            )
    if outcome is not None:
        raise outcome  # after the commit, so the declined attempt stays recorded
    return payment


# ─── Gateway notifications (SI-1.4) ───────────────────────────────────────


def _refund_failed(reference: str, message: str, request) -> None:
    """A refund the gateway accepted has failed after all: reverse it, never edit the ledger."""
    row = Payment.objects.filter(
        gateway_reference=reference, transaction_type=Type.REFUND, status=Payment.Status.SUCCEEDED
    ).first()
    if row is None:
        return
    row.status = Payment.Status.FAILED
    row.failure_reason = message[:255]
    row.save(update_fields=["status", "failure_reason", "updated_at"])
    refund = RefundRequest.objects.filter(refund=row).first()
    if refund is not None:
        refund.failure_reason = row.failure_reason
        _set_refund_status(
            refund,
            RefundStatus.FAILED,
            actor=None,
            reason=row.failure_reason,
            request=request,
            update_fields=("failure_reason",),
        )
        _notify_customer(refund, "refund_failed")
    original = row.ledger_entries.first()
    entry = LedgerEntry.objects.create(
        booking=row.booking,
        entry_type=LedgerEntry.EntryType.ADJUSTMENT,
        amount=row.amount,
        method=row.method,
        payment=row,
        gateway_reference=reference,
        reference_entry=original,
        note="Reverses the refund: the gateway reported it failed (SI-1.4).",
    )
    _audit_entries(None, row.booking, [entry], request)


def handle_notification(
    payload: bytes, signature: str, *, request=None
) -> tuple[GatewayNotification, bool]:
    """SI-1.4: verify the signature, store the event once, act on it once (Pay.Idempotent).

    Returns the stored notification and whether it was new. A refund.failed
    event reverses the refund; every other event is stored for the record.
    """
    if not get_payment_gateway().verify_notification(payload, signature):
        raise PaymentError(
            "The notification signature is not valid.", code="invalid_signature", status=403
        )
    try:
        data = json.loads(payload)
        event_id, event_type = str(data["id"]), str(data["type"])
    except (ValueError, KeyError, TypeError) as exc:
        raise PaymentError("The notification is not valid JSON with an id and a type.") from exc
    reference = str(data.get("transaction_id", ""))
    with transaction.atomic():
        existing = GatewayNotification.objects.filter(event_id=event_id).first()
        if existing is not None:
            return existing, False
        try:
            with transaction.atomic():
                notification = GatewayNotification.objects.create(
                    event_id=event_id[:100],
                    event_type=event_type[:64],
                    gateway_reference=reference[:128],
                    payload=data,
                )
        except IntegrityError:  # the same event arriving twice at once
            return GatewayNotification.objects.get(event_id=event_id), False
        record_audit(
            None,
            "Gateway Notification Received",
            notification,
            after=snapshot(notification),
            request=request,
        )
        if event_type == "refund.failed":
            _refund_failed(reference, str(data.get("message", "The refund failed.")), request)
    return notification, True
