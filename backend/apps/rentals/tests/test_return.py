"""Return Vehicle services (SRS 3.3 Return.*; Exp 2 use case 8; Exp 4 sequence 2; Exp 5
return fork/join; DFD process 6). Money moves only through R1's services, for real
against the mock gateway."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.test import RequestFactory
from django.utils import timezone
from freezegun import freeze_time

from apps.accounts.models import Customer
from apps.accounts.tests.factories import (
    DEFAULT_PASSWORD,
    AdministratorFactory,
    BranchManagerFactory,
    BranchStaffFactory,
    LicenceCategoryFactory,
    LicenceFactory,
)
from apps.bookings import services as bookings
from apps.bookings.models import Booking
from apps.bookings.states import IllegalBookingTransition, complete_booking
from apps.bookings.tests.factories import BookingFactory
from apps.core.models import AuditLog
from apps.fleet.models import Vehicle
from apps.maintenance.models import MaintenanceJob
from apps.notifications.models import Notification
from apps.notifications.templates import render
from apps.payments.models import CashPayment, InvoiceAdjustment, LedgerEntry, RefundRequest
from apps.payments.tests.factories import InvoiceFactory
from apps.rentals import services
from apps.rentals.models import ConditionReport
from apps.rentals.notification_templates import SAMPLE_CONTEXT
from apps.rentals.tests.factories import active_booking, readings, return_kwargs

pytestmark = pytest.mark.django_db

D = Decimal
Status = Booking.Status


@pytest.fixture(autouse=True)
def _media_in_tmp(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def staff_at(booking):
    return BranchStaffFactory(branch=booking.pickup_branch).user


def return_now(booking, user=None, **overrides) -> ConditionReport:
    user = user or staff_at(booking)
    return services.return_vehicle(booking.pk, user, **return_kwargs(**overrides))


def charges(booking) -> list[LedgerEntry]:
    """The Charge entries written at return (rental charges have a payment)."""
    return list(booking.ledger_entries.filter(entry_type="Charge", payment__isnull=True))


def _request():
    return RequestFactory().post("/api/v1/rentals/returns/")


# ─── The basic flow (UC 8 steps 1 to 6) ───────────────────────────────────


class TestReturnVehicle:
    def test_an_on_time_return_completes_and_refunds_the_whole_deposit(self, outbox):
        booking = active_booking()
        staff = staff_at(booking)
        kwargs = return_kwargs()
        report = services.return_vehicle(booking.pk, staff, **kwargs)

        booking.refresh_from_db()
        assert booking.status == Status.COMPLETED  # Return.Complete
        assert booking.returned_at == kwargs["readings"].returned_at  # the actual return time
        assert booking.distance_travelled == 200
        vehicle = Vehicle.objects.get(pk=booking.vehicle_id)
        assert vehicle.status == Vehicle.Status.AVAILABLE
        assert vehicle.odometer == 12200  # DE-3, which feeds BR-15

        report = ConditionReport.objects.get(pk=report.pk)
        assert report.report_type == "Return" and report.is_signed_in_db
        assert report.recorded_by.user == staff
        assert [p.caption for p in report.photos.all()] == ["Front", "Rear", "Left", "Right"]
        assert report.accessories == [{"name": "Child seat", "quantity": 1}]
        assert report.charges == []

        refund = services.deposit_refund(booking)  # BR-14, through refund_deposit()
        assert refund.status == RefundRequest.Status.ISSUED and refund.amount == D("5000.00")
        assert refund.refund_due_by is not None
        assert charges(booking) == []
        assert booking.ledger_entries.filter(entry_type="Capture").count() == 2

        actions = set(AuditLog.objects.filter(actor=staff).values_list("action", flat=True))
        assert {
            "Condition Report Signed",
            "Odometer Recorded",
            "Vehicle Status Changed",
            "Booking Status Changed",
            "Payment Captured",
            "Refund Requested",
        } <= actions
        assert AuditLog.objects.verify_chain()

        # Exp 5 fork: the settlement statement to the customer, through Celery.
        statement = Notification.objects.get(template="return_settlement")
        assert statement.status == Notification.Status.SENT
        (email,) = [m for m in outbox if "settlement" in m.subject]
        assert booking.booking_reference in email.subject
        assert "You travelled 200 km." in email.body
        assert "INR 5,000.00 is refunded" in email.body

    def test_late_over_the_allowance_and_short_of_fuel_each_a_line_and_a_debit_note(self):
        booking = active_booking(due_in=-timedelta(hours=3))
        invoice = InvoiceFactory(booking=booking)  # issued at 18%
        report = return_now(
            booking,
            readings=readings(odometer_reading=12400, fuel_level=D("75.00")),
            expected_total=D("4071.00"),
        )
        kinds = [(line["kind"], line["amount"]) for line in report.charges]
        assert kinds == [
            ("late_return", "450.00"),  # BR-10: 2 h 59 min late, 3 hours at 150.00
            ("excess_km", "1800.00"),  # BR-11: 150 km over 250 at 12.00
            ("fuel_shortfall", "1200.00"),  # BR-12: 10 L at 100.00 plus 20%
            ("tax", "621.00"),
        ]
        assert [entry.amount for entry in charges(booking)] == [
            D("450.00"),
            D("1800.00"),
            D("1200.00"),
            D("621.00"),
        ]
        (note,) = InvoiceAdjustment.objects.filter(invoice=invoice)  # Pay.Invoice: never an edit
        assert note.adjustment_type == "Debit Note" and note.amount == D("4071.00")
        assert note.tax_amount == D("621.00") and "(BR-11)" in note.reason
        assert services.deposit_refund(booking).amount == D("929.00")

    def test_charges_above_the_deposit_become_a_due(self):
        booking = active_booking()
        damage = [{"description": "Bumper", "amount": D("6000.00"), "justification": "Cracked"}]
        return_now(
            booking,
            readings=readings(damage_charges=damage),
            expected_total=D("7080.00"),
        )
        assert services.deposit_refund(booking) is None  # the whole deposit is used
        customer = Customer.objects.get(pk=booking.customer_id)
        assert customer.outstanding_due == D("2080.00")  # Pay.Dues, then BR-4 refuses bookings
        assert AuditLog.objects.filter(action="Due Recorded").count() == 1

    def test_a_refund_above_the_approval_limit_waits_for_an_administrator(self, settings):
        settings.REFUND_AUTO_APPROVAL_LIMIT = D("1000.00")
        booking = active_booking()
        report = return_now(booking)
        record = services.settlement_record(booking, report)
        assert record["refund_status"] == RefundRequest.Status.PENDING_APPROVAL  # UC 13
        assert record["refund"] == D("5000.00")
        email = Notification.objects.get(template="return_settlement")
        assert "waiting for approval" in email.context["balance"]

    def test_a_cash_deposit_is_paid_back_in_cash_by_the_staff_member(self):
        booking = active_booking(cash=True)
        staff = staff_at(booking)
        report = return_now(booking, staff)
        refund = services.deposit_refund(booking)
        assert refund.status == RefundRequest.Status.ISSUED
        cash = CashPayment.objects.get(pk=refund.refund_id)
        assert cash.received_by.user == staff and cash.customer_acknowledged_at
        assert booking.ledger_entries.filter(entry_type="Capture", payment__purpose="Rental")
        record = services.settlement_record(booking, report)
        assert record["refund_paid_out_by"] == staff.name
        email = Notification.objects.get(template="return_settlement")
        assert "paid back to you in cash" in email.context["balance"]

    def test_settling_twice_never_charges_twice(self):
        """Pay.Idempotent: a double click on Settle returns the first result."""
        booking = active_booking()
        staff = staff_at(booking)
        damage = [{"description": "Bumper", "amount": D("6000.00"), "justification": "Cracked"}]
        first = return_now(
            booking, staff, readings=readings(damage_charges=damage), expected_total=D("7080.00")
        )
        entries = LedgerEntry.objects.count()
        second = return_now(
            booking, staff, readings=readings(damage_charges=damage), expected_total=D("7080.00")
        )
        assert second.pk == first.pk
        assert LedgerEntry.objects.count() == entries
        assert ConditionReport.objects.filter(booking=booking).count() == 2
        assert Customer.objects.get(pk=booking.customer_id).outstanding_due == D("2080.00")

    def test_changed_charges_change_nothing(self):
        booking = active_booking()
        with pytest.raises(services.ReturnError) as raised:
            return_now(booking, readings=readings(odometer_reading=12400))  # 1,770.00 now due
        assert raised.value.code == "settlement_changed" and raised.value.status == 409
        assert "INR 2,124.00" in str(raised.value)
        booking.refresh_from_db()
        assert booking.status == Status.ACTIVE
        assert services.return_report(booking) is None
        assert not booking.ledger_entries.filter(entry_type="Capture").exists()

    def test_a_failure_after_the_money_rolls_everything_back(self, monkeypatch):
        booking = active_booking()

        def fail(*args, **kwargs):
            raise RuntimeError("status service down")

        monkeypatch.setattr(services, "update_status", fail)
        with pytest.raises(RuntimeError):
            return_now(booking)
        booking.refresh_from_db()
        assert booking.status == Status.ACTIVE
        assert services.return_report(booking) is None
        assert not RefundRequest.objects.exists()
        assert not booking.ledger_entries.filter(entry_type="Capture").exists()

    def test_staff_of_another_branch_cannot_take_it_back(self):
        booking = active_booking()
        with pytest.raises(services.ReturnError) as raised:
            return_now(booking, BranchStaffFactory().user)
        assert raised.value.code == "other_branch"

    def test_an_unsafe_flag_raised_during_the_rental_stays(self):
        booking = active_booking()
        Vehicle.objects.filter(pk=booking.vehicle_id).update(status=Vehicle.Status.UNSAFE)
        return_now(booking)
        assert Vehicle.objects.get(pk=booking.vehicle_id).status == Vehicle.Status.UNSAFE
        assert Booking.objects.get(pk=booking.pk).status == Status.COMPLETED


# ─── Only an Active booking can be returned ───────────────────────────────


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (Status.CANCELLED, "booking_cancelled"),
        (Status.NO_SHOW, "booking_no_show"),
        (Status.PENDING_PAYMENT, "booking_not_paid"),
        (Status.CONFIRMED, "not_handed_over"),
        (Status.COMPLETED, "already_returned"),
        (Status.DRAFT, "booking_not_active"),
    ],
)
def test_only_an_active_booking_can_be_returned(status, code):
    booking = BookingFactory(status=status)
    staff = staff_at(booking)
    with pytest.raises(services.ReturnRefusedError) as quoted:
        services.return_quote(booking, staff, readings())
    assert [r.code for r in quoted.value.refusals] == [code]
    with pytest.raises(services.ReturnRefusedError) as returned:
        services.return_vehicle(booking.pk, staff, **return_kwargs())
    assert [r.code for r in returned.value.refusals] == [code]
    assert Booking.objects.get(pk=booking.pk).status == status


def test_an_active_booking_without_a_handover_report_is_refused():
    booking = BookingFactory(status=Status.ACTIVE)
    assert [r.code for r in services.return_refusals(booking)] == ["no_handover_report"]
    assert services.deposit_refund(booking) is None  # nothing was paid


# ─── Return.Checklist and Return.Odometer ─────────────────────────────────


class TestChecklist:
    def test_a_reading_below_the_handover_is_rejected_for_correction(self):
        booking = active_booking()
        with pytest.raises(services.ReturnError) as raised:
            return_now(booking, readings=readings(odometer_reading=11999))
        assert (raised.value.code, raised.value.field) == ("odometer_lower", "odometer_reading")
        assert services.return_report(booking) is None

    @pytest.mark.parametrize("shift", [timedelta(minutes=5), -timedelta(days=2)])
    def test_the_return_time_lies_between_the_handover_and_now(self, shift):
        booking = active_booking()
        returned_at = timezone.now() + shift
        with pytest.raises(services.ReturnError) as raised:
            services.return_quote(booking, staff_at(booking), readings(returned_at=returned_at))
        assert raised.value.field == "returned_at"

    def test_a_missing_accessory_is_charged_at_the_cost_entered(self):
        booking = active_booking()
        missing = [{"name": "Child seat", "quantity": 1, "cost": D("1500.00")}]
        quote = services.return_quote(
            booking, staff_at(booking), readings(missing_accessories=missing)
        )
        assert quote.accessories_returned == []
        assert [(line.kind, line.amount) for line in quote.settlement.lines] == [
            ("accessory", D("1500.00")),
            ("tax", D("270.00")),
        ]
        assert quote.settlement.lines[0].description == "Accessory not returned: Child seat × 1"

    def test_an_accessory_never_issued_cannot_be_missing(self):
        booking = active_booking()
        missing = [{"name": "Helmet", "quantity": 1, "cost": D("100.00")}]
        with pytest.raises(services.ReturnError) as raised:
            services.return_quote(booking, staff_at(booking), readings(missing_accessories=missing))
        assert raised.value.field == "missing_accessories"

    def test_damage_is_charged_with_its_justification(self):
        booking = active_booking()
        damage = [
            {"description": "Dent", "amount": D("1000.00"), "justification": "Not at handover"}
        ]
        report = return_now(
            booking, readings=readings(damage_charges=damage), expected_total=D("1180.00")
        )
        assert report.charges[0] == {
            "kind": "damage",
            "description": "Damage: Dent",
            "amount": "1000.00",
            "justification": "Not at handover",
        }
        assert charges(booking)[0].note == "Damage: Dent"

    def test_a_shortfall_needs_the_vehicles_fuel_capacity(self):
        booking = active_booking()
        Vehicle.objects.filter(pk=booking.vehicle_id).update(fuel_capacity=None)
        booking = Booking.objects.get(pk=booking.pk)
        with pytest.raises(services.ReturnError) as raised:
            services.return_quote(booking, staff_at(booking), readings(fuel_level=D("50.00")))
        assert (raised.value.code, raised.value.status) == ("fuel_capacity_unknown", 409)


class TestOdometerOverride:
    """Return.Odometer: an implausible distance needs a supervisor and a reason."""

    FAR = 13500  # 1,500 km in under a day; the limit is 1,000 km a started day

    def _return(self, booking, override):
        staff = staff_at(booking)
        far = readings(odometer_reading=self.FAR)
        total = services.return_quote(booking, staff, far).settlement.total
        return services.return_vehicle(
            booking.pk,
            staff,
            request=_request(),
            **return_kwargs(readings=far, expected_total=total, override=override),
        )

    def test_the_quote_says_an_override_is_needed(self):
        booking = active_booking()
        quote = services.return_quote(
            booking, staff_at(booking), readings(odometer_reading=self.FAR)
        )
        assert quote.override_required and quote.plausibility_limit == 1000

    def test_without_a_supervisor_it_is_refused(self):
        booking = active_booking()
        with pytest.raises(services.ReturnError) as raised:
            self._return(booking, None)
        assert (raised.value.code, raised.value.field) == ("override_required", "override_reason")

    @pytest.mark.parametrize("who", ["wrong-password", "staff", "other-branch-manager"])
    def test_only_a_supervisor_of_the_branch_can_approve(self, who):
        booking = active_booking()
        user = {
            "wrong-password": lambda: BranchManagerFactory(branch=booking.pickup_branch).user,
            "staff": lambda: BranchStaffFactory(branch=booking.pickup_branch).user,
            "other-branch-manager": lambda: BranchManagerFactory().user,
        }[who]()
        password = "nope" if who == "wrong-password" else DEFAULT_PASSWORD
        override = {"email": user.email, "password": password, "reason": "Long trip"}
        with pytest.raises(services.ReturnError) as raised:
            self._return(booking, override)
        assert (raised.value.code, raised.value.field) == ("override_refused", "override_password")

    @pytest.mark.parametrize("role", ["manager", "admin"])
    def test_a_branch_manager_or_an_administrator_approves_with_a_reason(self, role):
        booking = active_booking()
        if role == "manager":
            supervisor = BranchManagerFactory(branch=booking.pickup_branch).user
        else:
            supervisor = AdministratorFactory().user
        override = {"email": supervisor.email, "password": DEFAULT_PASSWORD, "reason": "Goa trip"}
        report = self._return(booking, override)
        assert report.odometer_override_by == supervisor
        assert report.odometer_override_reason == "Goa trip"
        assert AuditLog.objects.get(action="Odometer Override Approved").actor == supervisor
        assert Booking.objects.get(pk=booking.pk).distance_travelled == 1500


# ─── Return.Flag (UC 8 extension 3a; sequence 2's opt fragment) ───────────


@pytest.mark.parametrize(
    ("unfit", "vehicle_status"),
    [(True, Vehicle.Status.UNDER_MAINTENANCE), (False, Vehicle.Status.AVAILABLE)],
)
def test_flagging_raises_a_job_and_an_unfit_vehicle_goes_under_maintenance(unfit, vehicle_status):
    booking = active_booking()
    staff = staff_at(booking)
    flag = services.Flag("Brakes squeal", MaintenanceJob.Severity.HIGH, unfit=unfit)
    report = return_now(booking, staff, flag=flag)
    job = MaintenanceJob.objects.get(vehicle=booking.vehicle)  # Maint.Create, via report_job()
    assert job.status == MaintenanceJob.Status.REPORTED
    assert job.job_type == MaintenanceJob.JobType.CORRECTIVE
    assert job.severity == MaintenanceJob.Severity.HIGH and job.reported_by == staff
    assert booking.booking_reference in job.reported_problem
    assert "Brakes squeal" in job.reported_problem
    assert report.maintenance_job == job
    assert Vehicle.objects.get(pk=booking.vehicle_id).status == vehicle_status
    assert services.settlement_record(booking, report)["maintenance_job"] == job.pk


def test_a_flag_the_maintenance_service_refuses_stops_the_return():
    booking = active_booking()
    flag = services.Flag("   ", MaintenanceJob.Severity.LOW)
    with pytest.raises(services.ReturnError) as raised:
        return_now(booking, flag=flag)
    assert raised.value.code == "flag_refused"
    assert Booking.objects.get(pk=booking.pk).status == Status.ACTIVE


# ─── R2: extended bookings settle on their current return time ────────────


def _extend(booking, new_return):
    licence = LicenceFactory(customer=booking.customer)
    LicenceCategoryFactory(licence=licence, category="Car")
    quote = bookings.extension_quote(booking.customer, booking.pk, new_return)
    bookings.extend_booking(
        booking.customer,
        booking.pk,
        new_return,
        expected_charge=quote.extra_charge,
        idempotency_key="extend-test-1",
        payment={"payment_token": "tok_test"},
    )
    booking.refresh_from_db()
    return quote.extra_charge


def test_an_extended_booking_returned_on_time_is_not_late_and_the_extension_is_paid():
    booking = active_booking(due_in=-timedelta(hours=3))  # 3 h past the original time
    extra = _extend(booking, booking.return_datetime + timedelta(days=1))
    report = return_now(booking, readings=readings(odometer_reading=12450))
    assert report.charges == []  # no late return, and 450 km is inside 2 x 250 km
    paid = services.rental_paid(booking)
    assert [entry.amount for entry in paid][-1] == extra  # shown as paid, never charged again
    assert "(Book.Extend)" in paid[-1].note
    assert charges(booking) == []


def test_an_extended_booking_returned_late_is_late_from_the_extended_time():
    booking = active_booking()
    _extend(booking, booking.return_datetime + timedelta(hours=2))
    with freeze_time(booking.return_datetime + timedelta(hours=3)):
        staff = staff_at(booking)
        quote = services.return_quote(booking, staff, readings(returned_at=timezone.now()))
    (late, tax) = quote.settlement.lines
    assert (late.kind, late.amount) == ("late_return", D("450.00"))  # 3 hours, not 5
    assert quote.settlement.free_km == 500  # a day and two hours is billed as two days


# ─── Branch returns (UC 8 step 1) ─────────────────────────────────────────


@freeze_time(timezone.make_aware(datetime(2026, 10, 18, 12, 0)))
def test_branch_returns_lists_due_and_overdue_rentals_and_finds_any_active_one():
    now = timezone.now()
    overdue = BookingFactory(
        status=Status.ACTIVE, pickup_datetime=now - timedelta(days=2), return_datetime=now
    )
    later_today = BookingFactory(
        status=Status.ACTIVE,
        pickup_datetime=now - timedelta(days=1),
        return_datetime=now + timedelta(hours=3),
    )
    next_week = BookingFactory(
        status=Status.ACTIVE, pickup_datetime=now, return_datetime=now + timedelta(days=7)
    )
    confirmed = BookingFactory(pickup_datetime=now - timedelta(hours=1))
    bookings_ = Booking.objects.all()
    assert list(services.branch_returns(bookings_)) == [overdue, later_today]
    found = services.branch_returns(bookings_, query=next_week.booking_reference)
    assert list(found) == [next_week]
    assert not services.branch_returns(bookings_, query=confirmed.booking_reference).exists()


# ─── bookings.states.complete_booking() (Module N2; Rohan to review) ──────


class TestCompleteBooking:
    def test_active_becomes_completed_with_the_return_time_and_distance(self):
        booking = BookingFactory(status=Status.ACTIVE)
        staff = BranchStaffFactory().user
        booking.returned_at = timezone.now()
        booking.distance_travelled = 320
        complete_booking(booking, staff)
        booking.refresh_from_db()
        assert booking.status == Status.COMPLETED and booking.distance_travelled == 320
        entry = AuditLog.objects.get(action="Booking Status Changed")
        assert entry.actor == staff and entry.before == {"status": "Active"}

    @pytest.mark.parametrize("status", ["Draft", "Pending Payment", "Confirmed", "Cancelled"])
    def test_only_from_active(self, status):
        with pytest.raises(IllegalBookingTransition):
            complete_booking(BookingFactory(status=status), None)


def test_the_settlement_e_mail_renders():
    subject, body = render("return_settlement", 1, SAMPLE_CONTEXT)
    assert "VRMS-20261016-0001" in subject
    assert "Total charges: INR 2,006.00" in body
