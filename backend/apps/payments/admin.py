"""Payments admin registrations.

Invoices, their lines and adjustments, and ledger entries are append-only
(Pay.Invoice, Pay.Ledger): view-only here, with no add, change or delete.
"""

from django.contrib import admin

from apps.core.admin import AuditedModelAdmin, ReadOnlyModelAdmin, ReadOnlyTabularInline

from .models import (
    CardPayment,
    CashPayment,
    Invoice,
    InvoiceAdjustment,
    InvoiceLine,
    LedgerEntry,
    OnlinePayment,
    Payment,
)

PAYMENT_LIST_DISPLAY = (
    "transaction_id",
    "booking",
    "transaction_type",
    "purpose",
    "amount",
    "status",
    "timestamp",
)
PAYMENT_LIST_FILTER = ("status", "transaction_type", "purpose")
PAYMENT_SEARCH = ("transaction_id", "gateway_reference", "booking__booking_reference")


class _PaymentAdmin(AuditedModelAdmin):
    list_display = PAYMENT_LIST_DISPLAY
    list_filter = PAYMENT_LIST_FILTER
    search_fields = PAYMENT_SEARCH
    raw_id_fields = ("booking", "original_payment", "initiated_by")
    date_hierarchy = "timestamp"

    def has_delete_permission(self, request, obj=None):
        return False  # Pay.Ledger: the payment record is kept


@admin.register(Payment)
class PaymentAdmin(_PaymentAdmin):
    def has_add_permission(self, request):
        return False  # add a card, cash or online payment instead


@admin.register(CardPayment)
class CardPaymentAdmin(_PaymentAdmin):
    list_display = (*PAYMENT_LIST_DISPLAY, "card_brand")


@admin.register(CashPayment)
class CashPaymentAdmin(_PaymentAdmin):
    list_display = (*PAYMENT_LIST_DISPLAY, "received_by")
    raw_id_fields = (*_PaymentAdmin.raw_id_fields, "received_by")


@admin.register(OnlinePayment)
class OnlinePaymentAdmin(_PaymentAdmin):
    list_display = (*PAYMENT_LIST_DISPLAY, "channel")
    list_filter = (*PAYMENT_LIST_FILTER, "channel")


class InvoiceLineInline(ReadOnlyTabularInline):
    model = InvoiceLine


class InvoiceAdjustmentInline(ReadOnlyTabularInline):
    model = InvoiceAdjustment


@admin.register(Invoice)
class InvoiceAdmin(ReadOnlyModelAdmin):
    list_display = ("invoice_number", "booking", "issue_date", "tax_amount", "total_amount")
    search_fields = ("invoice_number", "booking__booking_reference")
    date_hierarchy = "issue_date"
    inlines = [InvoiceLineInline, InvoiceAdjustmentInline]


@admin.register(InvoiceLine)
class InvoiceLineAdmin(ReadOnlyModelAdmin):
    list_display = ("invoice", "line_type", "description", "quantity", "unit_price", "amount")
    list_filter = ("line_type",)
    search_fields = ("invoice__invoice_number",)


@admin.register(InvoiceAdjustment)
class InvoiceAdjustmentAdmin(ReadOnlyModelAdmin):
    list_display = ("adjustment_number", "invoice", "adjustment_type", "amount", "issued_at")
    list_filter = ("adjustment_type",)
    search_fields = ("adjustment_number", "invoice__invoice_number")


@admin.register(LedgerEntry)
class LedgerEntryAdmin(ReadOnlyModelAdmin):
    list_display = ("timestamp", "booking", "entry_type", "amount", "method", "gateway_reference")
    list_filter = ("entry_type", "method")
    search_fields = ("booking__booking_reference", "gateway_reference")
    date_hierarchy = "timestamp"
