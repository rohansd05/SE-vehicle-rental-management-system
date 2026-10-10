"""Core exceptions."""


class ImmutableRecordError(Exception):
    """Raised on any attempt to change or delete an immutable record.

    Append-only tables (AuditLog, LedgerEntry, Invoice, InvoiceLine,
    InvoiceAdjustment), signed condition reports and tariffs in effect
    (BR-13) are corrected by adding a new record, never by editing.
    """
