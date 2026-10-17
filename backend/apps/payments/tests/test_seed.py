"""Demo payments data from seed_demo: a due, a cash collection and a refund awaiting approval."""

from datetime import datetime, time, timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone
from freezegun import freeze_time

from apps.accounts.models import Customer, User
from apps.bookings.models import Booking
from apps.core.management.commands.seed_demo import DEMO_ACCOUNTS
from apps.maintenance.models import MaintenanceJob
from apps.payments import seed
from apps.payments.models import RefundRequest

pytestmark = pytest.mark.django_db

DEMO_DAY = timezone.make_aware(datetime(2026, 10, 17, 11, 0))


def _seed(*args):
    call_command("seed_demo", *args, stdout=StringIO())


@freeze_time(DEMO_DAY)
def test_the_demo_customer_owes_a_due_and_has_a_cash_booking_and_a_pending_refund():
    _seed()
    customer = Customer.objects.get(user__email=seed.CUSTOMER_EMAIL)
    assert customer.user.check_password("Demo@1234")
    assert customer.outstanding_due == Decimal("850.00")

    cash = Booking.objects.get(vehicle__registration_no=seed.CASH_CAR)
    assert (cash.status, cash.cash_on_collection) == (Booking.Status.PENDING_PAYMENT, True)
    assert cash.pickup_branch.branch_name == "Andheri"
    pickup = timezone.localtime(cash.pickup_datetime)
    assert (pickup.date(), pickup.time()) == (DEMO_DAY.date() + timedelta(days=1), time(10, 0))
    assert cash.hold_expires_at == cash.pickup_datetime + timedelta(hours=2)
    assert not cash.payments.exists()

    refund = RefundRequest.objects.get(
        original_payment__booking__vehicle__registration_no=seed.REFUND_CAR
    )
    assert refund.status == RefundRequest.Status.PENDING_APPROVAL
    assert refund.amount == Decimal("8260.00")  # 2 SUV days of 3500.00 plus 18% tax
    assert refund.original_payment.booking.status == Booking.Status.CONFIRMED


def test_seeding_again_adds_nothing_and_keeps_the_other_demo_data():
    with freeze_time(DEMO_DAY):
        _seed()
        counts = (
            Booking.objects.count(),
            RefundRequest.objects.count(),
            MaintenanceJob.objects.count(),
        )
        _seed()
    assert (
        Booking.objects.count(),
        RefundRequest.objects.count(),
        MaintenanceJob.objects.count(),
    ) == counts
    assert Customer.objects.get(user__email=seed.CUSTOMER_EMAIL).outstanding_due == Decimal(
        "850.00"
    )
    for account in DEMO_ACCOUNTS:
        assert User.objects.get(email=account.email).check_password("Demo@1234")
    assert counts[2] == 3  # the three maintenance demo jobs are untouched


def test_reset_removes_the_demo_payments_data_and_loads_it_again():
    with freeze_time(DEMO_DAY):
        _seed()
        _seed("--reset")
    assert Booking.objects.filter(vehicle__registration_no__in=seed.REGISTRATIONS).count() == 2
    assert RefundRequest.objects.count() == 1
