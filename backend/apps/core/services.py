"""Core business logic. Views stay thin.

The audit log viewer (Fleet.Audit, SE-10; Module N3): which entries a user may
read, and the filters on them. Entries are never changed here or anywhere.
"""

from datetime import date

from django.db.models import CharField, Q, QuerySet
from django.db.models.functions import Cast

from .models import AuditLog
from .permissions import Role, branch_id_of


def _keys(queryset: QuerySet) -> QuerySet:
    """The primary keys as text, to match AuditLog.entity_id."""
    return queryset.annotate(entity_key=Cast("pk", CharField())).values("entity_key")


def _branch_entries(branch_id: int) -> Q:
    """A branch's entries: about its bookings, vehicles, jobs, reports, payments, refunds,
    invoices and ledger, about the branch itself, or made by its staff and manager."""
    from apps.bookings.models import Booking
    from apps.fleet.models import Branch, Vehicle
    from apps.maintenance.models import MaintenanceJob
    from apps.payments.models import Invoice, InvoiceAdjustment, LedgerEntry, Payment, RefundRequest
    from apps.rentals.models import ConditionReport

    on_booking = {"booking__pickup_branch_id": branch_id}
    records = [
        (["bookings.Booking"], Booking.objects.filter(pickup_branch_id=branch_id)),
        (["fleet.Branch"], Branch.objects.filter(pk=branch_id)),
        (
            ["fleet.Vehicle", "fleet.Car", "fleet.TwoWheeler"],
            Vehicle.objects.filter(home_branch_id=branch_id),
        ),
        (
            ["maintenance.MaintenanceJob"],
            MaintenanceJob.objects.filter(vehicle__home_branch_id=branch_id),
        ),
        (["rentals.ConditionReport"], ConditionReport.objects.filter(**on_booking)),
        (
            [
                "payments.Payment",
                "payments.CardPayment",
                "payments.CashPayment",
                "payments.OnlinePayment",
            ],
            Payment.objects.filter(**on_booking),
        ),  # fmt: skip
        (
            ["payments.RefundRequest"],
            RefundRequest.objects.filter(original_payment__booking__pickup_branch_id=branch_id),
        ),
        (["payments.Invoice"], Invoice.objects.filter(**on_booking)),
        (
            ["payments.InvoiceAdjustment"],
            InvoiceAdjustment.objects.filter(invoice__booking__pickup_branch_id=branch_id),
        ),
        (["payments.LedgerEntry"], LedgerEntry.objects.filter(**on_booking)),
    ]
    match = Q(actor__branch_staff__branch_id=branch_id) | Q(
        actor__administrator__branchmanager__branch_id=branch_id
    )
    for labels, queryset in records:
        match |= Q(entity_type__in=labels, entity_id__in=_keys(queryset))
    return match


def audit_entries_for(user) -> QuerySet:
    """Fleet.Audit: an Administrator reads every entry; a Branch Manager, a restricted
    Administrator (SRS 2.2), only their own branch's (Proposed N3-P1); nobody else any."""
    entries = AuditLog.objects.select_related("actor")
    if not (user and user.is_authenticated and user.is_active):
        return entries.none()
    if user.role == Role.ADMINISTRATOR:
        return entries
    branch = branch_id_of(user)
    if user.role == Role.BRANCH_MANAGER and branch:
        return entries.filter(_branch_entries(branch))
    return entries.none()


SYSTEM_ACTOR = "system"


def filter_audit_entries(
    entries: QuerySet,
    *,
    actor: str = "",
    action: str = "",
    entity_type: str = "",
    entity_id: str = "",
    date_from: date | None = None,
    date_to: date | None = None,
) -> QuerySet:
    """Filters by actor (name or e-mail, or "system" for system actions), action, entity
    and date. Dates are local dates (presentation time zone, CO-6)."""
    actor = actor.strip()
    if actor.lower() == SYSTEM_ACTOR:
        entries = entries.filter(actor__isnull=True)
    elif actor:
        entries = entries.filter(Q(actor__email__icontains=actor) | Q(actor__name__icontains=actor))
    if action:
        entries = entries.filter(action=action)
    if entity_type:
        entries = entries.filter(entity_type=entity_type)
    if entity_id:
        entries = entries.filter(entity_id=entity_id.strip())
    if date_from:
        entries = entries.filter(timestamp__date__gte=date_from)
    if date_to:
        entries = entries.filter(timestamp__date__lte=date_to)
    return entries


def audit_filter_options(entries: QuerySet) -> dict[str, list[str]]:
    """Every action and entity type the user's entries hold, so each event type of
    every module can be chosen, including ones added later."""
    unordered = entries.order_by()
    return {
        "actions": sorted(unordered.values_list("action", flat=True).distinct()),
        "entity_types": sorted(unordered.values_list("entity_type", flat=True).distinct()),
    }
