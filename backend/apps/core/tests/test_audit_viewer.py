"""The audit log viewer (Fleet.Audit, SE-10; Module N3): read-only, filtered, an
Administrator reads every entry and a Branch Manager only their own branch's."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.factories import (
    DEFAULT_PASSWORD,
    AdministratorFactory,
    BranchManagerFactory,
    BranchStaffFactory,
    CustomerFactory,
    MaintenanceTechnicianFactory,
    UserFactory,
)
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings.tests.factories import BookingFactory
from apps.core.audit import record_audit
from apps.core.models import AuditLog
from apps.fleet.tests.factories import BranchFactory, CarFactory
from apps.maintenance.tests.factories import MaintenanceJobFactory
from apps.payments import services as payments
from apps.payments.models import RefundRequest
from apps.payments.tests.factories import (
    CardPaymentFactory,
    InvoiceAdjustmentFactory,
    InvoiceFactory,
    LedgerEntryFactory,
)
from apps.rentals import services as rentals
from apps.rentals.services import Flag
from apps.rentals.tests.factories import (
    ConditionReportFactory,
    active_booking,
    checklist,
    readings,
    ready_booking,
    return_kwargs,
)

pytestmark = pytest.mark.django_db

LIST = reverse("core:audit-log")
FILTERS = reverse("core:audit-filters")


def _user(role):
    return {
        "customer": lambda: CustomerFactory().user,
        "staff": lambda: BranchStaffFactory().user,
        "technician": lambda: MaintenanceTechnicianFactory().user,
        "admin": lambda: AdministratorFactory().user,
        "manager": lambda: BranchManagerFactory().user,
        "anonymous": lambda: None,
    }[role]()


@pytest.mark.parametrize("url", [LIST, FILTERS], ids=["audit-log", "audit-filters"])
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
def test_endpoint_permission(api_client, url, role, expected):
    user = _user(role)
    client = authenticated_client(user) if user else api_client
    assert client.get(url).status_code == expected


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_the_log_cannot_be_written_through_the_api(method):
    """Fleet.Audit: not editable by any user, the Administrator included."""
    record_audit(None, "Create", entity_label="fleet.Branch", entity_id=1)
    client = authenticated_client(AdministratorFactory().user)
    assert getattr(client, method)(LIST, {}, format="json").status_code == 405
    assert AuditLog.objects.count() == 1


# ─── The Administrator: every entry, filtered ─────────────────────────────


@pytest.fixture
def admin_client():
    return authenticated_client(AdministratorFactory(user__name="Asha Admin").user)


def _ids(response) -> list[str]:
    return [entry["entity_id"] for entry in response.json()["results"]]


def test_an_administrator_reads_every_entry_newest_first_with_both_values(admin_client):
    actor = UserFactory(name="Ravi Rao", email="ravi@vrms.test")
    record_audit(
        actor, "Update", entity_label="fleet.Vehicle", entity_id=7, before={"a": 1}, after={"a": 2}
    )
    record_audit(None, "Create", entity_label="pricing.Tariff", entity_id=8, after={"x": "1.00"})

    results = admin_client.get(LIST).json()["results"]

    assert [r["entity_id"] for r in results] == ["8", "7"]
    assert results[0]["actor"] is None  # a system action
    assert results[1]["actor"] == {
        "id": actor.pk,
        "name": "Ravi Rao",
        "email": "ravi@vrms.test",
        "role": "CUSTOMER",
    }
    assert (results[1]["before"], results[1]["after"]) == ({"a": 1}, {"a": 2})
    assert results[1]["timestamp"]


def test_filters_by_actor_action_entity_and_date(admin_client):
    ravi = UserFactory(name="Ravi Rao", email="ravi@vrms.test")
    record_audit(ravi, "Update", entity_label="fleet.Vehicle", entity_id=1)
    record_audit(ravi, "Create", entity_label="pricing.Tariff", entity_id=2)
    record_audit(None, "Update", entity_label="fleet.Vehicle", entity_id=3)
    old = AuditLog(
        action="Update",
        entity_type="fleet.Vehicle",
        entity_id="4",
        timestamp=timezone.now() - timedelta(days=10),
    )
    old.save()

    assert _ids(admin_client.get(LIST, {"actor": "ravi@"})) == ["2", "1"]
    assert _ids(admin_client.get(LIST, {"actor": "Rao"})) == ["2", "1"]
    assert _ids(admin_client.get(LIST, {"actor": "system"})) == ["4", "3"]
    assert _ids(admin_client.get(LIST, {"action": "Create"})) == ["2"]
    assert _ids(admin_client.get(LIST, {"entity_type": "fleet.Vehicle"})) == ["4", "3", "1"]
    assert _ids(admin_client.get(LIST, {"entity_type": "fleet.Vehicle", "entity_id": "3"})) == ["3"]
    today = timezone.localdate().isoformat()
    assert _ids(admin_client.get(LIST, {"date_from": today, "date_to": today})) == ["3", "2", "1"]
    ten_days_ago = (timezone.localdate() - timedelta(days=10)).isoformat()
    assert _ids(admin_client.get(LIST, {"date_to": ten_days_ago})) == ["4"]


def test_a_reversed_date_range_is_refused(admin_client):
    response = admin_client.get(LIST, {"date_from": "2026-10-10", "date_to": "2026-10-01"})
    assert response.status_code == 400 and "date_to" in response.json()


def test_the_filter_lists_hold_every_action_and_entity_type(admin_client):
    for action, label in [
        ("Update", "fleet.Vehicle"),
        ("Refund Approved", "payments.RefundRequest"),
    ]:
        record_audit(None, action, entity_label=label, entity_id=1)
    record_audit(None, "Update", entity_label="fleet.Vehicle", entity_id=2)
    assert admin_client.get(FILTERS).json() == {
        "actions": ["Refund Approved", "Update"],
        "entity_types": ["fleet.Vehicle", "payments.RefundRequest"],
    }


# ─── The Branch Manager: their own branch only ────────────────────────────

# One record per entity type the scoping covers, made at the branch given.
RECORDS = {
    "bookings.Booking": lambda branch: BookingFactory(vehicle=CarFactory(home_branch=branch)),
    "fleet.Car": lambda branch: CarFactory(home_branch=branch),
    "fleet.Branch": lambda branch: branch,
    "maintenance.MaintenanceJob": lambda branch: MaintenanceJobFactory(
        vehicle=CarFactory(home_branch=branch)
    ),
    "rentals.ConditionReport": lambda branch: ConditionReportFactory(
        booking=BookingFactory(vehicle=CarFactory(home_branch=branch), status="Active")
    ),
    "payments.CardPayment": lambda branch: CardPaymentFactory(
        booking=BookingFactory(vehicle=CarFactory(home_branch=branch))
    ),
    "payments.Invoice": lambda branch: InvoiceFactory(
        booking=BookingFactory(vehicle=CarFactory(home_branch=branch))
    ),
    "payments.InvoiceAdjustment": lambda branch: InvoiceAdjustmentFactory(
        invoice=InvoiceFactory(booking=BookingFactory(vehicle=CarFactory(home_branch=branch)))
    ),
    "payments.LedgerEntry": lambda branch: LedgerEntryFactory(
        booking=BookingFactory(vehicle=CarFactory(home_branch=branch))
    ),
    "payments.RefundRequest": lambda branch: RefundRequest.objects.create(
        original_payment=CardPaymentFactory(
            booking=BookingFactory(vehicle=CarFactory(home_branch=branch))
        ),
        amount=Decimal("100.00"),
        reason="Test",
        status=RefundRequest.Status.PENDING_APPROVAL,
        idempotency_key=f"audit-test-{branch.pk}",
    ),
}


@pytest.mark.parametrize("label", list(RECORDS))
def test_a_branch_manager_sees_their_branchs_records_only(label):
    own, other = BranchFactory(), BranchFactory()
    mine, theirs = RECORDS[label](own), RECORDS[label](other)
    record_audit(None, "Update", mine)
    record_audit(None, "Update", theirs)
    manager = BranchManagerFactory(branch=own).user

    results = authenticated_client(manager).get(LIST, {"entity_type": label}).json()["results"]

    assert [r["entity_id"] for r in results] == [str(mine.pk)]


def test_a_branch_manager_sees_what_their_branchs_people_did():
    own = BranchFactory()
    staff = BranchStaffFactory(branch=own).user
    manager = BranchManagerFactory(branch=own).user
    record_audit(staff, "Licence Verified", entity_label="accounts.Licence", entity_id=1)
    record_audit(manager, "Login", entity_label="accounts.User", entity_id=manager.pk)
    record_audit(BranchStaffFactory().user, "Login", entity_label="accounts.User", entity_id=99)
    record_audit(None, "Due Recorded", entity_label="accounts.Customer", entity_id=5)

    response = authenticated_client(manager).get(LIST)

    assert {(r["action"], r["entity_id"]) for r in response.json()["results"]} == {
        ("Licence Verified", "1"),
        ("Login", str(manager.pk)),
    }
    options = authenticated_client(manager).get(FILTERS).json()
    assert options["actions"] == ["Licence Verified", "Login"]


def test_a_return_with_override_and_flag_is_in_both_audit_views():
    """N2's events (return, settlement, Return.Flag, the supervisor override) and the
    payments entries it makes through R1, for the Administrator and the Branch Manager."""
    booking = active_booking()
    manager = BranchManagerFactory(branch=booking.pickup_branch).user
    staff = BranchStaffFactory(branch=booking.pickup_branch).user
    far = readings(odometer_reading=13500)  # above the plausibility limit
    total = rentals.return_quote(booking, staff, far).settlement.total
    rentals.return_vehicle(
        booking.pk,
        staff,
        request=RequestFactory().post("/api/v1/rentals/returns/"),
        **return_kwargs(
            readings=far,
            expected_total=total,
            override={"email": manager.email, "password": DEFAULT_PASSWORD, "reason": "Long trip"},
            flag=Flag(problem="Clutch slipping", severity="High", unfit=True),
        ),
    )
    expected = {
        "Condition Report Signed",  # the signed return report (Return.Checklist)
        "Odometer Override Approved",  # Return.Odometer, the supervisor as actor
        "Odometer Recorded",
        "Create",  # Return.Flag: the maintenance job
        "Booking Status Changed",  # Return.Complete
        "Vehicle Status Changed",
        "Payment Captured",  # Return.Settle through R1
        "Ledger Entries Recorded",
        "Due Recorded",  # charges above the deposit (Pay.Dues), by the branch staff
    }
    for user in (AdministratorFactory().user, manager):
        actions = set(authenticated_client(user).get(FILTERS).json()["actions"])
        assert expected <= actions, expected - actions
    override = (
        authenticated_client(manager)
        .get(LIST, {"action": "Odometer Override Approved"})
        .json()["results"]
    )
    assert override[0]["actor"]["email"] == manager.email
    assert override[0]["after"]["reason"] == "Long trip"
    elsewhere = authenticated_client(BranchManagerFactory().user).get(LIST).json()
    assert elsewhere["count"] == 0


def test_a_cash_payment_and_a_handover_are_in_the_branch_managers_view():
    """R1's cash recorded (BR-9) and N1's handover, through their real services."""
    booking = ready_booking(cash_on_collection=True)
    staff = BranchStaffFactory(branch=booking.pickup_branch)
    payments.record_cash(
        BookingFactory(vehicle=CarFactory(home_branch=booking.pickup_branch)),
        staff=staff,
        rental_amount=Decimal("1800.00"),
        deposit_amount=Decimal("5000.00"),
        idempotency_key="audit-cash",
    )
    rentals.handover_vehicle(booking.pk, staff.user, **checklist())
    manager = BranchManagerFactory(branch=booking.pickup_branch).user

    actions = set(authenticated_client(manager).get(FILTERS).json()["actions"])

    assert {"Cash Payment Recorded", "Condition Report Signed", "Booking Status Changed"} <= actions
