"""SI-1.4: signed gateway notifications, stored once and acted on once (Pay.Idempotent)."""

import json
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection, transaction
from django.urls import reverse

from apps.core.exceptions import ImmutableRecordError
from apps.payments import services
from apps.payments.models import GatewayNotification, LedgerEntry, RefundRequest
from apps.payments.tests.conftest import original
from integrations.payment_gateway.mock import MockPaymentGateway

pytestmark = pytest.mark.django_db

URL = reverse("payments:webhook")


def send(api_client, event: dict, signature: str | None = None):
    body = json.dumps(event).encode()
    return api_client.post(
        URL,
        data=body,
        content_type="application/json",
        HTTP_X_GATEWAY_SIGNATURE=MockPaymentGateway.sign(body) if signature is None else signature,
    )


def test_a_signed_notification_is_stored_once(api_client):
    event = {"id": "evt_0001", "type": "refund.processed", "transaction_id": "rfnd_1"}
    first = send(api_client, event)
    assert first.status_code == 200
    assert first.json() == {"event_id": "evt_0001", "duplicate": False}
    again = send(api_client, event)
    assert again.json() == {"event_id": "evt_0001", "duplicate": True}
    assert GatewayNotification.objects.count() == 1


def test_an_unsigned_or_forged_notification_is_refused_and_not_stored(api_client):
    event = {"id": "evt_0002", "type": "refund.failed", "transaction_id": "x"}
    assert send(api_client, event, signature="").status_code == 403
    response = send(api_client, event, signature="0" * 64)
    assert (response.status_code, response.json()["code"]) == (403, "invalid_signature")
    assert not GatewayNotification.objects.exists()


def test_a_notification_needs_an_id_and_a_type(api_client):
    body = b"not json"
    response = api_client.post(
        URL,
        data=body,
        content_type="application/json",
        HTTP_X_GATEWAY_SIGNATURE=MockPaymentGateway.sign(body),
    )
    assert response.status_code == 400


def test_a_failed_refund_is_reversed_once_however_often_it_is_reported(
    api_client, paid, staff, outbox
):
    refund = services.refund_payment(original(paid), Decimal("500.00"), "Goodwill", staff)
    reference = refund.refund.gateway_reference
    event = {
        "id": "evt_0003",
        "type": "refund.failed",
        "transaction_id": reference,
        "message": "Account closed",
    }
    send(api_client, event)
    send(api_client, event)

    refund.refresh_from_db()
    assert refund.status == RefundRequest.Status.FAILED
    assert refund.failure_reason == "Account closed"
    refund.refund.refresh_from_db()
    assert refund.refund.status == "Failed"
    adjustment = LedgerEntry.objects.get(booking=paid, entry_type="Adjustment")
    assert adjustment.reference_entry == LedgerEntry.objects.get(booking=paid, entry_type="Refund")
    assert adjustment.amount == Decimal("500.00")
    assert "could not be completed" in outbox[-1].subject


def test_the_notification_log_is_append_only(api_client):
    send(api_client, {"id": "evt_0004", "type": "payment.captured"})
    row = GatewayNotification.objects.get()
    with pytest.raises(ImmutableRecordError):
        row.save()
    with pytest.raises(IntegrityError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM payments_gatewaynotification WHERE id = %s", [row.pk])
