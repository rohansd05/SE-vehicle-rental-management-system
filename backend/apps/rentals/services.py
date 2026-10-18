"""Rentals business logic: Handover Vehicle (SRS 3.3; Exp 2 use case 7). Views stay thin.

- Handover.Refuse: handover_refusals() lists every condition that is not
  met, each with a stable `code` and a message for the branch staff.
- Handover.Checklist, Handover.Sign: capture_report() (Exp 3
  ConditionReport.capture_report()) stores the odometer, the fuel or charge
  level, the accessories issued, one photo of each side and the damage
  marked on the diagram, then the customer's signature. Once signed the
  report cannot be altered (rentals/models.py, migration 0002).
- Handover.Activate: handover_vehicle() (Exp 3 BranchStaff.handover_vehicle())
  does all of it in one transaction: booking Active with the actual handover
  time (bookings.states.activate_booking), vehicle On Rent (fleet status
  service), every step audited (SE-10), and the signed report e-mailed to
  the customer through a Celery task after commit.

Return Vehicle (SRS 3.3 Return.*; Exp 2 use case 8; Exp 4 sequence 2; DFD
process 6), Module N2:

- return_refusals(): only an Active booking can be returned.
- return_quote(): Return.Checklist readings in, the itemised settlement out
  (settlement.calculate_settlement(), Return.Charges), shown to the customer.
- return_vehicle() (Exp 3 BranchStaff.return_vehicle()): in one transaction
  the signed return report (Return.Odometer, with a supervisor override when
  the distance is implausible), the money through R1's services only
  (capture_charges, issue_debit_note, refund_deposit, record_due;
  Return.Settle, BR-14, Pay.Dues), Return.Flag through maintenance's
  report_job(), the odometer (DE-3, BR-15), the booking Completed
  (bookings.states.complete_booking) and the vehicle Available or Under
  Maintenance, every step audited and the statement e-mailed through Celery.

Owner: Nidhi (Modules N1, N2).
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.accounts.models import Licence, User
from apps.bookings.eligibility import NotEligibleError, licence_is_valid
from apps.bookings.models import Booking
from apps.bookings.states import activate_booking, complete_booking
from apps.core.audit import record_audit, snapshot
from apps.core.choices import VehicleType
from apps.core.permissions import branch_id_of
from apps.fleet.models import Vehicle
from apps.fleet.services.status import update_status
from apps.maintenance.models import MaintenanceJob
from apps.maintenance.services import (
    MaintenanceError,
    due_text,
    raise_preventive_job_if_due,
    report_job,
    service_due,
)
from apps.notifications.services import queue_email
from apps.payments import services as payments
from apps.payments.models import LedgerEntry, Payment, RefundRequest
from apps.pricing.models import FuelPrice

from .models import ConditionPhoto, ConditionReport
from .settlement import (
    ExtraCharge,
    Settlement,
    SettlementError,
    calculate_settlement,
    plausibility_limit,
)

BookingStatus = Booking.Status
ReportType = ConditionReport.ReportType


@dataclass(frozen=True)
class Refusal:
    code: str
    message: str


class HandoverError(Exception):
    """The handover cannot go ahead; the message says why."""


class HandoverRefusedError(HandoverError):
    """Handover.Refuse: one or more conditions are not met."""

    def __init__(self, refusals: list[Refusal]):
        self.refusals = refusals
        super().__init__(" ".join(refusal.message for refusal in refusals))


# ─── Branch bookings (UC 7 step 1) ────────────────────────────────────────


def branch_collections(bookings: QuerySet, *, when: str = "today", query: str = "") -> QuerySet:
    """Confirmed bookings to collect: today's, or upcoming ones, or a search.

    `bookings` is already scoped to the caller's branch. A search finds a
    Confirmed booking on any date by its reference, its pickup code or the
    customer's mobile number (the last ten digits, so "+91" is optional).
    """
    bookings = bookings.filter(status=BookingStatus.CONFIRMED).order_by("pickup_datetime", "pk")
    query = query.strip()
    if query:
        return bookings.filter(_lookup(query))
    today = timezone.localdate()
    if when == "upcoming":
        return bookings.filter(pickup_datetime__date__gt=today)
    return bookings.filter(pickup_datetime__date=today)


def _lookup(query: str) -> Q:
    """A booking by its reference, its pickup code or the customer's mobile (last ten digits)."""
    match = Q(booking_reference__iexact=query) | Q(pickup_code=query)
    digits = "".join(ch for ch in query if ch.isdigit())
    if len(digits) >= 10:
        match |= Q(customer__user__mobile_no__endswith=digits[-10:])
    return match


# ─── Handover.Refuse ──────────────────────────────────────────────────────

# eligibility.py speaks to the customer; at the counter the staff read these.
LICENCE_REFUSALS = {
    "licence_not_verified": "The customer's driving licence has not been verified.",
    "licence_expired": "The customer's driving licence has expired.",
    "licence_expires_before_return": (
        "The customer's driving licence expires before the return date (BR-2)."
    ),
    "licence_category": "The customer's driving licence does not cover a {type} (BR-3).",
}


def _type_label(vehicle: Vehicle) -> str:
    return "two-wheeler" if vehicle.vehicle_type == VehicleType.TWO_WHEELER else "car"


def _licence_refusal(booking: Booking) -> Refusal | None:
    """Exp 2 UC 7 include "Verify Licence Eligibility": BR-2 and BR-3, re-checked now."""
    licence = Licence.objects.filter(customer_id=booking.customer_id).first()
    try:
        licence_is_valid(licence, booking.vehicle.vehicle_type, booking.return_datetime)
    except NotEligibleError as exc:
        message = LICENCE_REFUSALS[exc.code].format(type=_type_label(booking.vehicle))
        return Refusal(exc.code, message)
    return None


def _document_refusals(booking: Booking) -> list[Refusal]:
    """SA-3: each statutory document valid for the whole booked period."""
    first_day = timezone.localdate(booking.pickup_datetime)
    last_day = timezone.localdate(booking.return_datetime)
    documents = list(booking.vehicle.documents.all())
    refusals = []
    for document_type in settings.HANDOVER_REQUIRED_DOCUMENTS:
        covering = [
            document
            for document in documents
            if document.document_type == document_type
            and (document.valid_from is None or document.valid_from <= first_day)
            and document.expiry_date >= last_day
        ]
        if not covering:
            latest = max(
                (d.expiry_date for d in documents if d.document_type == document_type),
                default=None,
            )
            refusals.append(_document_refusal(document_type, latest, last_day))
    return refusals


def _document_refusal(document_type: str, latest: date | None, last_day: date) -> Refusal:
    code = "document_" + document_type.lower().replace(" ", "_")
    if latest is None:
        detail = "is not on record"
    elif latest < last_day:
        detail = f"expires on {latest:%d %b %Y}, before the return date"
    else:
        detail = "is not yet valid on the pickup date"
    return Refusal(code, f"The vehicle's {document_type.lower()} {detail} (SA-3).")


def _vehicle_refusal(vehicle: Vehicle) -> Refusal | None:
    if vehicle.status == Vehicle.Status.UNSAFE:
        return Refusal(
            "vehicle_unsafe",
            "The vehicle is flagged Unsafe. Only an Administrator or an authorised technician "
            "can clear the flag (SA-2).",
        )
    if vehicle.status != Vehicle.Status.AVAILABLE:
        return Refusal(
            "vehicle_unavailable",
            f"The vehicle is {vehicle.status}, so it cannot be handed over.",
        )
    return None


def _service_refusal(vehicle: Vehicle) -> Refusal | None:
    """SA-2: no handover of a vehicle overdue for its preventive service (BR-15)."""
    due = service_due(vehicle)
    if due is None:
        return None
    return Refusal(
        "service_overdue",
        f"The vehicle's preventive service was due at {due_text(due)} (BR-15); it reads "
        f"{vehicle.odometer:,} km. It must be serviced before it is handed over (SA-2).",
    )


def _is_paid(booking: Booking) -> bool:
    """Appendix B: Confirmed means paid. A cash booking is paid once its deposit is recorded.

    shortcut: reads the payment rows directly, the same check as
    bookings/serializers.py; switch to R1's payments service once it exists.
    """
    return booking.payments.filter(status="Succeeded", purpose="Security Deposit").exists()


def handover_refusals(booking: Booking) -> list[Refusal]:
    """Handover.Refuse: every condition not met, in the order the staff check them."""
    if booking.status != BookingStatus.CONFIRMED:
        already = booking.status == BookingStatus.ACTIVE
        message = (
            "This booking has already been handed over."
            if already
            else f"Only a Confirmed booking can be handed over; this one is {booking.status}."
        )
        return [Refusal("already_handed_over" if already else "booking_not_confirmed", message)]
    refusals = []
    if timezone.now() < booking.pickup_datetime:
        refusals.append(
            Refusal(
                "pickup_not_arrived",
                "The pickup time has not arrived yet (use case 7 precondition).",
            )
        )
    licence = _licence_refusal(booking)
    if licence:
        refusals.append(licence)
    refusals.extend(_document_refusals(booking))
    vehicle = _vehicle_refusal(booking.vehicle)
    if vehicle:
        refusals.append(vehicle)
    service = _service_refusal(booking.vehicle)
    if service:
        refusals.append(service)
    if not _is_paid(booking):
        refusals.append(
            Refusal(
                "payment_due",
                "This booking has not been paid. Record the cash payment before the handover "
                "(BR-9).",
            )
        )
    return refusals


# ─── Handover.Checklist ───────────────────────────────────────────────────


def expected_accessories(booking: Booking) -> list[dict]:
    """The accessories to issue: BR-7's free helmet on a two-wheeler, then the booked add-ons."""
    items = []
    if booking.vehicle.vehicle_type == VehicleType.TWO_WHEELER:
        items.append({"name": "Helmet", "quantity": settings.FREE_HELMETS_PER_RIDER})
    for line in booking.add_ons.select_related("add_on").order_by("pk"):
        items.append({"name": line.add_on.name, "quantity": line.quantity})
    return items


def capture_report(
    booking: Booking,
    staff,
    *,
    report_type: str = ConditionReport.ReportType.HANDOVER,
    odometer_reading: int,
    fuel_level,
    accessories: list[dict],
    damage_marks: list[dict],
    photos: list[tuple[str, object]],
    signature,
    **details,
) -> ConditionReport:
    """Exp 3 ConditionReport.capture_report(): the checklist, then the signature.

    The report is stored unsigned, its photos added, and then the signature,
    which makes it final (Handover.Sign). `details` are the return's other
    fields (the settlement lines, the odometer override, the flagged job).
    """
    # shortcut: files written before a later failure stay in storage; a cleanup job can remove them.
    report = ConditionReport.objects.create(
        booking=booking,
        report_type=report_type,
        odometer_reading=odometer_reading,
        fuel_level=fuel_level,
        recorded_by=staff,
        accessories=accessories,
        damage_marks=damage_marks,
        **details,
    )
    for caption, image in photos:
        ConditionPhoto.objects.create(report=report, image=image, caption=caption)
    report.signature = signature
    report.signed_at = timezone.now()
    report.save()
    return report


# ─── Handover.Activate ────────────────────────────────────────────────────


def _email_context(booking: Booking, report: ConditionReport) -> dict:
    vehicle = booking.vehicle
    accessories = ", ".join(f"{a['name']} x{a['quantity']}" for a in report.accessories) or "None"
    damage = "; ".join(m.get("note") or "Marked on the diagram" for m in report.damage_marks)
    return {
        "name": booking.customer.user.name,
        "reference": booking.booking_reference,
        "vehicle": f"{vehicle.brand} {vehicle.model}",
        "registration_no": vehicle.registration_no,
        "branch": booking.pickup_branch.branch_name,
        "handed_over_at": f"{timezone.localtime(booking.handed_over_at):%d %b %Y %H:%M}",
        "return_at": f"{timezone.localtime(booking.return_datetime):%d %b %Y %H:%M}",
        "odometer": report.odometer_reading,
        "fuel_level": f"{report.fuel_level.normalize():f}",
        "accessories": accessories,
        "damage": damage or "None",
        "photo_count": report.photos.count(),
        "staff": report.recorded_by.user.name,
    }


def handover_vehicle(booking_id: int, user, *, request=None, **checklist) -> ConditionReport:
    """Exp 3 BranchStaff.handover_vehicle(): refuse, or record, sign and activate atomically."""
    staff = user.branch_staff
    with transaction.atomic():
        booking = (
            Booking.objects.select_for_update(of=("self",))
            .select_related("vehicle__category", "customer__user", "pickup_branch")
            .get(pk=booking_id)
        )
        if booking.pickup_branch_id != staff.branch_id:
            raise HandoverError("This booking is collected at another branch.")
        refusals = handover_refusals(booking)
        if refusals:
            raise HandoverRefusedError(refusals)

        report = capture_report(booking, staff, **checklist)
        record_audit(
            user, "Condition Report Signed", report, after=snapshot(report), request=request
        )
        activate_booking(booking, user, request=request)
        update_status(
            booking.vehicle,
            Vehicle.Status.ON_RENT,
            actor=user,
            reason=f"Handed over for booking {booking.booking_reference} (Handover.Activate).",
            request=request,
        )
        queue_email(  # Handover.Sign: a copy for the customer, sent after commit
            booking.customer.user,
            "handover_report",
            _email_context(booking, report),
            booking=booking,
        )
    return report


# ═══ Module N2: Return Vehicle (UC 8; Exp 4 sequence 2; DFD process 6) ══


class ReturnError(Exception):
    """The return cannot go ahead; `field` names the input at fault, if one is."""

    def __init__(self, message: str, *, code: str, field: str | None = None, status: int = 400):
        self.code = code
        self.field = field
        self.status = status
        super().__init__(message)


class ReturnRefusedError(ReturnError):
    """Exp 2 UC 8 precondition: the booking is not Active."""

    def __init__(self, refusals: list[Refusal]):
        self.refusals = refusals
        super().__init__(" ".join(r.message for r in refusals), code="return_refused", status=409)


@dataclass(frozen=True)
class ReturnReadings:
    """Return.Checklist, and the charges the staff member enters (Return.Charges)."""

    odometer_reading: int
    fuel_level: Decimal
    returned_at: datetime  # "the actual return time"
    missing_accessories: list[dict] = field(default_factory=list)  # name, quantity, cost
    damage_charges: list[dict] = field(default_factory=list)  # description, amount, justification


@dataclass(frozen=True)
class Flag:
    """Return.Flag: the problem, its severity, and whether the vehicle is unfit for use."""

    problem: str
    severity: str
    unfit: bool = True


@dataclass(frozen=True)
class ReturnQuote:
    settlement: Settlement
    accessories_returned: list[dict]
    override_required: bool
    plausibility_limit: int


# ─── Branch returns (UC 8 step 1) ─────────────────────────────────────────


def branch_returns(bookings: QuerySet, *, query: str = "") -> QuerySet:
    """Active bookings due back today or overdue, or a search among the branch's Active ones.

    `bookings` is already scoped to the caller's branch.
    """
    bookings = bookings.filter(status=BookingStatus.ACTIVE).order_by("return_datetime", "pk")
    query = query.strip()
    if query:
        return bookings.filter(_lookup(query))
    return bookings.filter(return_datetime__date__lte=timezone.localdate())


# ─── Refusals and reads ───────────────────────────────────────────────────

RETURN_REFUSALS = {
    BookingStatus.CONFIRMED: (
        "not_handed_over",
        "The vehicle has not been handed over yet, so there is nothing to return.",
    ),
    BookingStatus.PENDING_PAYMENT: (
        "booking_not_paid",
        "This booking has not been paid or collected, so there is nothing to return.",
    ),
    BookingStatus.CANCELLED: (
        "booking_cancelled",
        "This booking was cancelled, so there is nothing to return.",
    ),
    BookingStatus.NO_SHOW: (
        "booking_no_show",
        "This booking was a no-show: the vehicle was never collected.",
    ),
    BookingStatus.COMPLETED: (
        "already_returned",
        "This vehicle has already been returned and the booking settled.",
    ),
}


def handover_report(booking: Booking) -> ConditionReport | None:
    return booking.condition_reports.filter(report_type=ReportType.HANDOVER).first()


def return_report(booking: Booking) -> ConditionReport | None:
    return booking.condition_reports.filter(report_type=ReportType.RETURN).first()


def return_refusals(booking: Booking) -> list[Refusal]:
    """Exp 2 UC 8 precondition "The booking has status Active", with the reason when not."""
    if booking.status != BookingStatus.ACTIVE:
        code, message = RETURN_REFUSALS.get(
            booking.status,
            (
                "booking_not_active",
                f"Only an Active booking can be returned; this one is {booking.status}.",
            ),
        )
        return [Refusal(code, message)]
    if handover_report(booking) is None:
        return [Refusal("no_handover_report", "This booking has no handover condition report.")]
    return []


def deposit_payment(booking: Booking) -> Payment | None:
    """Pay.Deposit: the security deposit the booking was confirmed with."""
    return Payment.objects.filter(
        booking=booking,
        original_payment__isnull=True,
        status=Payment.Status.SUCCEEDED,
        purpose=Payment.Purpose.SECURITY_DEPOSIT,
    ).first()


def rental_paid(booking: Booking) -> list[LedgerEntry]:
    """The rental charges already paid (Pay.Ledger): at booking, and for any modification
    or extension (R2). Shown as paid at return and never charged again."""
    return list(
        LedgerEntry.objects.filter(
            booking=booking,
            entry_type=LedgerEntry.EntryType.CHARGE,
            payment__purpose=Payment.Purpose.RENTAL,
        ).order_by("timestamp", "pk")
    )


def deposit_refund(booking: Booking) -> RefundRequest | None:
    """BR-14: the deposit balance refund, waiting for approval or issued (UC 13)."""
    deposit = deposit_payment(booking)
    if deposit is None:
        return None
    return deposit.refund_requests.select_related("refund__cashpayment__received_by__user").last()


# ─── Return.Charges ───────────────────────────────────────────────────────


def _check_return_time(booking: Booking, returned_at: datetime) -> None:
    if returned_at > timezone.now():
        raise ReturnError(
            "The return time cannot be in the future.", code="return_time", field="returned_at"
        )
    if returned_at < (booking.handed_over_at or booking.pickup_datetime):
        raise ReturnError(
            "The return time cannot be before the handover.",
            code="return_time",
            field="returned_at",
        )


def _fuel_price(fuel_type: str, at: datetime) -> Decimal | None:
    """BR-12: the prevailing fuel or electricity price at the return."""
    price = (
        FuelPrice.objects.filter(fuel_type=fuel_type, effective_from__lte=at)
        .order_by("-effective_from")
        .first()
    )
    return price.price_per_unit if price else None


def _accessories(issued: list[dict], missing: list[dict]) -> tuple[list[dict], list[ExtraCharge]]:
    """Return.Checklist "accessories returned": those issued at handover less the missing
    ones, each charged at the cost the staff member enters (Return.Charges, N2-P5)."""
    remaining = {item["name"]: item["quantity"] for item in issued}
    charges = []
    for item in missing:
        name, quantity = item["name"], item["quantity"]
        if remaining.get(name, 0) < quantity:
            raise ReturnError(
                f"{name} × {quantity} was not issued at handover.",
                code="accessory_not_issued",
                field="missing_accessories",
            )
        remaining[name] -= quantity
        charges.append(ExtraCharge(f"Accessory not returned: {name} × {quantity}", item["cost"]))
    returned = [{"name": name, "quantity": count} for name, count in remaining.items() if count]
    return returned, charges


def _settlement(booking: Booking, handover: ConditionReport, readings: ReturnReadings):
    """Exp 4 sequence 2 calculate_price(): BR-10 to BR-12 at the booking's current return
    time and tariff (R2 extensions and modifications included), plus the staff's charges."""
    _check_return_time(booking, readings.returned_at)
    returned, accessory_charges = _accessories(handover.accessories, readings.missing_accessories)
    vehicle = booking.vehicle
    damage = [
        ExtraCharge(f"Damage: {item['description']}", item["amount"], item["justification"])
        for item in readings.damage_charges
    ]
    try:
        settlement = calculate_settlement(
            tariff=booking.tariff,
            pickup=booking.pickup_datetime,
            return_due=booking.return_datetime,
            returned_at=readings.returned_at,
            odometer_out=handover.odometer_reading,
            odometer_in=readings.odometer_reading,
            fuel_out=handover.fuel_level,
            fuel_in=readings.fuel_level,
            fuel_type=vehicle.fuel_type,
            fuel_capacity=vehicle.fuel_capacity,
            fuel_price=_fuel_price(vehicle.fuel_type, readings.returned_at),
            accessories=accessory_charges,
            damage=damage,
            deposit=booking.security_deposit,
        )
    except SettlementError as exc:
        if exc.code == "odometer_lower":  # UC 8 extension 2a: rejected, correction required
            raise ReturnError(str(exc), code=exc.code, field="odometer_reading") from exc
        raise ReturnError(str(exc), code=exc.code, status=409) from exc
    return settlement, returned


def _limit(booking: Booking, readings: ReturnReadings) -> int:
    out_since = booking.handed_over_at or booking.pickup_datetime
    return plausibility_limit(out_since, readings.returned_at)


def _check_branch(booking: Booking, user) -> None:
    if booking.pickup_branch_id != user.branch_staff.branch_id:
        raise ReturnError("This booking belongs to another branch.", code="other_branch")


def return_quote(booking: Booking, user, readings: ReturnReadings) -> ReturnQuote:
    """UC 8 step 3 (include: Calculate Settlement Charges): nothing is saved."""
    _check_branch(booking, user)
    refusals = return_refusals(booking)
    if refusals:
        raise ReturnRefusedError(refusals)
    settlement, returned = _settlement(booking, handover_report(booking), readings)
    limit = _limit(booking, readings)
    return ReturnQuote(settlement, returned, settlement.distance > limit, limit)


# ─── Return.Odometer, Return.Flag, Return.Settle ──────────────────────────


def _is_supervisor(user, branch_id: int) -> bool:
    if user.role == User.Role.ADMINISTRATOR:
        return True
    return user.role == User.Role.BRANCH_MANAGER and branch_id_of(user) == branch_id


def _odometer_override(booking, settlement, readings, override: dict | None, request):
    """Return.Odometer: a distance above the plausibility limit needs a supervisor (a Branch
    Manager of the branch or an Administrator) to sign in on the branch device and give the
    reason. Their sign-in goes through django-axes like any other (SE-8)."""
    limit = _limit(booking, readings)
    if settlement.distance <= limit:
        return None, ""
    override = override or {}
    reason = override.get("reason", "").strip()
    if not override.get("email") or not reason:
        raise ReturnError(
            f"{settlement.distance} km is more than the {limit} km plausible for this rental. "
            "A Branch Manager or an Administrator must approve the reading and give the reason "
            "(Return.Odometer).",
            code="override_required",
            field="override_reason",
        )
    supervisor = authenticate(
        getattr(request, "_request", request),
        username=override["email"].strip().lower(),
        password=override.get("password", ""),
    )
    if supervisor is None or not _is_supervisor(supervisor, booking.pickup_branch_id):
        raise ReturnError(
            "These are not the sign-in details of a Branch Manager of this branch or an "
            "Administrator.",
            code="override_refused",
            field="override_password",
        )
    return supervisor, reason


def _flag_vehicle(booking: Booking, user, flag: Flag, request) -> MaintenanceJob:
    """Return.Flag, UC 8 extension 3a (extend: Flag Vehicle for Maintenance): Maint.Create
    through report_job(). A fault found at return is Corrective work (proposed N2-P6)."""
    problem = flag.problem.strip()
    if problem:  # a blank one goes through as blank, so report_job() refuses it
        problem = f"Flagged at the return of {booking.booking_reference}: {problem}"
    try:
        return report_job(
            user,
            vehicle=booking.vehicle,
            job_type=MaintenanceJob.JobType.CORRECTIVE,
            severity=flag.severity,
            reported_problem=problem,
            request=request,
        )
    except MaintenanceError as exc:
        raise ReturnError(str(exc), code="flag_refused", field="flag_problem") from exc


def _settle(booking: Booking, settlement: Settlement, user, request) -> RefundRequest | None:
    """Return.Settle (Exp 4 sequence 2 Payment.refund(); DFD 6.4) through R1's services only.

    The charges are captured from the deposit (capture_charges); on the invoice they
    are a debit note, never an edit (Pay.Invoice); the balance is refunded (BR-14),
    or the charges above the deposit become a due (Pay.Dues, BR-4). The key is stable
    per booking, so a repeated Settle never charges twice (Pay.Idempotent).
    """
    lines = [payments.ChargeLine(line.description, line.amount) for line in settlement.lines]
    payments.capture_charges(
        booking, lines, user, idempotency_key=f"return-{booking.pk}", request=request
    )
    invoice = getattr(booking, "invoice", None)
    if invoice is not None and settlement.total > 0:
        reason = "Return charges (Return.Charges): " + "; ".join(
            line.description for line in settlement.lines
        )
        payments.issue_debit_note(
            invoice, settlement.total, reason, issued_by=user, request=request
        )
    refund = None
    if settlement.refund > 0:
        refund = payments.refund_deposit(booking, settlement.refund, user, request=request)
    if settlement.due > 0:
        payments.record_due(
            booking.customer,
            settlement.due,
            f"Return charges of {booking.booking_reference} above the security deposit "
            "(Return.Settle)",
            initiated_by=user,
            request=request,
        )
    return refund


def _record_odometer(vehicle: Vehicle, reading: int, user, request) -> None:
    """DE-3: the return reading becomes the vehicle's odometer, which BR-15 reads."""
    vehicle = Vehicle.objects.select_for_update().get(pk=vehicle.pk)
    before = vehicle.odometer
    vehicle.odometer = max(before, reading)  # Appendix A: never decreases
    vehicle.save(update_fields=["odometer", "updated_at"])
    record_audit(
        user,
        "Odometer Recorded",
        vehicle,
        before={"odometer": before},
        after={"odometer": vehicle.odometer, "reason": "Return.Odometer"},
        request=request,
    )


def _money_text(amount: Decimal) -> str:
    return f"{settings.CURRENCY} {amount:,.2f}"


def _statement(booking: Booking, settlement: Settlement, refund: RefundRequest | None) -> dict:
    """Exp 5 fork "Receive settlement statement": the e-mail's variables."""
    charges = "\n".join(
        f"- {line.description}: {_money_text(line.amount)}" for line in settlement.lines
    )
    if refund is None:
        balance = "No deposit balance is due back to you."
    elif refund.status == RefundRequest.Status.PENDING_APPROVAL:
        balance = (
            f"The balance of {_money_text(refund.amount)} is waiting for approval and will be "
            "refunded to your original payment method within 7 working days (BR-14)."
        )
    elif refund.original_payment.method == "Cash":  # Pay.Refund: paid out at the counter
        balance = f"The balance of {_money_text(refund.amount)} was paid back to you in cash."
    else:
        balance = (
            f"The balance of {_money_text(refund.amount)} is refunded to your original payment "
            "method (BR-14)."
        )
    due = (
        f"\n{_money_text(settlement.due)} above the deposit is recorded as a due. Please pay it "
        "on-line before your next booking."
        if settlement.due > 0
        else ""
    )
    vehicle = booking.vehicle
    return {
        "name": booking.customer.user.name,
        "reference": booking.booking_reference,
        "vehicle": f"{vehicle.brand} {vehicle.model}",
        "registration_no": vehicle.registration_no,
        "returned_at": f"{timezone.localtime(booking.returned_at):%d %b %Y %H:%M}",
        "distance": settlement.distance,
        "charges": charges or "- None",
        "total": _money_text(settlement.total),
        "deposit": _money_text(settlement.deposit),
        "balance": balance + due,
    }


def return_vehicle(
    booking_id: int,
    user,
    *,
    readings: ReturnReadings,
    expected_total: Decimal,
    damage_marks: list[dict],
    photos: list[tuple[str, object]],
    signature,
    flag: Flag | None = None,
    override: dict | None = None,
    request=None,
) -> ConditionReport:
    """Exp 3 BranchStaff.return_vehicle(), Exp 4 sequence 2, in one transaction.

    capture_report() (the odometer checked, Return.Odometer) -> calculate_price()
    (Return.Charges) -> Payment.refund() (Return.Settle) -> opt [fault] the job and
    Under Maintenance, alt [not flagged] Available -> booking Completed. The job is
    raised before the report is signed, because a signed report cannot change.
    `expected_total` is the total the customer acknowledged; if the charges now
    differ, nothing changes (409 settlement_changed). A second Settle of a booking
    already returned returns the first report and moves no money (Pay.Idempotent).
    """
    staff = user.branch_staff
    with transaction.atomic():
        booking = (
            Booking.objects.select_for_update(of=("self",))
            .select_related("vehicle__category", "customer__user", "pickup_branch", "tariff")
            .get(pk=booking_id)
        )
        _check_branch(booking, user)
        existing = return_report(booking)
        if booking.status == BookingStatus.COMPLETED and existing is not None:
            return existing
        refusals = return_refusals(booking)
        if refusals:
            raise ReturnRefusedError(refusals)

        settlement, returned = _settlement(booking, handover_report(booking), readings)
        if settlement.total != expected_total:
            raise ReturnError(
                f"The charges are now {_money_text(settlement.total)}. Show the settlement to "
                "the customer again and confirm.",
                code="settlement_changed",
                status=409,
            )
        supervisor, reason = _odometer_override(booking, settlement, readings, override, request)
        job = _flag_vehicle(booking, user, flag, request) if flag else None
        report = capture_report(
            booking,
            staff,
            report_type=ReportType.RETURN,
            odometer_reading=readings.odometer_reading,
            fuel_level=readings.fuel_level,
            accessories=returned,
            damage_marks=damage_marks,
            photos=photos,
            signature=signature,
            charges=[
                {
                    "kind": line.kind,
                    "description": line.description,
                    "amount": str(line.amount),
                    "justification": line.justification,
                }
                for line in settlement.lines
            ],
            odometer_override_by=supervisor,
            odometer_override_reason=reason,
            maintenance_job=job,
        )
        record_audit(
            user, "Condition Report Signed", report, after=snapshot(report), request=request
        )
        if supervisor is not None:
            record_audit(
                supervisor,
                "Odometer Override Approved",
                report,
                after={"distance": settlement.distance, "reason": reason},
                request=request,
            )
        refund = _settle(booking, settlement, user, request)
        _record_odometer(booking.vehicle, readings.odometer_reading, user, request)
        raise_preventive_job_if_due(booking.vehicle, request=request)  # Maint.Auto.Km
        vehicle = Vehicle.objects.get(pk=booking.vehicle_id)
        if vehicle.status == Vehicle.Status.ON_RENT:  # an Unsafe flag stays until cleared (SA-2)
            unfit = job is not None and flag.unfit
            update_status(
                vehicle,
                Vehicle.Status.UNDER_MAINTENANCE if unfit else Vehicle.Status.AVAILABLE,
                actor=user,
                reason=(
                    f"Flagged at return, maintenance job {job.job_id} (Return.Flag)."
                    if unfit
                    else f"Returned from booking {booking.booking_reference} (Return.Complete)."
                ),
                request=request,
            )
        booking.returned_at = readings.returned_at
        booking.distance_travelled = settlement.distance
        complete_booking(booking, user, request=request)
        queue_email(
            booking.customer.user,
            "return_settlement",
            _statement(booking, settlement, refund),
            booking=booking,
        )
    return report


def settlement_record(booking: Booking, report: ConditionReport) -> dict:
    """Return.Complete: the settlement the customer signed, and where its money went.

    `refund_status` is the deposit refund's (UC 13): Pending Approval above
    REFUND_AUTO_APPROVAL_LIMIT, Issued once refunded; a cash refund names the
    staff member who paid it out (Pay.Refund).
    """
    total = sum((Decimal(line["amount"]) for line in report.charges), Decimal("0.00"))
    used = min(total, booking.security_deposit)
    refund = deposit_refund(booking)
    cash = getattr(refund.refund, "cashpayment", None) if refund and refund.refund else None
    return {
        "lines": report.charges,
        "total": total,
        "deposit": booking.security_deposit,
        "deposit_used": used,
        "refund": booking.security_deposit - used,
        "due": total - used,
        "refund_status": refund.status if refund else "",
        "refund_paid_out_by": cash.received_by.user.name if cash else "",
        "maintenance_job": report.maintenance_job_id,
    }
