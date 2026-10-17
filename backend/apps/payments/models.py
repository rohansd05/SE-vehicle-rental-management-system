"""Payment, invoice and ledger models (SRS 3.4; Appendix A payment transaction).

Payment is a concrete base (Exp 3 «interface» Payment) with CardPayment,
CashPayment and OnlinePayment as multi-table children. Invoice, InvoiceLine,
InvoiceAdjustment and LedgerEntry are append-only (Pay.Invoice, Pay.Ledger):
model guards here, and a PostgreSQL trigger per table in the migration.

Owner: Rohan (WBS 1.4.3). Only the owner edits this file or its migrations.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import AppendOnlyModel, TimeStampedModel


def _money(**kwargs) -> models.DecimalField:
    return models.DecimalField(max_digits=12, decimal_places=2, **kwargs)


class Payment(TimeStampedModel):
    """Exp 3 Payment; Appendix A payment transaction."""

    class Status(models.TextChoices):
        INITIATED = "Initiated", "Initiated"
        PROCESSING = "Processing", "Processing"
        SUCCEEDED = "Succeeded", "Succeeded"
        FAILED = "Failed", "Failed"
        REVERSED = "Reversed", "Reversed"

    class TransactionType(models.TextChoices):
        """Appendix A "transaction type": the gateway calls of SI-1.1 to SI-1.3."""

        AUTHORIZE = "Authorize", "Authorize"
        CAPTURE = "Capture", "Capture"
        REFUND = "Refund", "Refund"

    class Purpose(models.TextChoices):
        RENTAL = "Rental", "Rental"
        SECURITY_DEPOSIT = "Security Deposit", "Security Deposit"  # Pay.Deposit: held apart
        DUE = "Due", "Due"  # Pay.Dues: clearing an outstanding due

    transaction_id = models.CharField(max_length=64, unique=True)
    amount = _money()
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.INITIATED)
    timestamp = models.DateTimeField(default=timezone.now)
    # Booking–Payment association (Exp 3: a booking is settled by 1..* payments).
    # Only a payment that clears a due (Pay.Dues) has no booking.
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
    )
    transaction_type = models.CharField(max_length=16, choices=TransactionType.choices)
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    # Pay.Idempotent: a repeated submission or notification reuses the key.
    idempotency_key = models.CharField(max_length=64, unique=True)
    gateway_reference = models.CharField(max_length=128, blank=True)  # SI-1.3, Appendix A
    initiated_by = models.ForeignKey(  # Appendix A "initiated by"
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments_initiated",
    )
    # Pay.Refund, BR-14: a capture or refund refers to the original authorisation.
    original_payment = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="follow_ups"
    )
    failure_reason = models.CharField(max_length=255, blank=True)  # SRS 3.4.2: shown to the user

    class Meta:
        ordering = ["-timestamp"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payments_amount_positive"),
            models.CheckConstraint(
                condition=Q(booking__isnull=False) | Q(purpose="Due"),
                name="payments_booking_unless_due",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.transaction_id} {self.transaction_type} {self.amount} ({self.status})"

    @property
    def method(self) -> str:
        """Pay.Ledger "method": Card, Online or Cash; a capture or refund takes its original's."""
        if isinstance(self, CashPayment) or hasattr(self, "cashpayment"):
            return "Cash"
        if isinstance(self, OnlinePayment) or hasattr(self, "onlinepayment"):
            return "Online"
        if not isinstance(self, CardPayment) and self.original_payment_id:
            return self.original_payment.method
        return "Card"


class CardPayment(Payment):
    """Exp 3 CardPayment.

    CO-2: only the gateway's token and the card brand are stored. A card
    number, expiry date or CVV never reaches VRMS.
    """

    card_token = models.CharField(max_length=255)
    card_brand = models.CharField(max_length=32)


class CashPayment(Payment):
    """Exp 3 CashPayment. BR-9: recorded by a named staff member."""

    received_by = models.ForeignKey(
        "accounts.BranchStaff", on_delete=models.PROTECT, related_name="cash_payments"
    )
    # Pay.Refund: a cash refund is acknowledged by the customer.
    customer_acknowledged_at = models.DateTimeField(null=True, blank=True)


class OnlinePayment(Payment):
    """Exp 3 OnlinePayment. D6: UPI, net banking and wallet are channels."""

    class Channel(models.TextChoices):
        UPI = "UPI", "UPI"
        NET_BANKING = "Net Banking", "Net Banking"
        WALLET = "Wallet", "Wallet"

    channel = models.CharField(max_length=16, choices=Channel.choices)
    upi_id = models.CharField(max_length=100, blank=True)  # Exp 3; set for UPI only


# ─── Invoices (append-only) ───────────────────────────────────────────────


class Invoice(AppendOnlyModel):
    """Exp 3 Invoice; Pay.Invoice. Booking ◆ Invoice (one per booking).

    Never modified once issued: a correction is an InvoiceAdjustment.
    The agency details are copied at issue so the invoice never changes.
    """

    invoice_number = models.CharField(max_length=32, unique=True)  # unique, sequential
    issue_date = models.DateTimeField(default=timezone.now)
    tax_amount = _money()
    total_amount = _money()
    booking = models.OneToOneField(
        "bookings.Booking", on_delete=models.PROTECT, related_name="invoice"
    )
    agency_name = models.CharField(max_length=150)  # D7: from settings.AGENCY_NAME
    agency_tax_registration = models.CharField(max_length=64, blank=True)  # Pay.Invoice
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invoices_issued",
    )

    class Meta:
        ordering = ["-issue_date"]
        constraints = [
            models.CheckConstraint(
                condition=Q(tax_amount__gte=0) & Q(total_amount__gte=0),
                name="payments_invoice_amounts_not_negative",
            ),
        ]

    def __str__(self) -> str:
        return self.invoice_number


class InvoiceLine(AppendOnlyModel):
    """Pay.Invoice: an itemised charge line (UI-4; Return.Charges)."""

    class LineType(models.TextChoices):
        RENTAL = "Rental", "Rental"  # BR-6 tariff for the period
        ADD_ON = "Add-on", "Add-on"  # BR-7
        EXCESS_KM = "Excess Kilometres", "Excess Kilometres"  # BR-11
        FUEL_SHORTFALL = "Fuel Shortfall", "Fuel Shortfall"  # BR-12
        LATE_RETURN = "Late Return", "Late Return"  # BR-10
        ACCESSORY = "Unreturned Accessory", "Unreturned Accessory"  # Return.Charges
        DAMAGE = "Damage", "Damage"  # Return.Charges
        DISCOUNT = "Discount", "Discount"  # BR-6

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="lines")
    line_type = models.CharField(max_length=32, choices=LineType.choices)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = _money()
    amount = _money()
    # Return.Charges: a damage charge is entered with a justification.
    justification = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(Q(line_type="Discount") & Q(amount__lte=0))
                | (~Q(line_type="Discount") & Q(amount__gte=0)),
                name="payments_invoiceline_amount_sign",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.invoice}: {self.line_type} {self.amount}"


class InvoiceAdjustment(AppendOnlyModel):
    """Pay.Invoice, History.Immutable: a credit or debit note on an invoice."""

    class AdjustmentType(models.TextChoices):
        CREDIT_NOTE = "Credit Note", "Credit Note"
        DEBIT_NOTE = "Debit Note", "Debit Note"

    adjustment_number = models.CharField(max_length=32, unique=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="adjustments")
    adjustment_type = models.CharField(max_length=16, choices=AdjustmentType.choices)
    reason = models.TextField()
    amount = _money()
    tax_amount = _money(default=0)
    issued_at = models.DateTimeField(default=timezone.now)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invoice_adjustments_issued",
    )

    class Meta:
        ordering = ["-issued_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0) & Q(tax_amount__gte=0),
                name="payments_adjustment_amounts",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.adjustment_number} ({self.adjustment_type} on {self.invoice})"


# ─── Ledger (append-only) ─────────────────────────────────────────────────


class LedgerEntry(AppendOnlyModel):
    """Pay.Ledger: every money movement of a booking, never deleted or overwritten."""

    class EntryType(models.TextChoices):
        CHARGE = "Charge", "Charge"
        CAPTURE = "Capture", "Capture"
        REFUND = "Refund", "Refund"
        DEPOSIT_HOLD = "Deposit Hold", "Deposit Hold"
        DEPOSIT_RELEASE = "Deposit Release", "Deposit Release"
        ADJUSTMENT = "Adjustment", "Adjustment"

    class Method(models.TextChoices):
        CARD = "Card", "Card"
        ONLINE = "Online", "Online"
        CASH = "Cash", "Cash"

    booking = models.ForeignKey(
        "bookings.Booking", on_delete=models.PROTECT, related_name="ledger_entries"
    )
    entry_type = models.CharField(max_length=32, choices=EntryType.choices)
    amount = _money()
    method = models.CharField(max_length=16, choices=Method.choices, blank=True)
    payment = models.ForeignKey(
        Payment, on_delete=models.PROTECT, null=True, blank=True, related_name="ledger_entries"
    )
    gateway_reference = models.CharField(max_length=128, blank=True)
    # An adjustment references the entry it corrects (CLAUDE.md: corrections
    # are new records that reference the original).
    reference_entry = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="adjustments"
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    note = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    # Pay.Idempotent: set on the entry that marks a capture_charges() run.
    idempotency_key = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["booking", "timestamp", "id"]
        verbose_name_plural = "ledger entries"
        constraints = [
            models.UniqueConstraint(
                fields=["idempotency_key"],
                condition=~Q(idempotency_key=""),
                name="payments_ledger_idempotency_key_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.booking}: {self.entry_type} {self.amount}"


# ─── Refunds (Pay.Refund, UC 13 Approve Refund) ──────────────────────────


class RefundRequest(TimeStampedModel):
    """A refund of one payment, to its original instrument (Pay.Refund, BR-14).

    Exp 2 UC 13: a refund above REFUND_AUTO_APPROVAL_LIMIT waits as Pending
    Approval until an Administrator approves (the refund is issued and the
    approver recorded) or rejects it (the reason is recorded and the customer
    told). A cash refund is Approved until a named branch staff member pays
    it out. Status changes go through payments.services and are audited.
    """

    class Status(models.TextChoices):
        PENDING_APPROVAL = "Pending Approval", "Pending Approval"
        APPROVED = "Approved", "Approved"  # cash only: waiting to be paid out at the branch
        ISSUED = "Issued", "Issued"
        REJECTED = "Rejected", "Rejected"
        FAILED = "Failed", "Failed"  # the gateway refused it

    original_payment = models.ForeignKey(
        Payment, on_delete=models.PROTECT, related_name="refund_requests"
    )
    amount = _money()
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="refunds_requested",
    )
    requested_at = models.DateTimeField(default=timezone.now)
    # UC 13: the Administrator who approved or rejected it.
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="refunds_decided",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    # The Refund payment row once issued (gateway reference, SI-1.3; or the cash refund).
    refund = models.OneToOneField(
        Payment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="refund_request",
    )
    refund_due_by = models.DateField(null=True, blank=True)  # BR-14, deposit refunds
    idempotency_key = models.CharField(max_length=80, unique=True)  # Pay.Idempotent

    class Meta:
        ordering = ["requested_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="payments_refund_amount_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"Refund {self.pk} of {self.amount} ({self.status})"


class GatewayNotification(AppendOnlyModel):
    """SI-1.4: every signed gateway notification, stored once by its event id.

    A repeated notification finds its event id here and changes nothing
    (Pay.Idempotent). Append-only, like the ledger.
    """

    event_id = models.CharField(max_length=100, unique=True)
    event_type = models.CharField(max_length=64)
    gateway_reference = models.CharField(max_length=128, blank=True)
    payload = models.JSONField()
    received_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self) -> str:
        return f"{self.event_id} {self.event_type}"
