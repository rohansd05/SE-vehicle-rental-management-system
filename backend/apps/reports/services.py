"""Reports (SRS 3.8 Report.Dashboard, Report.Utilisation, Report.Revenue, Report.Access;
Exp 2 UC 14 View Reports; Exp 3 BranchManager.view_branch_reports(); DFD process 8).

Computed on the fly in the database (annotate and aggregate; no report
tables). Report.Access, UC 14 extension 1a: an Administrator reports on every
branch, a Branch Manager only on their own, through scope_queryset(); the
views let nobody else in. Money is Decimal (CO-6). A period is a range of
local (IST) dates, turned here into UTC instants [start, end).

Owner: Rohan (WBS 1.4.5).
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db.models import (
    Case,
    Count,
    DateTimeField,
    DecimalField,
    DurationField,
    ExpressionWrapper,
    F,
    Func,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Greatest, Least
from django.utils import timezone

from apps.accounts.models import Customer, User
from apps.bookings.models import Booking
from apps.core.permissions import branch_id_of, scope_queryset
from apps.fleet.models import Branch, Vehicle, VehicleCategory
from apps.maintenance.models import MaintenanceJob, PartUsed
from apps.payments.models import Invoice, InvoiceAdjustment, InvoiceLine, LedgerEntry, RefundRequest
from apps.rentals.models import ConditionReport

ZERO = Decimal("0.00")
MONEY = DecimalField(max_digits=14, decimal_places=2)
NO_TIME = timedelta(0)
Status = Booking.Status
Line = InvoiceLine.LineType
Note = InvoiceAdjustment.AdjustmentType
Entry = LedgerEntry.EntryType
Job = MaintenanceJob


@dataclass(frozen=True)
class Period:
    """Report.*: the period the actor selects (UC 14 step 1), as local dates, both included."""

    date_from: date
    date_to: date

    @property
    def start(self) -> datetime:
        return timezone.make_aware(datetime.combine(self.date_from, time.min))

    @property
    def end(self) -> datetime:
        return timezone.make_aware(datetime.combine(self.date_to + timedelta(days=1), time.min))

    def window(self, field: str) -> Q:
        return Q(**{f"{field}__gte": self.start, f"{field}__lt": self.end})


def scope_label(user) -> str:
    """UC 14 extension 1a: what the report covers, in words."""
    if user.role == User.Role.ADMINISTRATOR:
        return "All branches"
    return Branch.objects.get(pk=branch_id_of(user)).branch_name


def _money(expression, *conditions: Q, **lookups):
    """A Decimal Sum, of the rows matching the conditions if any; 0.00, never None."""
    matching = Q(*conditions, **lookups) if conditions or lookups else None
    total = Sum(expression, filter=matching, output_field=MONEY)
    return Coalesce(total, Value(ZERO), output_field=MONEY)


def _subtotal(rows: QuerySet, group: str, field: str, **condition):
    """Per outer row (a branch, a category, a customer): the Sum of `field` over `rows`."""
    totals = (
        rows.filter(**{group: OuterRef("pk")}, **condition)
        .order_by()
        .values(group)
        .annotate(total=Sum(field, output_field=MONEY))
        .values("total")
    )
    return Coalesce(Subquery(totals, output_field=MONEY), Value(ZERO), output_field=MONEY)


def _hours(duration: timedelta | None) -> Decimal:
    seconds = Decimal((duration or NO_TIME).total_seconds())
    return (seconds / 3600).quantize(Decimal("0.1"), ROUND_HALF_UP)


def _percent(part: Decimal, whole: Decimal) -> Decimal | None:
    if whole <= 0:
        return None
    return (part * 100 / whole).quantize(Decimal("0.1"), ROUND_HALF_UP)


# ─── Revenue (Report.Revenue) ─────────────────────────────────────────────


@dataclass(frozen=True)
class _Revenue:
    lines: QuerySet
    invoices: QuerySet
    notes: QuerySet


def _revenue_sources(user, period: Period) -> _Revenue:
    """Invoices, their lines and the credit and debit notes issued in the period, in scope.
    Security deposits are never on an invoice (Pay.Deposit), so revenue excludes them."""
    branch = "booking__pickup_branch_id"
    return _Revenue(
        lines=scope_queryset(
            InvoiceLine.objects.filter(period.window("invoice__issue_date")),
            user,
            branch_lookup=f"invoice__{branch}",
        ),
        invoices=scope_queryset(
            Invoice.objects.filter(period.window("issue_date")), user, branch_lookup=branch
        ),
        notes=scope_queryset(
            InvoiceAdjustment.objects.filter(period.window("issued_at")),
            user,
            branch_lookup=f"invoice__{branch}",
        ),
    )


def _revenue_by(groups: QuerySet, path: str, sources: _Revenue) -> list[dict]:
    """Report.Revenue by branch or vehicle category; `path` leads from a booking to the group."""
    booking = f"booking__{path}"
    rows = groups.annotate(
        rental=_subtotal(sources.lines, f"invoice__{booking}", "amount", line_type=Line.RENTAL),
        add_ons=_subtotal(sources.lines, f"invoice__{booking}", "amount", line_type=Line.ADD_ON),
        discounts=_subtotal(
            sources.lines, f"invoice__{booking}", "amount", line_type=Line.DISCOUNT
        ),
        tax=_subtotal(sources.invoices, booking, "tax_amount"),
        invoiced=_subtotal(sources.invoices, booking, "total_amount"),
        debit_notes=_subtotal(
            sources.notes, f"invoice__{booking}", "amount", adjustment_type=Note.DEBIT_NOTE
        ),
        credit_notes=_subtotal(
            sources.notes, f"invoice__{booking}", "amount", adjustment_type=Note.CREDIT_NOTE
        ),
    ).annotate(net_revenue=F("invoiced") + F("debit_notes") - F("credit_notes"))
    fields = ("rental", "add_ons", "discounts", "tax", "debit_notes", "credit_notes")
    return [
        {"name": row.name_for_report, **{f: getattr(row, f) for f in (*fields, "net_revenue")}}
        for row in rows
    ]


def revenue_report(user, period: Period) -> dict:
    """Report.Revenue: rental and add-on income apart, discounts, tax, debit notes (R2's
    modify and extend, N2's return charges) and credit notes (refunds) as separate lines,
    from the invoices and their notes; by branch, vehicle category and payment method (the
    ledger). Refunds awaiting approval are shown apart and never counted (UC 13)."""
    sources = _revenue_sources(user, period)
    lines = sources.lines.aggregate(
        rental=_money("amount", line_type=Line.RENTAL),
        add_ons=_money("amount", line_type=Line.ADD_ON),
        discounts=_money("amount", line_type=Line.DISCOUNT),
    )
    invoices = sources.invoices.aggregate(
        invoices=Count("pk"), tax=_money("tax_amount"), invoiced=_money("total_amount")
    )
    notes = sources.notes.aggregate(
        debit_notes=_money("amount", adjustment_type=Note.DEBIT_NOTE),
        credit_notes=_money("amount", adjustment_type=Note.CREDIT_NOTE),
    )
    awaiting = scope_queryset(
        RefundRequest.objects.filter(
            period.window("requested_at"),
            status=RefundRequest.Status.PENDING_APPROVAL,
            original_payment__purpose="Rental",  # a deposit refund is not revenue either way
        ),
        user,
        branch_lookup="original_payment__booking__pickup_branch_id",
    ).aggregate(total=_money("amount"))["total"]
    dues = _customers(user).aggregate(total=_money("outstanding_due"))["total"]
    ledger = scope_queryset(
        LedgerEntry.objects.filter(
            period.window("timestamp"),
            entry_type__in=(Entry.CHARGE, Entry.REFUND, Entry.ADJUSTMENT),
        ),
        user,
        branch_lookup="booking__pickup_branch_id",
    )
    by_method = (
        ledger.order_by("method")
        .values("method")
        .annotate(
            charges=_money("amount", entry_type=Entry.CHARGE),
            # A refund the gateway later reports failed is reversed by an Adjustment (R1-P12).
            refunds=_money("amount", entry_type=Entry.REFUND)
            - _money(
                "amount", entry_type=Entry.ADJUSTMENT, reference_entry__entry_type=Entry.REFUND
            ),
        )
        .annotate(net=F("charges") - F("refunds"))
    )
    branches = scope_queryset(Branch.objects.order_by("branch_name"), user, branch_lookup="pk")
    categories = VehicleCategory.objects.order_by("name")
    return {
        "totals": {
            **lines,
            **invoices,
            **notes,
            "net_revenue": invoices["invoiced"] + notes["debit_notes"] - notes["credit_notes"],
            "refunds_awaiting_approval": awaiting,
            "outstanding_dues": dues,
        },
        "by_branch": _revenue_by(
            branches.annotate(name_for_report=F("branch_name")), "pickup_branch", sources
        ),
        "by_category": _revenue_by(
            categories.annotate(name_for_report=F("name")), "vehicle__category", sources
        ),
        "by_method": list(by_method),
    }


# ─── Utilisation (Report.Utilisation) ─────────────────────────────────────


def _report_time(report_type: str):
    """When the condition report of this type was recorded (rentals, read only)."""
    reports = ConditionReport.objects.filter(booking=OuterRef("pk"), report_type=report_type)
    return Subquery(reports.values("recorded_at")[:1], output_field=DateTimeField())


def _overlap(begin, finish, start: datetime, end: datetime):
    """How much of [begin, finish) lies inside [start, end); never below zero."""
    inside = ExpressionWrapper(
        Least(finish, Value(end)) - Greatest(begin, Value(start)), output_field=DurationField()
    )
    return Greatest(inside, Value(NO_TIME), output_field=DurationField())


def _day_starts(field: str):
    """A date column as the instant its local day begins (CO-6; PostgreSQL timezone())."""
    local = Func(F(field), template="%(expressions)s::timestamp", output_field=DateTimeField())
    return Func(Value(settings.TIME_ZONE), local, function="timezone", output_field=DateTimeField())


def _vehicle_hours(user, start: datetime, end: datetime) -> QuerySet:
    """Each vehicle in scope with its hours on rent, under maintenance and available."""
    on_rent = (
        Booking.objects.filter(vehicle=OuterRef("pk"), status__in=(Status.ACTIVE, Status.COMPLETED))
        .annotate(
            # The actual handover and return times where recorded, the booked times otherwise;
            # an Active rental past its return time is still on rent.
            out_at=Coalesce(
                _report_time(ConditionReport.ReportType.HANDOVER), F("pickup_datetime")
            ),
            back_at=Coalesce(
                _report_time(ConditionReport.ReportType.RETURN),
                Case(
                    When(status=Status.ACTIVE, then=Greatest(F("return_datetime"), Value(end))),
                    default=F("return_datetime"),
                ),
            ),
        )
        .filter(out_at__lt=end, back_at__gt=start)
        .order_by()
        .values("vehicle")
        .annotate(total=Sum(_overlap(F("out_at"), F("back_at"), start, end)))
        .values("total")
    )
    # Under Maintenance from the job's start (or its scheduled start) until it closed or was
    # cancelled (Maint.History; Appendix B: scheduled or started jobs hold the vehicle).
    maintained = (
        MaintenanceJob.objects.filter(vehicle=OuterRef("pk"))
        .filter(Q(started_at__isnull=False) | Q(scheduled_from__isnull=False))
        .annotate(
            begin=Coalesce("started_at", "scheduled_from"),
            finish=Coalesce("closed_at", "cancelled_at", Value(end), output_field=DateTimeField()),
        )
        .filter(begin__lt=end, finish__gt=start)
        .order_by()
        .values("vehicle")
        .annotate(total=Sum(_overlap(F("begin"), F("finish"), start, end)))
        .values("total")
    )
    in_fleet = Greatest(
        Value(end) - Greatest(Value(start), _day_starts("available_from")),
        Value(NO_TIME),
        output_field=DurationField(),
    )
    # shortcut: no retirement time is stored, so a Retired vehicle is left out of every period.
    vehicles = Vehicle.objects.exclude(status=Vehicle.Status.RETIRED)
    return (
        scope_queryset(vehicles, user, branch_lookup="home_branch_id")
        .annotate(
            rented=Coalesce(Subquery(on_rent, output_field=DurationField()), Value(NO_TIME)),
            maintenance=Coalesce(
                Subquery(maintained, output_field=DurationField()), Value(NO_TIME)
            ),
        )
        .annotate(
            available=Greatest(
                ExpressionWrapper(in_fleet - F("maintenance"), output_field=DurationField()),
                Value(NO_TIME),
                output_field=DurationField(),
            )
        )
    )


def _utilisation(rented: timedelta, available: timedelta) -> dict:
    rented_hours, available_hours = _hours(rented), _hours(available)
    return {
        "rented_hours": rented_hours,
        "available_hours": available_hours,
        "utilisation_percent": _percent(rented_hours, available_hours),
    }


def _utilisation_by(vehicles: QuerySet, field: str) -> list[dict]:
    rows = (
        vehicles.order_by(field)
        .values(field)
        .annotate(
            vehicles=Count("pk"), rented_total=Sum("rented"), available_total=Sum("available")
        )
    )
    return [
        {
            "name": row[field],
            "vehicles": row["vehicles"],
            **_utilisation(row["rented_total"], row["available_total"]),
        }
        for row in rows
    ]


LEAST_UTILISED = 5  # Report.Utilisation "identify the least utilised vehicles"


def utilisation_report(user, period: Period, *, now: datetime | None = None) -> dict:
    """Report.Utilisation: the percentage of available hours a vehicle was on rent, by
    vehicle, category and branch, and the least utilised vehicles. Available hours are the
    hours in the fleet (from its availability date) less the hours Under Maintenance
    (proposed R3-P1); the future part of a period is left out. Cancelled, No-show and
    unpaid bookings never count as rented."""
    now = now or timezone.now()
    start, end = period.start, min(period.end, max(now, period.start))
    vehicles = _vehicle_hours(user, start, end)
    by_vehicle = []
    for row in vehicles.select_related("category", "home_branch").order_by("registration_no"):
        by_vehicle.append(
            {
                "vehicle_id": row.pk,
                "registration_no": row.registration_no,
                "vehicle": f"{row.brand} {row.model}",
                "category": row.category.name,
                "branch": row.home_branch.branch_name,
                "maintenance_days": (_hours(row.maintenance) / 24).quantize(Decimal("0.1")),
                **_utilisation(row.rented, row.available),
            }
        )
    totals = vehicles.aggregate(
        vehicles=Count("pk"), rented_total=Sum("rented"), available_total=Sum("available")
    )
    measured = [row for row in by_vehicle if row["utilisation_percent"] is not None]
    return {
        "totals": {
            "name": "All vehicles",
            "vehicles": totals["vehicles"],
            **_utilisation(totals["rented_total"], totals["available_total"]),
        },
        "by_vehicle": by_vehicle,
        "by_category": _utilisation_by(vehicles, "category__name"),
        "by_branch": _utilisation_by(vehicles, "home_branch__branch_name"),
        "least_utilised": sorted(measured, key=lambda row: row["utilisation_percent"])[
            :LEAST_UTILISED
        ],
    }


# ─── Maintenance cost (UC 14; Maint.Record, Maint.History) ────────────────


def _maintenance_jobs(user, period: Period) -> QuerySet:
    """Jobs whose work record (service date) falls in the period, with their parts' cost."""
    parts = (
        PartUsed.objects.filter(job=OuterRef("pk"))
        .order_by()
        .values("job")
        .annotate(
            total=Sum(
                ExpressionWrapper(F("quantity") * F("unit_cost"), output_field=MONEY),
                output_field=MONEY,
            )
        )
        .values("total")
    )
    jobs = MaintenanceJob.objects.filter(
        service_date__gte=period.date_from, service_date__lte=period.date_to
    ).exclude(status=Job.Status.CANCELLED)
    return scope_queryset(jobs, user, branch_lookup="vehicle__home_branch_id").annotate(
        parts_cost=Coalesce(Subquery(parts, output_field=MONEY), Value(ZERO), output_field=MONEY)
    )


def _costs() -> dict:
    return {
        "jobs": Count("pk"),
        "labour": _money("labour_cost"),
        "parts": _money("parts_cost"),
        "total": _money("total_cost"),
    }


def maintenance_report(user, period: Period) -> dict:
    """UC 14 maintenance cost: labour, parts (PartUsed) and the job total (labour plus parts,
    computed by the server, M12; the workshop invoice is attached as a file, N3-P6), per
    vehicle and per job type, including the Preventive jobs the system raised (N3-P3)."""
    jobs = _maintenance_jobs(user, period)
    totals = jobs.aggregate(
        **_costs(), invoices_attached=Count("pk", filter=~Q(workshop_invoice=""))
    )
    by_vehicle = (
        jobs.values(
            "vehicle_id",
            "vehicle__registration_no",
            "vehicle__brand",
            "vehicle__model",
            "vehicle__home_branch__branch_name",
        )
        .annotate(**_costs())
        .order_by("-total", "vehicle__registration_no")
    )
    by_type = {
        row["job_type"]: row
        for row in jobs.order_by()
        .values("job_type")
        .annotate(**_costs(), automatic=Count("pk", filter=Q(reported_by__isnull=True)))
    }
    empty = {"jobs": 0, "automatic": 0, "labour": ZERO, "parts": ZERO, "total": ZERO}
    return {
        "totals": totals,
        "by_vehicle": [
            {
                "vehicle_id": row["vehicle_id"],
                "registration_no": row["vehicle__registration_no"],
                "vehicle": f"{row['vehicle__brand']} {row['vehicle__model']}",
                "branch": row["vehicle__home_branch__branch_name"],
                **{key: row[key] for key in ("jobs", "labour", "parts", "total")},
            }
            for row in by_vehicle
        ],
        # Every job type, so a type with no cost in the period still shows as nil.
        "by_job_type": [
            {**empty, **by_type.get(value, {}), "job_type": value} for value in Job.JobType.values
        ],
    }


# ─── Customers (UC 14) ────────────────────────────────────────────────────


def _customers(user) -> QuerySet:
    """Every customer for an Administrator; those who booked at the branch for a Manager."""
    if user.role == User.Role.ADMINISTRATOR:
        return Customer.objects.all()
    booked = scope_queryset(Booking.objects.all(), user, branch_lookup="pickup_branch_id")
    return Customer.objects.filter(pk__in=booked.values("customer_id"))


TOP_CUSTOMERS = 10


def customer_report(user, period: Period) -> dict:
    """UC 14 customers: new (registered in the period), active (a Confirmed, Active or
    Completed booking collected in the period; proposed R3-P5), the no-show count, the top
    customers by net revenue and every customer with an outstanding due (Pay.Dues, BR-4)."""
    customers = _customers(user)
    bookings = scope_queryset(
        Booking.objects.filter(period.window("pickup_datetime")),
        user,
        branch_lookup="pickup_branch_id",
    )
    counts = bookings.aggregate(
        active=Count(
            "customer",
            distinct=True,
            filter=Q(status__in=(Status.CONFIRMED, Status.ACTIVE, Status.COMPLETED)),
        ),
        no_shows=Count("pk", filter=Q(status=Status.NO_SHOW)),
    )
    dues = customers.filter(outstanding_due__gt=0)
    sources = _revenue_sources(user, period)
    customer = "booking__customer"
    top = (
        customers.select_related("user")
        .annotate(
            invoiced=_subtotal(sources.invoices, customer, "total_amount"),
            debit_notes=_subtotal(
                sources.notes, f"invoice__{customer}", "amount", adjustment_type=Note.DEBIT_NOTE
            ),
            credit_notes=_subtotal(
                sources.notes, f"invoice__{customer}", "amount", adjustment_type=Note.CREDIT_NOTE
            ),
            bookings_count=Coalesce(
                Subquery(
                    bookings.filter(customer=OuterRef("pk"))
                    .order_by()
                    .values("customer")
                    .annotate(n=Count("pk"))
                    .values("n")
                ),
                Value(0),
            ),
            no_shows=Coalesce(
                Subquery(
                    bookings.filter(customer=OuterRef("pk"), status=Status.NO_SHOW)
                    .order_by()
                    .values("customer")
                    .annotate(n=Count("pk"))
                    .values("n")
                ),
                Value(0),
            ),
        )
        .annotate(net_revenue=F("invoiced") + F("debit_notes") - F("credit_notes"))
        .filter(net_revenue__gt=0)
        .order_by("-net_revenue", "pk")[:TOP_CUSTOMERS]
    )
    due_totals = dues.aggregate(count=Count("pk"), total=_money("outstanding_due"))
    return {
        "totals": {
            "new": customers.filter(period.window("user__date_joined")).count(),
            **counts,
            "with_dues": due_totals["count"],
            "dues_total": due_totals["total"],
        },
        "top": [
            {
                "customer_id": row.pk,
                "name": row.user.name,
                "email": row.user.email,
                "bookings": row.bookings_count,
                "no_shows": row.no_shows,
                "net_revenue": row.net_revenue,
            }
            for row in top
        ],
        "with_dues": [
            {
                "customer_id": row.pk,
                "name": row.user.name,
                "email": row.user.email,
                "outstanding_due": row.outstanding_due,
            }
            for row in dues.select_related("user").order_by("-outstanding_due", "pk")
        ],
    }


# ─── Dashboard (Report.Dashboard) ─────────────────────────────────────────

OPEN_JOBS = (Job.Status.REPORTED, Job.Status.SCHEDULED, Job.Status.IN_PROGRESS)


def dashboard(user, *, now: datetime | None = None) -> dict:
    """Report.Dashboard: vehicles in each status, the collections and returns due today,
    the bookings and revenue of the current day, week (from Monday) and month, the overdue
    returns and the open maintenance jobs, for the actor's scope (Report.Access)."""
    now = now or timezone.now()
    today = timezone.localdate(now)
    periods = {
        "today": Period(today, today),
        "week": Period(today - timedelta(days=today.weekday()), today),
        "month": Period(today.replace(day=1), today),
    }
    by_status = dict(
        scope_queryset(Vehicle.objects.all(), user, branch_lookup="home_branch_id")
        .order_by()
        .values_list("status")
        .annotate(n=Count("pk"))
    )
    earliest = min(p.start for p in periods.values())  # the week may begin last month
    bookings = scope_queryset(
        Booking.objects.filter(
            Q(status__in=(Status.CONFIRMED, Status.ACTIVE)) | Q(confirmed_at__gte=earliest)
        ),
        user,
        branch_lookup="pickup_branch_id",
    )
    day = periods["today"]
    counts = bookings.aggregate(
        collections_today=Count(
            "pk", filter=Q(day.window("pickup_datetime"), status=Status.CONFIRMED)
        ),
        returns_today=Count("pk", filter=Q(day.window("return_datetime"), status=Status.ACTIVE)),
        overdue_returns=Count("pk", filter=Q(return_datetime__lt=now, status=Status.ACTIVE)),
        **{key: Count("pk", filter=p.window("confirmed_at")) for key, p in periods.items()},
    )
    invoices = scope_queryset(
        Invoice.objects.filter(issue_date__gte=earliest),
        user,
        branch_lookup="booking__pickup_branch_id",
    )
    invoiced = invoices.aggregate(
        **{key: _money("total_amount", p.window("issue_date")) for key, p in periods.items()}
    )
    notes = scope_queryset(
        InvoiceAdjustment.objects.filter(issued_at__gte=earliest),
        user,
        branch_lookup="invoice__booking__pickup_branch_id",
    )
    adjusted = notes.aggregate(
        **{
            key: _money("amount", p.window("issued_at"), adjustment_type=Note.DEBIT_NOTE)
            - _money("amount", p.window("issued_at"), adjustment_type=Note.CREDIT_NOTE)
            for key, p in periods.items()
        }
    )
    open_jobs = scope_queryset(
        MaintenanceJob.objects.filter(status__in=OPEN_JOBS),
        user,
        branch_lookup="vehicle__home_branch_id",
    ).count()
    return {
        "vehicles_by_status": [
            {"status": value, "count": by_status.get(value, 0)} for value in Vehicle.Status.values
        ],
        "collections_today": counts["collections_today"],
        "returns_today": counts["returns_today"],
        "overdue_returns": counts["overdue_returns"],
        "open_maintenance_jobs": open_jobs,
        "periods": [
            {"period": key, "bookings": counts[key], "revenue": invoiced[key] + adjusted[key]}
            for key in periods
        ],
    }
