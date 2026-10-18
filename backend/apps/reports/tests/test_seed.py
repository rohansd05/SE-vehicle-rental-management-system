"""`seed_demo --reports` (apps/reports/seed.py): every report has data, idempotent, and the
default demo (accounts, jobs 1 to 3, N3's job count, the reset) is unchanged."""

from datetime import timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.accounts.models import Customer, Licence, LicenceCategory, User
from apps.bookings.models import Booking
from apps.core.tests.test_seed_demo import EXPECTED
from apps.maintenance.models import MaintenanceJob
from apps.maintenance.seed import DEMO_PROBLEMS
from apps.payments.models import Invoice, InvoiceAdjustment, LedgerEntry
from apps.reports import services
from apps.reports.seed import CUSTOMER_EMAIL, JOB_PROBLEM
from apps.reports.services import Period

pytestmark = pytest.mark.django_db

D = Decimal
# What --reports adds to the default demo (apps/core/tests/test_seed_demo.py EXPECTED):
# reports@vrms.test, and rating@vrms.test (Module R4, bookings/seed_ratings.py).
REPORTS_ADD = {User: 2, Customer: 2, Licence: 2, LicenceCategory: 4}
INVOICES = 12  # the reports customer's 10 and the rating customer's 2


def _seed(*args):
    call_command("seed_demo", *args, stdout=StringIO())


def _last_three_months() -> Period:
    today = timezone.localdate()
    return Period(today - timedelta(days=90), today)


def _counts() -> dict:
    return {model: model.objects.count() for model in EXPECTED}


def test_the_default_demo_loads_no_report_data():
    _seed()
    assert not User.objects.filter(email=CUSTOMER_EMAIL).exists()
    assert MaintenanceJob.objects.count() == 3  # N3's expectation is unchanged


def test_the_reports_demo_gives_every_report_data():
    _seed("--reports")
    admin = User.objects.get(email="admin@vrms.test")
    period = _last_three_months()

    revenue = services.revenue_report(admin, period)
    totals = revenue["totals"]
    assert totals["invoices"] == INVOICES
    assert totals["add_ons"] > 0 and totals["discounts"] < 0 and totals["tax"] > 0
    assert totals["debit_notes"] == D("472.00")  # the return charges (N2)
    assert totals["credit_notes"] > 0  # the no-show refund (BR-8)
    assert totals["refunds_awaiting_approval"] > 0  # the payments demo's (R1)
    assert totals["outstanding_dues"] == D("850.00")  # payments@vrms.test
    assert {row["name"] for row in revenue["by_branch"] if row["net_revenue"] > 0} == {
        "Andheri",
        "Bandra",
    }
    assert {row["method"] for row in revenue["by_method"]} == {"Card", "Online", "Cash"}

    utilisation = services.utilisation_report(admin, period)
    rented = {row["name"]: row["rented_hours"] for row in utilisation["by_branch"]}
    assert rented["Andheri"] > 0 and rented["Bandra"] > 0

    maintenance = services.maintenance_report(admin, period)
    preventive = next(r for r in maintenance["by_job_type"] if r["job_type"] == "Preventive")
    assert (preventive["parts"], preventive["total"]) == (D("2150.00"), D("2750.00"))

    customers = services.customer_report(admin, period)
    assert customers["top"][0]["email"] == CUSTOMER_EMAIL
    assert customers["totals"]["no_shows"] == 1 and customers["totals"]["new"] >= 1

    manager = User.objects.get(email="manager@vrms.test")  # Andheri (UC 14 extension 1a)
    assert [row["name"] for row in services.revenue_report(manager, period)["by_branch"]] == [
        "Andheri"
    ]


def test_the_reports_demo_follows_the_state_machine_and_bills_as_book_done_does():
    _seed("--reports")
    bookings = Booking.objects.filter(customer__user__email=CUSTOMER_EMAIL)
    assert sorted(bookings.values_list("status", flat=True)) == ["Completed"] * 9 + ["No-show"]
    for booking in bookings.select_related("invoice"):
        assert booking.invoice.total_amount == booking.total_amount
        lines = sum((line.amount for line in booking.invoice.lines.all()), D("0"))
        assert lines + booking.invoice.tax_amount == booking.total_amount
        assert booking.booking_reference.startswith("VRMS-")
    assert not LedgerEntry.objects.filter(
        booking__in=bookings, entry_type=LedgerEntry.EntryType.DEPOSIT_HOLD
    ).exclude(amount__in=[D("5000.00"), D("2000.00")])
    job = MaintenanceJob.objects.get(reported_problem=JOB_PROBLEM)
    assert (job.status, job.closed_by.email) == ("Completed", "tech@vrms.test")


def test_the_reports_demo_is_idempotent_and_keeps_the_rest_of_the_demo():
    _seed("--reports")
    _seed("--reports")
    expected = {model: n + REPORTS_ADD.get(model, 0) for model, n in EXPECTED.items()}
    assert _counts() == expected
    assert Invoice.objects.count() == INVOICES and InvoiceAdjustment.objects.count() == 2
    assert MaintenanceJob.objects.count() == 4  # demo jobs 1 to 3, and this one
    assert MaintenanceJob.objects.filter(reported_problem__in=DEMO_PROBLEMS).count() == 3
    for email in ["customer@vrms.test", "staff@vrms.test", "admin@vrms.test", CUSTOMER_EMAIL]:
        assert User.objects.get(email=email).check_password("Demo@1234")


def test_reset_refuses_once_the_append_only_report_data_is_loaded():
    _seed("--reports")
    before = _counts()
    with pytest.raises(CommandError):
        _seed("--reset")
    assert _counts() == before
