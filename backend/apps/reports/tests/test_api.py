"""Reports API (UC 14 View Reports; Report.Access; SE-4): an explicit permission class on
every endpoint, Administrators and Branch Managers only; the period; Decimal strings
(CO-6); a fixed number of queries however much data there is (aggregation in the database).
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from freezegun import freeze_time

from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchManagerFactory,
    BranchStaffFactory,
    CustomerFactory,
    MaintenanceTechnicianFactory,
)
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings.models import Booking
from apps.bookings.tests.factories import BookingFactory
from apps.fleet.tests.factories import BranchFactory, CarFactory
from apps.maintenance.models import MaintenanceJob
from apps.maintenance.tests.factories import MaintenanceJobFactory, PartUsedFactory
from apps.payments.models import InvoiceAdjustment, LedgerEntry
from apps.payments.tests.factories import (
    InvoiceAdjustmentFactory,
    InvoiceFactory,
    InvoiceLineFactory,
    LedgerEntryFactory,
)
from apps.rentals.tests.factories import ConditionReportFactory
from apps.reports import views

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 18, 6, 30, tzinfo=UTC)  # 12:00 IST
NAMES = ["summary", "utilisation", "revenue", "maintenance", "customers"]
PERIOD = {"date_from": "2026-10-01", "date_to": "2026-10-15"}


@pytest.fixture(autouse=True)
def _now():
    with freeze_time(NOW):
        yield


def url(name: str) -> str:
    return reverse(f"reports:{name}")


def _user(role):
    return {
        "customer": lambda: CustomerFactory().user,
        "staff": lambda: BranchStaffFactory().user,
        "technician": lambda: MaintenanceTechnicianFactory().user,
        "admin": lambda: AdministratorFactory().user,
        "manager": lambda: BranchManagerFactory().user,
        "anonymous": lambda: None,
    }[role]()


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("anonymous", 401),
        ("customer", 403),
        ("staff", 403),
        ("technician", 403),
        ("admin", 200),
        ("manager", 200),
    ],
)
def test_only_administrators_and_branch_managers_read_reports(api_client, name, role, expected):
    """Report.Access: "No other user class shall have access to revenue or cost reports"."""
    user = _user(role)
    client = authenticated_client(user) if user else api_client
    assert client.get(url(name), PERIOD).status_code == expected


@pytest.mark.parametrize(
    "view",
    [
        views.DashboardView,
        views.UtilisationReportView,
        views.RevenueReportView,
        views.MaintenanceReportView,
        views.CustomerReportView,
    ],
)
def test_every_report_view_declares_its_permission_class(view):
    assert view.permission_classes == [views.REPORT_READERS]


@pytest.fixture
def admin_client():
    return authenticated_client(AdministratorFactory().user)


def test_the_default_period_is_this_month_to_today(admin_client):
    body = admin_client.get(url("revenue")).json()
    assert (body["date_from"], body["date_to"], body["scope"]) == (
        "2026-10-01",
        "2026-10-18",
        "All branches",
    )


def test_a_period_ending_before_it_starts_is_refused_on_its_field(admin_client):
    response = admin_client.get(
        url("utilisation"), {"date_from": "2026-10-15", "date_to": "2026-10-01"}
    )
    assert response.status_code == 400
    assert response.json() == {"date_to": ["The end of the period cannot be before its start."]}


def test_a_date_that_is_not_a_date_is_refused(admin_client):
    response = admin_client.get(url("customers"), {"date_from": "2026-13-01"})
    assert response.status_code == 400 and "date_from" in response.json()


def test_money_and_hours_are_decimal_strings(admin_client):
    revenue = admin_client.get(url("revenue"), PERIOD).json()
    assert revenue["totals"]["net_revenue"] == "0.00"
    utilisation = admin_client.get(url("utilisation"), PERIOD).json()
    assert utilisation["totals"]["available_hours"] == "0.0"
    summary = admin_client.get(url("summary")).json()
    assert [row["period"] for row in summary["periods"]] == ["today", "week", "month"]
    assert summary["periods"][0]["revenue"] == "0.00"


def test_a_branch_managers_report_names_their_branch():
    manager = BranchManagerFactory(branch=BranchFactory(branch_name="Powai")).user
    body = authenticated_client(manager).get(url("maintenance"), PERIOD).json()
    assert body["scope"] == "Powai"
    assert authenticated_client(manager).get(url("summary")).json()["scope"] == "Powai"


# ─── Query counts ─────────────────────────────────────────────────────────


def _rentals(branch, count: int) -> None:
    """`count` returned rentals at `branch`, each invoiced with a note, a ledger entry,
    condition reports and a maintenance job with parts, all inside the period."""
    for index in range(count):
        out = datetime(2026, 10, 2 + index, 4, 30, tzinfo=UTC)
        vehicle = CarFactory(home_branch=branch, available_from=date(2026, 1, 1))
        booking = BookingFactory(
            vehicle=vehicle,
            pickup_datetime=out,
            return_datetime=out + timedelta(days=1),
            status=Booking.Status.COMPLETED,
            confirmed_at=out - timedelta(days=1),
        )
        ConditionReportFactory(booking=booking, recorded_at=out)
        invoice = InvoiceFactory(booking=booking, issue_date=out)
        InvoiceLineFactory(invoice=invoice)
        InvoiceAdjustmentFactory(
            invoice=invoice,
            adjustment_type=InvoiceAdjustment.AdjustmentType.DEBIT_NOTE,
            issued_at=out,
            adjustment_number=f"DN-{invoice.pk}",
        )
        LedgerEntryFactory(booking=booking, entry_type=LedgerEntry.EntryType.CHARGE, timestamp=out)
        job = MaintenanceJobFactory(
            vehicle=vehicle,
            status=MaintenanceJob.Status.COMPLETED,
            service_date=out.date(),
            started_at=out + timedelta(days=2),
            closed_at=out + timedelta(days=3),
            labour_cost=Decimal("100.00"),
            total_cost=Decimal("1550.00"),
        )
        PartUsedFactory(job=job)


def _queries(client, name: str) -> int:
    with CaptureQueriesContext(connection) as captured:
        assert client.get(url(name), PERIOD).status_code == 200
    return len(captured.captured_queries)


# Request authentication included. An Administrator's scope needs no branch lookup.
EXPECTED_QUERIES = {"summary": 6, "utilisation": 5, "revenue": 9, "maintenance": 4, "customers": 6}


@pytest.mark.parametrize("name", NAMES)
def test_each_report_runs_a_fixed_number_of_queries(admin_client, name):
    """The aggregation runs in the database: ten times the data, the same queries."""
    branches = [BranchFactory(branch_name="Andheri"), BranchFactory(branch_name="Bandra")]
    for branch in branches:
        _rentals(branch, 1)
    few = _queries(admin_client, name)
    for branch in branches:
        _rentals(branch, 10)
    assert (few, _queries(admin_client, name)) == (EXPECTED_QUERIES[name],) * 2
