"""Pay.Refund, BR-14, UC 13 Approve Refund and Pay.Invoice credit notes."""

from datetime import date
from decimal import Decimal

import pytest
from django.test import override_settings
from freezegun import freeze_time

from apps.accounts.tests.factories import BranchManagerFactory, BranchStaffFactory
from apps.core.exceptions import ImmutableRecordError
from apps.core.models import AuditLog
from apps.notifications.models import Notification
from apps.payments import services
from apps.payments.models import (
    CashPayment,
    InvoiceAdjustment,
    LedgerEntry,
    Payment,
    RefundRequest,
)
from apps.payments.tests.conftest import cash_confirmed, deposit_of, original
from integrations.payment_gateway.interface import GatewayResponse
from integrations.payment_gateway.mock import MockPaymentGateway

pytestmark = pytest.mark.django_db

R = RefundRequest.Status
E = LedgerEntry.EntryType


def refunds_of(payment):
    return Payment.objects.filter(original_payment=payment, transaction_type="Refund")


# ─── Issued at once, within the limit ─────────────────────────────────────


def test_a_refund_within_the_limit_goes_back_to_the_original_card_at_once(paid, staff, outbox):
    rental = original(paid)
    refund = services.refund_payment(rental, Decimal("1000.00"), "Goodwill", staff)

    assert refund.status == R.ISSUED
    assert refund.decided_by is None  # automatic: no approver needed
    row = refund.refund
    assert (row.original_payment, row.transaction_type, row.amount) == (
        rental,
        "Refund",
        Decimal("1000.00"),
    )
    assert row.gateway_reference.startswith("rfnd_")  # SI-1.3: the reference is stored
    entry = LedgerEntry.objects.get(payment=row)
    assert (entry.entry_type, entry.amount, entry.method) == (E.REFUND, Decimal("1000.00"), "Card")
    assert outbox[-1].recipient == paid.customer.user.email
    assert "has been issued" in outbox[-1].subject


def test_an_uncaptured_authorisation_is_captured_before_it_is_refunded(paid, staff):
    rental = original(paid)
    services.refund_payment(rental, Decimal("300.00"), "Goodwill", staff)
    capture = Payment.objects.get(original_payment=rental, transaction_type="Capture")
    assert capture.amount == Decimal("300.00")
    assert LedgerEntry.objects.filter(payment=capture, entry_type=E.CAPTURE).exists()


def test_a_rental_refund_corrects_the_issued_invoice_with_a_credit_note(paid, staff):
    invoice = paid.invoice
    services.refund_payment(original(paid), Decimal("1180.00"), "Charged a day too many", staff)
    note = InvoiceAdjustment.objects.get(invoice=invoice)
    assert note.adjustment_type == InvoiceAdjustment.AdjustmentType.CREDIT_NOTE
    assert note.adjustment_number.startswith("CN-") and note.adjustment_number.endswith("000001")
    assert (note.amount, note.tax_amount) == (Decimal("1180.00"), Decimal("180.00"))  # 18% inside
    invoice.refresh_from_db()
    assert invoice.total_amount == Decimal("4248.00")  # the invoice itself is never edited
    with pytest.raises(ImmutableRecordError):
        note.save()


def test_a_deposit_refund_is_a_deposit_release_and_never_a_credit_note(paid, staff):
    refund = services.refund_payment(deposit_of(paid), Decimal("5000.00"), "Balance", staff)
    assert refund.status == R.ISSUED  # exactly the limit is still automatic
    assert LedgerEntry.objects.get(payment=refund.refund).entry_type == E.DEPOSIT_RELEASE
    assert not InvoiceAdjustment.objects.exists()


def test_credit_notes_never_exceed_the_invoice(paid, staff):
    services.issue_credit_note(paid.invoice, Decimal("4000.00"), "Part", issued_by=staff)
    with pytest.raises(services.PaymentError) as refused:
        services.issue_credit_note(paid.invoice, Decimal("248.01"), "More", issued_by=staff)
    assert refused.value.code == "exceeds_invoice"


# ─── UC 13: above the limit, an Administrator decides ─────────────────────


def test_a_refund_above_the_limit_waits_for_an_administrator(long_paid, staff):
    rental = original(long_paid)
    refund = services.refund_payment(rental, Decimal("6372.00"), "Cancelled by us", staff)
    assert refund.status == R.PENDING_APPROVAL
    assert refund.refund is None
    assert not refunds_of(rental).exists()
    assert not LedgerEntry.objects.filter(booking=long_paid, entry_type=E.REFUND).exists()
    assert AuditLog.objects.filter(action="Refund Requested", entity_id=str(refund.pk)).exists()


@override_settings(REFUND_AUTO_APPROVAL_LIMIT=Decimal("100.00"))
def test_the_limit_is_the_refund_auto_approval_setting(paid, staff):
    refund = services.refund_payment(original(paid), Decimal("100.01"), "Goodwill", staff)
    assert refund.status == R.PENDING_APPROVAL


def test_approving_issues_the_refund_and_records_the_approver(long_paid, staff, admin):
    refund = services.refund_payment(original(long_paid), Decimal("6372.00"), "Cancelled", staff)
    refund = services.approve_refund(refund, admin)
    assert refund.status == R.ISSUED
    assert refund.decided_by == admin and refund.decided_at is not None
    assert refunds_of(original(long_paid)).get().amount == Decimal("6372.00")
    actions = list(
        AuditLog.objects.filter(entity_id=str(refund.pk), entity_type="payments.RefundRequest")
        .order_by("id")
        .values_list("action", flat=True)
    )
    assert actions == ["Refund Requested", "Refund Approved", "Refund Status Changed"]


def test_rejecting_records_the_reason_and_notifies_the_customer_through_celery(
    long_paid, staff, admin, outbox
):
    refund = services.refund_payment(original(long_paid), Decimal("6372.00"), "Cancelled", staff)
    refund = services.reject_refund(refund, admin, "The cancellation was after the cut-off.")
    assert refund.status == R.REJECTED
    assert refund.rejection_reason == "The cancellation was after the cut-off."
    assert refund.decided_by == admin
    assert not refunds_of(original(long_paid)).exists()
    notification = Notification.objects.get(template="refund_rejected")
    assert notification.status == Notification.Status.SENT  # delivered by the Celery task
    assert "after the cut-off" in outbox[-1].body
    audit = AuditLog.objects.filter(action="Refund Status Changed").latest("id")
    assert audit.after["status"] == R.REJECTED


def test_a_rejection_needs_a_reason(long_paid, staff, admin):
    refund = services.refund_payment(original(long_paid), Decimal("6372.00"), "Cancelled", staff)
    with pytest.raises(services.PaymentError) as refused:
        services.reject_refund(refund, admin, "  ")
    assert refused.value.code == "reason_required"


def test_only_an_administrator_approves_or_rejects(long_paid, staff, branch):
    refund = services.refund_payment(original(long_paid), Decimal("6372.00"), "Cancelled", staff)
    manager = BranchManagerFactory(branch=branch).user
    for user in (staff, manager):
        with pytest.raises(services.PaymentError) as refused:
            services.approve_refund(refund, user)
        assert refused.value.status == 403
        with pytest.raises(services.PaymentError):
            services.reject_refund(refund, user, "No")
    refund.refresh_from_db()
    assert refund.status == R.PENDING_APPROVAL


def test_a_decided_refund_cannot_be_decided_again(long_paid, staff, admin):
    refund = services.refund_payment(original(long_paid), Decimal("6372.00"), "Cancelled", staff)
    services.reject_refund(refund, admin, "No")
    for decide in (
        lambda: services.approve_refund(refund, admin),
        lambda: services.reject_refund(refund, admin, "Again"),
    ):
        with pytest.raises(services.PaymentError) as refused:
            decide()
        assert refused.value.code == "not_pending"


def test_refund_statuses_follow_their_transition_table(paid, staff):
    refund = services.refund_payment(original(paid), Decimal("10.00"), "Goodwill", staff)
    with pytest.raises(services.PaymentError) as refused:
        services._set_refund_status(refund, R.APPROVED, actor=None, reason="x", request=None)
    assert refused.value.code == "invalid_state"
    assert services.REFUND_TRANSITIONS[R.REJECTED] == frozenset()


# ─── Limits and Pay.Idempotent ────────────────────────────────────────────


def test_no_more_than_was_paid_can_be_refunded_counting_refunds_waiting(long_paid, staff):
    rental = original(long_paid)
    with pytest.raises(services.PaymentError) as refused:
        services.refund_payment(rental, Decimal("6372.01"), "Too much", staff)
    assert refused.value.code == "exceeds_refundable"
    services.refund_payment(rental, Decimal("6000.00"), "Waiting", staff)  # pending approval
    with pytest.raises(services.PaymentError):
        services.refund_payment(rental, Decimal("372.01"), "Over", staff)
    assert services.refund_payment(rental, Decimal("372.00"), "Rest", staff).status == R.ISSUED


def test_the_same_key_never_refunds_twice(paid, staff):
    rental = original(paid)
    first = services.refund_payment(
        rental, Decimal("500.00"), "Goodwill", staff, idempotency_key="rf-1"
    )
    again = services.refund_payment(
        rental, Decimal("500.00"), "Goodwill", staff, idempotency_key="rf-1"
    )
    assert again.pk == first.pk
    assert refunds_of(rental).count() == 1
    with pytest.raises(services.PaymentError) as reused:
        services.refund_payment(rental, Decimal("600.00"), "Other", staff, idempotency_key="rf-1")
    assert reused.value.code == "idempotency_key_reused"


def test_only_a_successful_booking_payment_can_be_refunded(paid, staff):
    capture = services.capture_charges(paid, [], staff)[0].payment
    with pytest.raises(services.PaymentError) as follow_up:
        services.refund_payment(capture, Decimal("1.00"), "No", staff)
    assert follow_up.value.code == "not_refundable"
    with pytest.raises(services.PaymentError) as no_reason:
        services.refund_payment(original(paid), Decimal("1.00"), " ", staff)
    assert no_reason.value.code == "reason_required"
    with pytest.raises(TypeError):
        services.refund_payment(original(paid), 1.0, "Float", staff)


def test_a_refund_the_gateway_refuses_is_marked_failed(paid, staff, monkeypatch):
    monkeypatch.setattr(
        MockPaymentGateway,
        "refund",
        lambda self, txn, amount, key: GatewayResponse(False, txn, amount, "Card closed."),
    )
    refund = services.refund_payment(original(paid), Decimal("100.00"), "Goodwill", staff)
    assert refund.status == R.FAILED
    assert refund.failure_reason == "Card closed."
    assert not LedgerEntry.objects.filter(booking=paid, entry_type=E.REFUND).exists()


# ─── Cash refunds: a named staff member, acknowledged by the customer ────


def test_a_cash_refund_is_paid_out_by_the_named_staff_member(customer, car, pickup, return_, staff):
    booking = cash_confirmed(customer, car, pickup, return_, staff)
    refund = services.refund_payment(deposit_of(booking), Decimal("5000.00"), "Balance", staff)
    assert refund.status == R.ISSUED
    cash = CashPayment.objects.get(pk=refund.refund_id)
    assert cash.received_by == staff.branch_staff
    assert cash.customer_acknowledged_at is not None
    entry = LedgerEntry.objects.get(payment=cash)
    assert (entry.entry_type, entry.method) == (E.DEPOSIT_RELEASE, "Cash")


def test_a_cash_refund_asked_for_elsewhere_waits_for_the_branch(
    customer, car, pickup, return_, staff, admin
):
    booking = cash_confirmed(customer, car, pickup, return_, staff)
    refund = services.refund_payment(deposit_of(booking), Decimal("2000.00"), "Balance", admin)
    assert refund.status == R.APPROVED
    with pytest.raises(services.PaymentError) as not_staff:
        services.pay_out_cash_refund(refund, admin)
    assert not_staff.value.status == 403
    refund = services.pay_out_cash_refund(refund, staff)
    assert refund.status == R.ISSUED
    with pytest.raises(services.PaymentError) as twice:
        services.pay_out_cash_refund(refund, staff)
    assert twice.value.code == "invalid_state"


def test_a_large_cash_refund_is_approved_then_paid_out(customer, car, pickup, staff, admin):
    from datetime import timedelta

    booking = cash_confirmed(customer, car, pickup, pickup + timedelta(days=3), staff)
    refund = services.refund_payment(original(booking), Decimal("6372.00"), "Cancelled", staff)
    assert refund.status == R.PENDING_APPROVAL
    assert services.approve_refund(refund, admin).status == R.APPROVED
    other = BranchStaffFactory().user  # staff of another branch: the API scopes them out (404)
    assert services.pay_out_cash_refund(refund, other).status == R.ISSUED


# ─── BR-14: the deposit balance within 7 working days ────────────────────


@freeze_time("2026-10-15 06:00:00")  # a Thursday in IST
def test_the_deposit_balance_is_due_within_seven_working_days(paid, staff):
    refund = services.refund_deposit(paid, Decimal("4349.50"), staff)
    assert refund.refund_due_by == date(2026, 10, 26)  # Fri 16, Mon 19 ... Mon 26
    assert refund.status == R.ISSUED
    assert refund.reason == "Security deposit balance (BR-14)"
    assert LedgerEntry.objects.get(payment=refund.refund).entry_type == E.DEPOSIT_RELEASE


def test_one_deposit_refund_per_booking(paid, staff):
    first = services.refund_deposit(paid, Decimal("4000.00"), staff)
    assert services.refund_deposit(paid, Decimal("4000.00"), staff).pk == first.pk
    with pytest.raises(services.PaymentError) as other:
        services.refund_deposit(paid, Decimal("100.00"), staff)
    assert other.value.code == "idempotency_key_reused"


def test_a_booking_without_a_deposit_payment_has_none_to_refund(
    customer, car, pickup, return_, staff
):
    from apps.payments.tests.conftest import held

    with pytest.raises(services.PaymentError) as refused:
        services.refund_deposit(held(customer, car, pickup, return_), Decimal("1.00"), staff)
    assert refused.value.code == "not_paid"


def test_working_days_skip_the_weekend():
    assert services.add_working_days(date(2026, 10, 16), 1) == date(2026, 10, 19)  # Fri -> Mon
    assert services.add_working_days(date(2026, 10, 17), 7) == date(2026, 10, 27)  # Sat
