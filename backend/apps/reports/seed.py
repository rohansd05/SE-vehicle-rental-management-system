"""DEMO data for the reports (Module R3), loaded by `seed_demo --reports` (fictitious).

- reports@vrms.test, a demo customer with a verified licence (password as the
  other demo accounts), who joined about three months ago.
- Ten past bookings of that customer over the last three months, at Andheri
  (MH02DB2001, MH02DB2002) and Bandra (three of the 20 demo vehicles): eight
  returned, one returned with return charges (a debit note, N2) and one no-show
  (a credit note for the half of the rental refunded, BR-8). Each has its
  invoice, issued at confirmation, and its ledger entries: the rental charge and
  the deposit hold and release; card, on-line and cash. One has an add-on, one a
  discount code (D17).
- One Preventive maintenance job with parts at Bandra, through the maintenance
  services (work recorded with a service date 40 days ago), so the cost report
  has a job beside demo jobs 2 and 3 (maintenance/seed.py, unchanged).

Why a flag: invoices, notes and ledger entries are append-only (CLAUDE.md; a
PostgreSQL trigger refuses deletes), so once loaded this data can never be
removed and `seed_demo --reset` refuses afterwards, as it does once any demo has
moved money. Without --reports, seed_demo and its reset are unchanged.

The past dates are written on the rows directly, because the payments services
always stamp "now"; the bookings still pass through the booking state machine
(states.transition(), audited as system actions) and the prices through
calculate_price() (BR-6, BR-7, D14). Idempotent: a booking is added only if the
customer has none at that vehicle and pickup time, the job only once.
"""

import secrets
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.utils import timezone

from apps.accounts.models import Customer, Licence, LicenceCategory, MaintenanceTechnician, User
from apps.bookings.models import Booking, BookingAddOn
from apps.bookings.numbering import next_in_sequence
from apps.bookings.seed import _audit
from apps.bookings.states import transition
from apps.core.audit import record_audit, snapshot
from apps.core.choices import VehicleType
from apps.fleet.models import Vehicle
from apps.maintenance import services as maintenance
from apps.maintenance.models import MaintenanceJob
from apps.payments.models import Invoice, InvoiceAdjustment, InvoiceLine, LedgerEntry
from apps.pricing.models import AddOn, DiscountCode
from apps.pricing.services import calculate_price, current_tariff

CUSTOMER_EMAIL = "reports@vrms.test"
CUSTOMER_NAME = "Demo Customer (reports)"
CUSTOMER_MOBILE = "+919800000013"
LICENCE_NUMBER = "MH02 20160044556"
PICKUP_TIME = time(10, 0)  # IST
RETURN_CHARGE = Decimal("472.00")  # 40 km over the allowance at 10.00 (BR-11), tax inside
RETURN_CHARGE_NOTE = (
    "Return charges (Return.Charges): Excess kilometres, 40 km over the allowance (BR-11)"
)
JOB_PROBLEM = "[Reports demo] Preventive service at the BR-15 interval."

Status = Booking.Status
Entry = LedgerEntry.EntryType

# (days before today, rental days, vehicle, add-on, discount code, method, outcome)
# Vehicles: Andheri MH02DB2001 (Baleno) and MH02DB2002 (Venue); Bandra demo vehicles 1
# (i20), 6 (XUV700) and 16 (Classic 350). Outcomes: returned, "charges" or "no-show".
BOOKINGS = [
    (84, 2, "MH02DB2001", "Child seat", "", "Card", "returned"),
    (66, 3, "MH02DB2002", "", "WELCOME10", "Online", "returned"),
    (45, 1, "MH02DB2001", "", "", "Card", "charges"),
    (20, 2, "MH02DB2002", "", "", "Card", "returned"),
    (9, 1, "MH02DB2001", "", "", "Card", "no-show"),
    (75, 2, 1, "", "", "Card", "returned"),
    (52, 4, 6, "", "", "Online", "returned"),
    (30, 1, 16, "Additional helmet", "", "Cash", "returned"),
    (12, 2, 6, "", "", "Card", "returned"),
    (4, 2, 1, "", "", "Cash", "returned"),
]


def _vehicle(key) -> Vehicle:
    from apps.core.management.commands.seed_demo import demo_registrations

    registration = key if isinstance(key, str) else demo_registrations()[key]
    return Vehicle.objects.select_related("category", "home_branch").get(
        registration_no=registration
    )


def _at(days_ago: int) -> datetime:
    return timezone.make_aware(
        datetime.combine(timezone.localdate() - timedelta(days=days_ago), PICKUP_TIME)
    )


def _seed_customer(
    count,
    *,
    email: str = CUSTOMER_EMAIL,
    name: str = CUSTOMER_NAME,
    mobile_no: str = CUSTOMER_MOBILE,
    licence_number: str = LICENCE_NUMBER,
) -> Customer:
    """The reports customer; Module R4's rating demo reuses it with its own details."""
    from apps.core.management.commands.seed_demo import DEMO_PASSWORD, STAFF

    user = User.objects.filter(email=email).first()
    if user is None:
        user = User.objects.create_user(
            email=email,
            password=DEMO_PASSWORD,
            name=name,
            mobile_no=mobile_no,
            role=User.Role.CUSTOMER,
            address="22 Demo Lane, Bandra (W), Mumbai 400050",
            date_joined=_at(88),
        )
        count("users", True)
        _audit("Create", user)
    customer, created = Customer.objects.get_or_create(
        user=user,
        defaults={
            "date_of_birth": date(1992, 8, 14),
            "emergency_contact_name": "Demo Emergency Contact",
            "emergency_contact_mobile": "+919800000092",
        },
    )
    count("customers", created)
    licence, created = Licence.objects.get_or_create(
        customer=customer,
        defaults={
            "licence_number": licence_number,
            "issuing_authority": "RTO Mumbai (West)",
            "issue_date": date(2016, 5, 2),
            "expiry_date": date(2036, 5, 1),
            "status": Licence.Status.VERIFIED,
            "verified_by": User.objects.get(email=STAFF.email),
            "verified_at": _at(88),
        },
    )
    count("licences", created)
    for category in (VehicleType.CAR, VehicleType.TWO_WHEELER):
        _, created = LicenceCategory.objects.get_or_create(licence=licence, category=category)
        count("licence categories", created)
    return customer


def _number(model, field: str, prefix: str, on: datetime) -> str:
    return next_in_sequence(model, field, f"{prefix}-{timezone.localtime(on).year}-", 6)


def _invoice(booking: Booking, priced, issued: datetime) -> Invoice:
    """Pay.Invoice as payments.issue_invoice() writes it, dated at the confirmation."""
    invoice = Invoice.objects.create(
        invoice_number=_number(Invoice, "invoice_number", "INV", issued),
        issue_date=issued,
        tax_amount=priced.tax_amount,
        total_amount=priced.total_payable,
        booking=booking,
        agency_name=settings.AGENCY_NAME,
        agency_tax_registration=settings.AGENCY_TAX_REGISTRATION,
    )
    unit = priced.billing_unit + ("" if priced.billing_count == 1 else "s")
    lines = [
        (
            InvoiceLine.LineType.RENTAL,
            f"Rental, {priced.billing_count} {unit}",
            Decimal(priced.billing_count),
            priced.unit_rate,
            priced.base_charge,
        )
    ]
    lines += [
        (
            InvoiceLine.LineType.ADD_ON,
            f"{line.name} x{line.quantity}, {line.days} day{'' if line.days == 1 else 's'}",
            Decimal(line.quantity * line.days),
            line.daily_rate,
            line.amount,
        )
        for line in priced.add_ons
    ]
    if priced.discount_amount > 0:
        lines.append(
            (
                InvoiceLine.LineType.DISCOUNT,
                f"Discount {priced.discount_code}",
                Decimal("1"),
                -priced.discount_amount,
                -priced.discount_amount,
            )
        )
    for line_type, description, quantity, unit_price, amount in lines:
        InvoiceLine.objects.create(
            invoice=invoice,
            line_type=line_type,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            amount=amount,
        )
    record_audit(None, "Invoice Issued", invoice, after=snapshot(invoice))
    return invoice


def _note(invoice: Invoice, kind: str, amount: Decimal, reason: str, issued: datetime) -> None:
    taxable = invoice.total_amount - invoice.tax_amount
    rate = invoice.tax_amount * 100 / taxable if taxable > 0 else Decimal("0")
    prefix = "CN" if kind == InvoiceAdjustment.AdjustmentType.CREDIT_NOTE else "DN"
    note = InvoiceAdjustment.objects.create(
        adjustment_number=_number(InvoiceAdjustment, "adjustment_number", prefix, issued),
        invoice=invoice,
        adjustment_type=kind,
        reason=reason,
        amount=amount,
        tax_amount=(amount * rate / (100 + rate)).quantize(Decimal("0.01"), ROUND_HALF_UP),
        issued_at=issued,
    )
    record_audit(None, f"{kind} Issued", note, after=snapshot(note))


def _ledger(booking: Booking, entry_type: str, amount: Decimal, method: str, note, at) -> None:
    LedgerEntry.objects.create(
        booking=booking,
        entry_type=entry_type,
        amount=amount,
        method=method,
        note=note,
        timestamp=at,
    )


def _seed_booking(count, customer: Customer, spec) -> None:
    days_ago, days, key, add_on_name, code, method, outcome = spec
    vehicle = _vehicle(key)
    pickup = _at(days_ago)
    if Booking.objects.filter(customer=customer, vehicle=vehicle, pickup_datetime=pickup).exists():
        return
    return_ = pickup + timedelta(days=days)
    confirmed = pickup - timedelta(days=3)
    discount = DiscountCode.objects.get(code=code) if code else None
    add_ons = [(AddOn.objects.get(name=add_on_name), 1)] if add_on_name else []
    tariff = current_tariff(vehicle.category, pickup)
    priced = calculate_price(
        tariff=tariff,
        vehicle_type=vehicle.category.vehicle_type,
        pickup=pickup,
        return_=return_,
        add_ons=add_ons,
        discount=discount,
    )
    booking = Booking.objects.create(
        customer=customer,
        vehicle=vehicle,
        pickup_branch=vehicle.home_branch,
        tariff=tariff,
        pickup_datetime=pickup,
        return_datetime=return_,
        terms_accepted_at=confirmed,
        discount_code=discount,
    )
    for add_on, quantity in add_ons:
        BookingAddOn.objects.create(
            booking=booking, add_on=add_on, quantity=quantity, daily_rate=add_on.daily_rate
        )
    booking.total_amount = priced.total_payable
    booking.security_deposit = priced.security_deposit
    booking.discount_amount = priced.discount_amount
    reason = "Demo booking (seed_demo --reports)."
    transition(
        booking,
        Status.PENDING_PAYMENT,
        actor=None,
        reason=reason,
        update_fields=("total_amount", "security_deposit", "discount_amount"),
    )
    booking.booking_reference = next_in_sequence(
        Booking, "booking_reference", f"VRMS-{timezone.localtime(confirmed):%Y%m%d}-", 4
    )
    booking.pickup_code = f"{secrets.randbelow(10**settings.PICKUP_CODE_LENGTH):06d}"
    booking.confirmed_at = confirmed
    booking.cash_on_collection = method == "Cash"
    transition(
        booking,
        Status.CONFIRMED,
        actor=None,
        reason=reason,
        update_fields=("booking_reference", "pickup_code", "confirmed_at", "cash_on_collection"),
    )
    paid_at = pickup if method == "Cash" else confirmed  # BR-9: cash at the collection
    invoice = _invoice(booking, priced, paid_at)
    _ledger(
        booking, Entry.CHARGE, priced.total_payable, method, "Rental charge (Book.Done)", paid_at
    )
    deposit = priced.security_deposit
    _ledger(booking, Entry.DEPOSIT_HOLD, deposit, method, "Security deposit held (BR-3)", paid_at)
    count("bookings", True)

    if outcome == "no-show":
        transition(booking, Status.NO_SHOW, actor=None, reason=reason)
        missed = pickup + settings.NO_SHOW_AFTER
        refund = (priced.total_payable * (100 - settings.NO_SHOW_RETAINED_PERCENT) / 100).quantize(
            Decimal("0.01"), ROUND_HALF_UP
        )
        why = "No-show: 50% of the rental retained (BR-8)."
        _note(invoice, InvoiceAdjustment.AdjustmentType.CREDIT_NOTE, refund, why, missed)
        _ledger(booking, Entry.REFUND, refund, method, why, missed)
        _ledger(booking, Entry.DEPOSIT_RELEASE, deposit, method, "Security deposit (BR-8)", missed)
        return
    booking.handed_over_at = pickup
    transition(booking, Status.ACTIVE, actor=None, reason=reason, update_fields=("handed_over_at",))
    booking.returned_at = return_
    booking.distance_travelled = 180 * days
    balance = deposit
    if outcome == "charges":
        booking.distance_travelled += 40
        balance -= RETURN_CHARGE
        _note(
            invoice,
            InvoiceAdjustment.AdjustmentType.DEBIT_NOTE,
            RETURN_CHARGE,
            RETURN_CHARGE_NOTE,
            return_,
        )
        _ledger(booking, Entry.CHARGE, RETURN_CHARGE, method, RETURN_CHARGE_NOTE, return_)
    transition(
        booking,
        Status.COMPLETED,
        actor=None,
        reason=reason,
        update_fields=("returned_at", "distance_travelled"),
    )
    _ledger(
        booking, Entry.DEPOSIT_RELEASE, balance, method, "Security deposit balance (BR-14)", return_
    )


def _seed_job(count) -> None:
    """A Preventive job with parts at Bandra, through the maintenance services (BR-16)."""
    if MaintenanceJob.objects.filter(reported_problem=JOB_PROBLEM).exists():
        return
    from apps.core.management.commands.seed_demo import ADMIN, TECH

    admin = User.objects.get(email=ADMIN.email)
    technician = MaintenanceTechnician.objects.get(user__email=TECH.email)
    vehicle = _vehicle(6)
    start = timezone.now()
    job = maintenance.report_job(
        admin,
        vehicle=vehicle,
        job_type=MaintenanceJob.JobType.PREVENTIVE,
        severity=MaintenanceJob.Severity.MEDIUM,
        reported_problem=JOB_PROBLEM,
    )
    maintenance.schedule_job(
        job.pk,
        admin,
        technician=technician,
        scheduled_from=start,
        scheduled_to=start + timedelta(hours=4),
    )
    maintenance.start_job(job.pk, technician.user)
    maintenance.record_work(
        job.pk,
        technician.user,
        service_date=timezone.localdate() - timedelta(days=40),
        odometer_at_service=Vehicle.objects.get(pk=vehicle.pk).odometer,
        work_description="Changed the engine oil and the oil filter; checked brakes and tyres.",
        labour_cost=Decimal("600.00"),
        downtime_hours=Decimal("4.00"),
        parts=[
            {
                "part_name": "Engine oil (1 litre)",
                "quantity": Decimal("4"),
                "unit_cost": Decimal("450.00"),
            },
            {"part_name": "Oil filter", "quantity": Decimal("1"), "unit_cost": Decimal("350.00")},
        ],
    )
    maintenance.complete_job(job.pk, technician.user)
    count("maintenance jobs", True)


def seed_demo_report_data(count: Callable[[str, bool], None]) -> None:
    """Called by `seed_demo --reports` after its own data; `count(label, created)` counts."""
    customer = _seed_customer(count)
    for spec in BOOKINGS:
        _seed_booking(count, customer, spec)
    _seed_job(count)
