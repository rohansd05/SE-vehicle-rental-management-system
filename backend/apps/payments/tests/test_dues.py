"""Pay.Dues and BR-4: record_due() blocks booking; pay_due() clears it on-line at once."""

from decimal import Decimal

import pytest

from apps.bookings.eligibility import NotEligibleError
from apps.core.models import AuditLog
from apps.payments import services
from apps.payments.models import OnlinePayment, Payment
from apps.payments.tests.conftest import held

pytestmark = pytest.mark.django_db


def test_a_due_is_added_to_the_customer_and_audited(customer, staff):
    assert services.record_due(
        customer, Decimal("750.00"), "Damage over the deposit", initiated_by=staff
    ) == Decimal("750.00")
    assert services.record_due(customer, Decimal("50.00"), "Fuel") == Decimal("800.00")
    customer.refresh_from_db()
    assert customer.outstanding_due == Decimal("800.00")
    entry = AuditLog.objects.filter(action="Due Recorded").order_by("id").first()
    assert entry.actor == staff
    assert entry.before == {"outstanding_due": "0.00"}
    assert entry.after["reason"] == "Damage over the deposit"


def test_a_due_must_be_a_positive_decimal_with_a_reason(customer):
    with pytest.raises(services.PaymentError):
        services.record_due(customer, Decimal("0.00"), "Nothing")
    with pytest.raises(TypeError):
        services.record_due(customer, 10.0, "Float")
    with pytest.raises(services.PaymentError) as no_reason:
        services.record_due(customer, Decimal("1.00"), "")
    assert no_reason.value.code == "reason_required"


def test_a_due_blocks_booking_and_paying_it_lifts_the_restriction_at_once(
    customer, car, pickup, return_
):
    services.record_due(customer, Decimal("850.00"), "Late return over the deposit")
    with pytest.raises(NotEligibleError) as refused:
        held(customer, car, pickup, return_)
    assert refused.value.code == "outstanding_due"

    payment = services.pay_due(customer, payment_token="tok_visa", idempotency_key="due-key-0001")
    assert (payment.purpose, payment.amount, payment.status) == (
        "Due",
        Decimal("850.00"),
        "Succeeded",
    )
    assert payment.booking is None
    customer.refresh_from_db()
    assert customer.outstanding_due == Decimal("0.00")
    assert held(customer, car, pickup, return_).status == "Pending Payment"  # BR-4 lifted
    assert AuditLog.objects.filter(action="Due Cleared").exists()


def test_a_due_can_be_paid_through_an_online_channel(customer):
    services.record_due(customer, Decimal("120.00"), "Fuel")
    payment = services.pay_due(
        customer,
        payment_token="tok_upi",
        idempotency_key="due-key-0002",
        channel=OnlinePayment.Channel.UPI,
        upi_id="asha@okbank",
    )
    online = OnlinePayment.objects.get(pk=payment.pk)
    assert (online.channel, online.upi_id) == ("UPI", "asha@okbank")


def test_the_same_key_never_charges_the_due_twice(customer):
    services.record_due(customer, Decimal("300.00"), "Fuel")
    first = services.pay_due(customer, payment_token="tok_visa", idempotency_key="due-key-0003")
    services.record_due(customer, Decimal("40.00"), "Another")  # a new due after paying
    again = services.pay_due(customer, payment_token="tok_visa", idempotency_key="due-key-0003")
    assert again.pk == first.pk
    assert Payment.objects.filter(purpose="Due").count() == 1
    customer.refresh_from_db()
    assert customer.outstanding_due == Decimal("40.00")  # the repeat paid nothing


def test_a_declined_due_payment_keeps_the_due_and_is_recorded(customer):
    services.record_due(customer, Decimal("300.00"), "Fuel")
    with pytest.raises(services.PaymentError) as declined:
        services.pay_due(customer, payment_token="tok_decline", idempotency_key="due-key-0004")
    assert (declined.value.code, declined.value.status) == ("payment_declined", 402)
    customer.refresh_from_db()
    assert customer.outstanding_due == Decimal("300.00")
    assert Payment.objects.get(purpose="Due").status == "Failed"
    with pytest.raises(services.PaymentError) as repeated:
        services.pay_due(customer, payment_token="tok_decline", idempotency_key="due-key-0004")
    assert repeated.value.code == "payment_declined"


def test_nothing_to_pay_without_a_due(customer):
    with pytest.raises(services.PaymentError) as refused:
        services.pay_due(customer, payment_token="tok_visa", idempotency_key="due-key-0005")
    assert (refused.value.code, refused.value.status) == ("no_due", 409)


def test_another_customers_key_is_not_theirs(customer):
    from apps.payments.tests.conftest import eligible_customer

    other = eligible_customer()
    services.record_due(customer, Decimal("10.00"), "Fuel")
    services.record_due(other, Decimal("10.00"), "Fuel")
    services.pay_due(customer, payment_token="tok_visa", idempotency_key="due-key-0006")
    with pytest.raises(services.PaymentError) as refused:
        services.pay_due(other, payment_token="tok_visa", idempotency_key="due-key-0006")
    assert refused.value.code == "idempotency_key_reused"
