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
    booking = models.ForeignKey(
        "bookings.Booking", on_delete=models.PROTECT, related_name="payments"
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
        ]

    def __str__(self) -> str:
        return f"{self.transaction_id} {self.transaction_type} {self.amount} ({self.status})"


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

    class Meta:
        ordering = ["booking", "timestamp", "id"]
        verbose_name_plural = "ledger entries"

    def __str__(self) -> str:
        return f"{self.booking}: {self.entry_type} {self.amount}"
