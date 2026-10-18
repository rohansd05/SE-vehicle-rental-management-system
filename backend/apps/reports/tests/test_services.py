"""Reports computed on the fly (SRS 3.8 Report.Dashboard, Report.Utilisation, Report.Revenue,
Report.Access; Exp 2 UC 14 and its extension 1a; Exp 3 BranchManager.view_branch_reports()).

The period is 1 to 15 October 2026 in IST (30 Sep 18:30 to 15 Oct 18:30 UTC); "now" is
Sunday 18 October 2026, 12:00 IST.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from apps.accounts.models import Customer
from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchManagerFactory,
    CustomerFactory,
)
from apps.bookings.models import Booking
from apps.bookings.tests.factories import BookingFactory
from apps.fleet.models import Vehicle
from apps.fleet.tests.factories import BranchFactory, CarFactory, VehicleCategoryFactory
from apps.maintenance.models import MaintenanceJob
from apps.maintenance.tests.factories import MaintenanceJobFactory, PartUsedFactory
from apps.payments.models import InvoiceAdjustment, InvoiceLine, LedgerEntry, RefundRequest
from apps.payments.tests.factories import (
    CardPaymentFactory,
    InvoiceAdjustmentFactory,
    InvoiceFactory,
    InvoiceLineFactory,
    LedgerEntryFactory,
)
from apps.pricing.models import Tariff
from apps.pricing.tests.factories import TariffFactory
from apps.rentals.models import ConditionReport
from apps.rentals.tests.factories import ConditionReportFactory
from apps.reports import services
from apps.reports.services import Period

pytestmark = pytest.mark.django_db

IST = ZoneInfo("Asia/Kolkata")
NOW = datetime(2026, 10, 18, 6, 30, tzinfo=UTC)
PERIOD = Period(date(2026, 10, 1), date(2026, 10, 15))
D = Decimal
S = Booking.Status
Line = InvoiceLine.LineType
Note = InvoiceAdjustment.AdjustmentType
Entry = LedgerEntry.EntryType


def ist(day: int, hour: int = 10, month: int = 10) -> datetime:
    return datetime(2026, month, day, hour, tzinfo=IST)


@pytest.fixture(autouse=True)
def _now():
    with freeze_time(NOW):
        yield


@pytest.fixture
def andheri():
    return BranchFactory(branch_name="Andheri")


@pytest.fixture
def bandra():
    return BranchFactory(branch_name="Bandra")


@pytest.fixture
def admin():
    return AdministratorFactory().user


@pytest.fixture
def manager(andheri):
    return BranchManagerFactory(branch=andheri).user


def car(branch, category="Hatchback", **kwargs):
    kwargs.setdefault("available_from", date(2026, 1, 1))
    return CarFactory(home_branch=branch, category=VehicleCategoryFactory(name=category), **kwargs)


def rental(vehicle, out: datetime, back: datetime, status=S.COMPLETED, **kwargs) -> Booking:
    tariff = Tariff.objects.filter(vehicle_category=vehicle.category).first()
    return BookingFactory(
        vehicle=vehicle,
        tariff=tariff or TariffFactory(vehicle_category=vehicle.category),
        pickup_datetime=out,
        return_datetime=back,
        status=status,
        **kwargs,
    )


def invoice(booking, issued: datetime, rental_amount: str, add_on="0", discount="0"):
    """An invoice as Book.Done issues it: rental, add-on and discount lines, tax at 18%."""
    taxable = D(rental_amount) + D(add_on) + D(discount)
    tax = (taxable * D("0.18")).quantize(D("0.01"))
    issued_invoice = InvoiceFactory(
        booking=booking, issue_date=issued, tax_amount=tax, total_amount=taxable + tax
    )
    for line_type, amount in (
        (Line.RENTAL, rental_amount),
        (Line.ADD_ON, add_on),
        (Line.DISCOUNT, discount),
    ):
        if D(amount):
            InvoiceLineFactory(
                invoice=issued_invoice, line_type=line_type, unit_price=D(amount), amount=D(amount)
            )
    return issued_invoice


def note(invoice_, kind, amount: str, issued: datetime):
    return InvoiceAdjustmentFactory(
        invoice=invoice_,
        adjustment_type=kind,
        amount=D(amount),
        issued_at=issued,
        adjustment_number=f"{'DN' if kind == Note.DEBIT_NOTE else 'CN'}-{amount}-{issued:%d%H}",
    )


# ─── Revenue (Report.Revenue) ─────────────────────────────────────────────


@pytest.fixture
def revenue(andheri, bandra):
    """Andheri: invoiced 1298.00 (rental 1000, add-on 200, discount -100, tax 198), a debit
    note of 236.00 and a credit note of 118.00. Bandra: invoiced 2360.00, and a refund of
    500.00 waiting for approval. Plus rows outside the period and deposits."""
    at_andheri = rental(car(andheri), ist(5), ist(7))
    at_bandra = rental(car(bandra, "SUV"), ist(6), ist(8))
    first = invoice(at_andheri, ist(4), "1000.00", add_on="200.00", discount="-100.00")
    second = invoice(at_bandra, ist(6), "2000.00")
    note(first, Note.DEBIT_NOTE, "236.00", ist(8))  # e.g. N2's return charges
    note(first, Note.CREDIT_NOTE, "118.00", ist(9))  # e.g. R1's refund of a rental part
    invoice(rental(car(andheri), ist(16), ist(17)), ist(16), "9999.00")  # after the period
    note(second, Note.CREDIT_NOTE, "50.00", ist(16))  # after the period
    LedgerEntryFactory(
        booking=at_andheri, entry_type=Entry.CHARGE, amount=D("1298.00"), timestamp=ist(4)
    )
    LedgerEntryFactory(
        booking=at_andheri, entry_type=Entry.CHARGE, amount=D("236.00"), timestamp=ist(8)
    )
    refund = LedgerEntryFactory(
        booking=at_andheri, entry_type=Entry.REFUND, amount=D("118.00"), timestamp=ist(9)
    )
    LedgerEntryFactory(  # Pay.Deposit: deposits are never revenue
        booking=at_andheri, entry_type=Entry.DEPOSIT_HOLD, amount=D("5000.00"), timestamp=ist(4)
    )
    LedgerEntryFactory(
        booking=at_bandra,
        entry_type=Entry.CHARGE,
        amount=D("2360.00"),
        method=LedgerEntry.Method.ONLINE,
        timestamp=ist(6),
    )
    paid = CardPaymentFactory(booking=at_bandra, amount=D("2360.00"))
    deposit = CardPaymentFactory(booking=at_bandra, amount=D("5000.00"), purpose="Security Deposit")
    for payment, amount, key in ((paid, "500.00", "r-1"), (deposit, "5000.00", "r-2")):
        RefundRequest.objects.create(
            original_payment=payment,
            amount=D(amount),
            reason="Goodwill",
            status=RefundRequest.Status.PENDING_APPROVAL,
            requested_at=ist(10),
            idempotency_key=key,
        )
    Customer.objects.filter(pk=at_andheri.customer_id).update(outstanding_due=D("850.00"))
    return {"refund_entry": refund, "andheri_booking": at_andheri}


def test_revenue_shows_each_line_apart_and_nets_the_notes(admin, revenue):
    totals = services.revenue_report(admin, PERIOD)["totals"]
    assert totals == {
        "invoices": 2,
        "rental": D("3000.00"),
        "add_ons": D("200.00"),
        "discounts": D("-100.00"),
        "tax": D("558.00"),
        "invoiced": D("3658.00"),
        "debit_notes": D("236.00"),
        "credit_notes": D("118.00"),
        "net_revenue": D("3776.00"),  # invoiced + debit notes - credit notes
        "refunds_awaiting_approval": D("500.00"),  # shown apart, never counted
        "outstanding_dues": D("850.00"),
    }
    assert all(isinstance(value, D) for key, value in totals.items() if key != "invoices")


def test_revenue_by_branch_category_and_payment_method(admin, revenue):
    report = services.revenue_report(admin, PERIOD)
    by_branch = {row["name"]: row for row in report["by_branch"]}
    assert by_branch["Andheri"] == {
        "name": "Andheri",
        "rental": D("1000.00"),
        "add_ons": D("200.00"),
        "discounts": D("-100.00"),
        "tax": D("198.00"),
        "debit_notes": D("236.00"),
        "credit_notes": D("118.00"),
        "net_revenue": D("1416.00"),
    }
    assert by_branch["Bandra"]["net_revenue"] == D("2360.00")
    by_category = {row["name"]: row["net_revenue"] for row in report["by_category"]}
    assert (by_category["Hatchback"], by_category["SUV"]) == (D("1416.00"), D("2360.00"))
    # The ledger, deposits excluded: charges less refunds by payment method.
    assert report["by_method"] == [
        {"method": "Card", "charges": D("1534.00"), "refunds": D("118.00"), "net": D("1416.00")},
        {"method": "Online", "charges": D("2360.00"), "refunds": D("0.00"), "net": D("2360.00")},
    ]


def test_a_refund_the_gateway_reversed_is_no_longer_a_refund(admin, revenue):
    """R1-P12: an Adjustment entry referencing a Refund entry reverses it."""
    entry = revenue["refund_entry"]
    LedgerEntryFactory(
        booking=entry.booking,
        entry_type=Entry.ADJUSTMENT,
        amount=entry.amount,
        reference_entry=entry,
        timestamp=ist(11),
    )
    card = services.revenue_report(admin, PERIOD)["by_method"][0]
    assert (card["refunds"], card["net"]) == (D("0.00"), D("1534.00"))


def test_a_branch_manager_sees_only_their_branchs_revenue(manager, revenue):
    """UC 14 extension 1a, Report.Access."""
    report = services.revenue_report(manager, PERIOD)
    assert report["totals"]["net_revenue"] == D("1416.00")
    assert report["totals"]["refunds_awaiting_approval"] == D("0.00")  # Bandra's
    assert report["totals"]["outstanding_dues"] == D("850.00")  # their customer's
    assert [row["name"] for row in report["by_branch"]] == ["Andheri"]
    assert [row["method"] for row in report["by_method"]] == ["Card"]
    assert services.scope_label(manager) == "Andheri"


def test_an_empty_period_reports_zero_not_none(admin):
    totals = services.revenue_report(admin, PERIOD)["totals"]
    assert totals["net_revenue"] == D("0.00") and totals["invoices"] == 0


# ─── Utilisation (Report.Utilisation) ─────────────────────────────────────


def by_reg(report) -> dict:
    return {row["registration_no"]: row for row in report["by_vehicle"]}


def test_utilisation_uses_the_actual_handover_and_return_times(admin, andheri):
    vehicle = car(andheri)
    booking = rental(vehicle, ist(5), ist(7))  # booked for 48 hours
    ConditionReportFactory(booking=booking, recorded_at=ist(5, 11))
    ConditionReportFactory(
        booking=booking, report_type=ConditionReport.ReportType.RETURN, recorded_at=ist(7, 9)
    )
    row = by_reg(services.utilisation_report(admin, PERIOD))[vehicle.registration_no]
    assert row["rented_hours"] == D("46.0")
    assert row["available_hours"] == D("360.0")  # 15 days
    assert row["utilisation_percent"] == D("12.8")


def test_utilisation_falls_back_to_the_booked_times(admin, andheri):
    vehicle = car(andheri)
    rental(vehicle, ist(5), ist(7))
    assert by_reg(services.utilisation_report(admin, PERIOD))[vehicle.registration_no][
        "rented_hours"
    ] == D("48.0")


def test_only_the_part_inside_the_period_counts(admin, andheri):
    vehicle = car(andheri)
    rental(vehicle, ist(30, 22, month=9), ist(2, 22))  # starts before 1 October 00:00
    assert by_reg(services.utilisation_report(admin, PERIOD))[vehicle.registration_no][
        "rented_hours"
    ] == D("46.0")


@pytest.mark.parametrize(
    "status", [S.CANCELLED, S.NO_SHOW, S.DRAFT, S.PENDING_PAYMENT, S.CONFIRMED]
)
def test_cancelled_no_show_and_uncollected_bookings_are_never_rented(admin, andheri, status):
    vehicle = car(andheri)
    rental(vehicle, ist(5), ist(7), status=status)
    row = by_reg(services.utilisation_report(admin, PERIOD))[vehicle.registration_no]
    assert row["rented_hours"] == D("0.0") and row["utilisation_percent"] == D("0.0")


def test_an_overdue_rental_is_on_rent_until_the_end_of_the_period(admin, andheri):
    vehicle = car(andheri)
    booking = rental(vehicle, ist(14), ist(15), status=S.ACTIVE)
    ConditionReportFactory(booking=booking, recorded_at=ist(14))
    row = by_reg(services.utilisation_report(admin, PERIOD))[vehicle.registration_no]
    assert row["rented_hours"] == D("38.0")  # 14 Oct 10:00 to 16 Oct 00:00 IST


def test_under_maintenance_days_come_from_the_job_history_and_are_not_available(admin, andheri):
    vehicle = car(andheri)
    rental(vehicle, ist(5), ist(7))
    MaintenanceJobFactory(  # started 13 Oct 10:00, closed 14 Oct 10:00
        vehicle=vehicle,
        status=MaintenanceJob.Status.COMPLETED,
        started_at=ist(13),
        closed_at=ist(14),
    )
    MaintenanceJobFactory(vehicle=vehicle)  # only Reported: the vehicle stayed on the road
    MaintenanceJobFactory(  # scheduled for 15 Oct 12:00, still open at the end of the period
        vehicle=vehicle,
        status=MaintenanceJob.Status.SCHEDULED,
        scheduled_from=ist(15, 12),
        scheduled_to=ist(15, 20),
    )
    row = by_reg(services.utilisation_report(admin, PERIOD))[vehicle.registration_no]
    assert row["maintenance_days"] == D("1.5")  # 24 hours + 12 hours
    assert row["available_hours"] == D("324.0")  # 360 - 36
    assert row["utilisation_percent"] == D("14.8")  # 48 of 324


def test_a_vehicle_counts_from_its_availability_date(admin, andheri):
    vehicle = car(andheri, available_from=date(2026, 10, 11))
    row = by_reg(services.utilisation_report(admin, PERIOD))[vehicle.registration_no]
    assert row["available_hours"] == D("120.0")  # 11 Oct 00:00 to 16 Oct 00:00 IST


def test_the_future_part_of_a_period_is_left_out(admin, andheri):
    vehicle = car(andheri)
    report = services.utilisation_report(admin, Period(date(2026, 10, 18), date(2026, 10, 31)))
    assert by_reg(report)[vehicle.registration_no]["available_hours"] == D("12.0")  # to 12:00


def test_a_retired_vehicle_is_left_out(admin, andheri):
    retired = car(andheri, status=Vehicle.Status.RETIRED)
    assert retired.registration_no not in by_reg(services.utilisation_report(admin, PERIOD))


def test_utilisation_by_category_and_branch_and_the_least_utilised(admin, andheri, bandra):
    busy = car(andheri)  # 48 of 360 hours
    rental(busy, ist(5), ist(7))
    idle = car(andheri, available_from=date(2026, 10, 11))  # 0 of 120
    suv = car(bandra, "SUV")  # 72 of 360
    rental(suv, ist(9), ist(12))
    report = services.utilisation_report(admin, PERIOD)
    assert report["by_category"] == [
        {
            "name": "Hatchback",
            "vehicles": 2,
            "rented_hours": D("48.0"),
            "available_hours": D("480.0"),
            "utilisation_percent": D("10.0"),
        },
        {
            "name": "SUV",
            "vehicles": 1,
            "rented_hours": D("72.0"),
            "available_hours": D("360.0"),
            "utilisation_percent": D("20.0"),
        },
    ]
    assert [(row["name"], row["utilisation_percent"]) for row in report["by_branch"]] == [
        ("Andheri", D("10.0")),
        ("Bandra", D("20.0")),
    ]
    assert report["totals"]["utilisation_percent"] == D("14.3")  # 120 of 840
    assert [row["registration_no"] for row in report["least_utilised"]] == [
        idle.registration_no,
        busy.registration_no,
        suv.registration_no,
    ]


def test_a_branch_manager_sees_only_their_branchs_vehicles(manager, andheri, bandra):
    mine, theirs = car(andheri), car(bandra)
    report = services.utilisation_report(manager, PERIOD)
    assert set(by_reg(report)) == {mine.registration_no}
    assert theirs.registration_no not in by_reg(report)
    assert [row["name"] for row in report["by_branch"]] == ["Andheri"]


# ─── Maintenance cost ─────────────────────────────────────────────────────


@pytest.fixture
def maintenance(andheri, bandra):
    """Andheri: a Corrective job, labour 800.00 and parts 1700.00, with a workshop invoice.
    Bandra: a Preventive job the system raised (N3-P3), labour 500.00 and parts 300.00."""
    corrective = MaintenanceJobFactory(
        vehicle=car(andheri),
        status=MaintenanceJob.Status.COMPLETED,
        service_date=date(2026, 10, 5),
        labour_cost=D("800.00"),
        total_cost=D("2500.00"),
        workshop_invoice="maintenance/invoices/demo.pdf",
    )
    PartUsedFactory(job=corrective, unit_cost=D("1450.00"))
    PartUsedFactory(job=corrective, part_name="Brake fluid", quantity=D("2"), unit_cost=D("125.00"))
    preventive = MaintenanceJobFactory(
        vehicle=car(bandra, "SUV"),
        job_type=MaintenanceJob.JobType.PREVENTIVE,
        status=MaintenanceJob.Status.IN_PROGRESS,
        reported_by=None,
        service_date=date(2026, 10, 10),
        labour_cost=D("500.00"),
        total_cost=D("800.00"),
    )
    PartUsedFactory(job=preventive, part_name="Oil filter", unit_cost=D("300.00"))
    earlier = MaintenanceJobFactory(  # before the period
        vehicle=corrective.vehicle,
        status=MaintenanceJob.Status.COMPLETED,
        service_date=date(2026, 9, 30),
        labour_cost=D("100.00"),
        total_cost=D("100.00"),
    )
    MaintenanceJobFactory(vehicle=earlier.vehicle, status=MaintenanceJob.Status.CANCELLED)
    return corrective, preventive


def test_maintenance_cost_per_vehicle_and_job_type(admin, maintenance):
    corrective, preventive = maintenance
    report = services.maintenance_report(admin, PERIOD)
    assert report["totals"] == {
        "jobs": 2,
        "labour": D("1300.00"),
        "parts": D("2000.00"),
        "total": D("3300.00"),
        "invoices_attached": 1,
    }
    assert [(row["registration_no"], row["total"]) for row in report["by_vehicle"]] == [
        (corrective.vehicle.registration_no, D("2500.00")),
        (preventive.vehicle.registration_no, D("800.00")),
    ]
    assert report["by_vehicle"][0]["parts"] == D("1700.00")
    by_type = {row["job_type"]: row for row in report["by_job_type"]}
    assert set(by_type) == set(MaintenanceJob.JobType.values)  # every type, nil included
    assert by_type["Preventive"] == {
        "job_type": "Preventive",
        "jobs": 1,
        "automatic": 1,
        "labour": D("500.00"),
        "parts": D("300.00"),
        "total": D("800.00"),
    }
    assert by_type["Inspection"]["jobs"] == 0 and by_type["Inspection"]["total"] == D("0.00")


def test_a_branch_manager_sees_only_their_branchs_maintenance_cost(manager, maintenance):
    report = services.maintenance_report(manager, PERIOD)
    assert report["totals"]["total"] == D("2500.00")
    assert len(report["by_vehicle"]) == 1


# ─── Customers ────────────────────────────────────────────────────────────


@pytest.fixture
def customers(andheri, bandra, revenue):
    """revenue's Andheri customer (net 1416.00, due 850.00) and Bandra customer (2360.00);
    one more Bandra customer with a no-show; one new Andheri customer who cancelled."""
    andheri_customer = revenue["andheri_booking"].customer
    bandra_booking = Booking.objects.get(pickup_branch=bandra, status=S.COMPLETED)
    no_show = CustomerFactory()
    rental(car(bandra), ist(9), ist(10), status=S.NO_SHOW, customer=no_show)
    newcomer = CustomerFactory()
    rental(car(andheri), ist(12), ist(13), status=S.CANCELLED, customer=newcomer)
    joined = {andheri_customer: ist(3), bandra_booking.customer: ist(1, month=9)}
    joined |= {no_show: ist(2, month=9), newcomer: ist(10)}
    for customer, when in joined.items():
        type(customer.user).objects.filter(pk=customer.user_id).update(date_joined=when)
    return andheri_customer, bandra_booking.customer, no_show, newcomer


def test_customers_new_active_top_dues_and_no_shows(admin, customers):
    andheri_customer, bandra_customer, no_show, newcomer = customers
    report = services.customer_report(admin, PERIOD)
    assert report["totals"] == {
        "new": 2,  # the Andheri customer and the newcomer joined in October
        "active": 2,  # a completed rental each
        "no_shows": 1,
        "with_dues": 1,
        "dues_total": D("850.00"),
    }
    assert [(row["customer_id"], row["net_revenue"], row["bookings"]) for row in report["top"]] == [
        (bandra_customer.pk, D("2360.00"), 1),
        (andheri_customer.pk, D("1416.00"), 1),
    ]
    assert [(row["customer_id"], row["outstanding_due"]) for row in report["with_dues"]] == [
        (andheri_customer.pk, D("850.00"))
    ]
    assert report["with_dues"][0]["email"] == andheri_customer.user.email


def test_a_customers_no_shows_are_counted_in_the_top_list(admin, customers):
    _, bandra_customer, _, _ = customers
    rental(
        car(BranchFactory(branch_name="Bandra")),
        ist(11),
        ist(12),
        status=S.NO_SHOW,
        customer=bandra_customer,
    )
    top = services.customer_report(admin, PERIOD)["top"]
    assert (top[0]["bookings"], top[0]["no_shows"]) == (2, 1)


def test_a_branch_manager_sees_only_customers_who_booked_at_their_branch(manager, customers):
    andheri_customer, _, _, newcomer = customers
    report = services.customer_report(manager, PERIOD)
    assert report["totals"] == {
        "new": 2,
        "active": 1,
        "no_shows": 0,
        "with_dues": 1,
        "dues_total": D("850.00"),
    }
    assert [row["customer_id"] for row in report["top"]] == [andheri_customer.pk]


# ─── Dashboard (Report.Dashboard) ─────────────────────────────────────────


@pytest.fixture
def day(andheri, bandra):
    """Sunday 18 October: the week began on Monday 12 October."""
    mine, other = car(andheri), car(bandra, status=Vehicle.Status.ON_RENT)
    car(andheri, status=Vehicle.Status.UNDER_MAINTENANCE)
    car(andheri, status=Vehicle.Status.RETIRED)
    rental(mine, ist(18, 15), ist(19, 15), status=S.CONFIRMED, confirmed_at=ist(18, 8))
    rental(car(andheri), ist(19), ist(20), status=S.CONFIRMED, confirmed_at=ist(13))  # tomorrow
    rental(other, ist(17), ist(18, 18), status=S.ACTIVE, confirmed_at=ist(2))  # due back today
    rental(
        car(andheri), ist(16), ist(17), status=S.ACTIVE, confirmed_at=ist(10, month=9)
    )  # overdue
    for vehicle, status in (
        (mine, MaintenanceJob.Status.REPORTED),
        (other, MaintenanceJob.Status.SCHEDULED),
        (mine, MaintenanceJob.Status.COMPLETED),
    ):
        MaintenanceJobFactory(vehicle=vehicle, status=status)
    earlier = {"confirmed_at": ist(1, month=9)}  # booked last month, invoiced this month
    today = invoice(rental(car(andheri), ist(1), ist(2), **earlier), ist(18, 9), "1000.00")
    invoice(rental(car(bandra), ist(1), ist(2), **earlier), ist(13), "2000.00")
    invoice(rental(car(andheri), ist(1), ist(2), **earlier), ist(2), "3000.00")
    note(today, Note.CREDIT_NOTE, "100.00", ist(18, 11))


def figures(report) -> dict:
    return {row["period"]: (row["bookings"], row["revenue"]) for row in report["periods"]}


def test_the_dashboard_counts_everything_report_dashboard_asks_for(admin, day):
    report = services.dashboard(admin)
    statuses = {row["status"]: row["count"] for row in report["vehicles_by_status"]}
    assert statuses["Available"] == 6 and statuses["On Rent"] == 1
    assert statuses["Under Maintenance"] == 1 and statuses["Retired"] == 1
    assert statuses["Unsafe"] == 0
    assert (report["collections_today"], report["returns_today"]) == (1, 1)
    assert (report["overdue_returns"], report["open_maintenance_jobs"]) == (1, 2)
    assert figures(report) == {
        "today": (1, D("1080.00")),  # 1180.00 invoiced less a credit note of 100.00 (tax in)
        "week": (2, D("3440.00")),
        "month": (3, D("6980.00")),
    }


def test_a_branch_manager_dashboard_covers_only_their_branch(manager, day):
    report = services.dashboard(manager)
    statuses = {row["status"]: row["count"] for row in report["vehicles_by_status"]}
    assert statuses["On Rent"] == 0 and statuses["Under Maintenance"] == 1
    assert (report["collections_today"], report["returns_today"]) == (1, 0)
    assert (report["overdue_returns"], report["open_maintenance_jobs"]) == (1, 1)
    assert figures(report)["month"] == (2, D("4620.00"))  # 1180 + 3540 - 100
