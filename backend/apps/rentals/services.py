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

Owner: Nidhi (Module N1).
"""

from dataclasses import dataclass
from datetime import date

from django.conf import settings
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.accounts.models import Licence
from apps.bookings.eligibility import NotEligibleError, licence_is_valid
from apps.bookings.models import Booking
from apps.bookings.states import activate_booking
from apps.core.audit import record_audit, snapshot
from apps.core.choices import VehicleType
from apps.fleet.models import Vehicle
from apps.fleet.services.status import update_status
from apps.notifications.services import queue_email

from .models import ConditionPhoto, ConditionReport

BookingStatus = Booking.Status


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
        match = Q(booking_reference__iexact=query) | Q(pickup_code=query)
        digits = "".join(ch for ch in query if ch.isdigit())
        if len(digits) >= 10:
            match |= Q(customer__user__mobile_no__endswith=digits[-10:])
        return bookings.filter(match)
    today = timezone.localdate()
    if when == "upcoming":
        return bookings.filter(pickup_datetime__date__gt=today)
    return bookings.filter(pickup_datetime__date=today)


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
            "The vehicle is flagged Unsafe. Only an Administrator can clear the flag (SA-2).",
        )
    if vehicle.status != Vehicle.Status.AVAILABLE:
        return Refusal(
            "vehicle_unavailable",
            f"The vehicle is {vehicle.status}, so it cannot be handed over.",
        )
    return None


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
    odometer_reading: int,
    fuel_level,
    accessories: list[dict],
    damage_marks: list[dict],
    photos: list[tuple[str, object]],
    signature,
) -> ConditionReport:
    """Exp 3 ConditionReport.capture_report(): the checklist, then the signature.

    The report is stored unsigned, its photos added, and then the signature,
    which makes it final (Handover.Sign).
    """
    # shortcut: files written before a later failure stay in storage; a cleanup job can remove them.
    report = ConditionReport.objects.create(
        booking=booking,
        report_type=ConditionReport.ReportType.HANDOVER,
        odometer_reading=odometer_reading,
        fuel_level=fuel_level,
        recorded_by=staff,
        accessories=accessories,
        damage_marks=damage_marks,
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
