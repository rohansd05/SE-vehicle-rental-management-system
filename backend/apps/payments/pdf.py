"""Invoice PDF (Pay.Invoice; D3: ReportLab, pure Python).

Rendered from the stored, immutable invoice and its lines, so a download
always shows exactly what was issued. Times are shown in local time (CO-6).
The security deposit is shown apart and outside the total (Pay.Deposit).
"""

from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Invoice
from .services import tax_rate_of


def _money(amount: Decimal) -> str:
    return f"{settings.CURRENCY} {amount:,.2f}"


def _local(value) -> str:
    return timezone.localtime(value).strftime("%d %b %Y, %H:%M")


def render_invoice_pdf(invoice: Invoice) -> bytes:
    booking = invoice.booking
    vehicle = booking.vehicle
    styles = getSampleStyleSheet()
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=f"Invoice {invoice.invoice_number}",
        author=invoice.agency_name,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    story = [
        Paragraph(invoice.agency_name, styles["Title"]),
        Paragraph(
            f"Tax registration: {invoice.agency_tax_registration or 'not set'}", styles["Normal"]
        ),
        Spacer(1, 6 * mm),
        Paragraph(f"Tax invoice {invoice.invoice_number}", styles["Heading2"]),
    ]
    details = [
        ["Issued", _local(invoice.issue_date)],
        ["Booking reference", booking.booking_reference],
        ["Customer", f"{booking.customer.user.name} ({booking.customer.user.email})"],
        ["Vehicle", f"{vehicle.brand} {vehicle.model}, {vehicle.registration_no}"],
        ["Pickup branch", booking.pickup_branch.branch_name],
        ["Pickup", _local(booking.pickup_datetime)],
        ["Return", _local(booking.return_datetime)],
    ]
    story += [Table(details, colWidths=[45 * mm, 125 * mm]), Spacer(1, 6 * mm)]

    rows = [["Item", "Quantity", "Unit price", "Amount"]]
    rows += [
        [
            line.description,
            f"{line.quantity.normalize():f}",
            _money(line.unit_price),
            _money(line.amount),
        ]
        for line in invoice.lines.order_by("pk")
    ]
    taxable = invoice.total_amount - invoice.tax_amount
    rows += [
        ["Taxable amount", "", "", _money(taxable)],
        [f"Tax at {tax_rate_of(invoice)}%", "", "", _money(invoice.tax_amount)],
        ["Total", "", "", _money(invoice.total_amount)],
    ]
    table = Table(rows, colWidths=[85 * mm, 22 * mm, 32 * mm, 32 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.black),
                ("LINEABOVE", (0, -3), (-1, -3), 0.5, colors.grey),
                ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.black),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ]
        )
    )
    story += [
        table,
        Spacer(1, 8 * mm),
        Paragraph(
            f"Refundable security deposit held separately: {_money(booking.security_deposit)}. "
            "It is not part of this invoice and is refunded after the rental (BR-14).",
            styles["Normal"],
        ),
    ]
    document.build(story)
    return buffer.getvalue()
