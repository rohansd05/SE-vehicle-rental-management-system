"""Mock notification service and factory."""

import pytest
from django.core.exceptions import ImproperlyConfigured

from integrations.notification import get_notification_service
from integrations.notification.mock import MockNotificationService


def test_factory_returns_mock_in_tests():
    assert isinstance(get_notification_service(), MockNotificationService)


def test_factory_rejects_unknown_backend(settings):
    settings.NOTIFICATION_BACKEND = "nope"
    with pytest.raises(ImproperlyConfigured):
        get_notification_service()


def test_mock_records_every_channel_in_order():
    service = MockNotificationService()

    email = service.send_email("a@vrms.test", "Booking confirmed", "Body")
    sms = service.send_sms("+919800000001", "Code 123456")
    push = service.send_push("device-1", "Reminder", "Pickup in 1 hour")

    assert [r.message_id for r in (email, sms, push)] == [
        "mock_msg_000001",
        "mock_msg_000002",
        "mock_msg_000003",
    ]
    assert all(r.success for r in (email, sms, push))
    assert [n.channel for n in service.outbox] == ["email", "sms", "push"]
    assert service.outbox[0].subject == "Booking confirmed"
