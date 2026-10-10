"""Notification delivery log (SI-2)."""

import pytest

from apps.notifications.models import Notification
from apps.notifications.tests.factories import NotificationFactory

pytestmark = pytest.mark.django_db


def test_factory_creates_a_valid_row():
    notification = NotificationFactory()
    notification.full_clean()
    assert notification.status == "Queued"
    assert str(notification)


def test_channels_are_email_sms_and_push():
    assert Notification.Channel.values == ["Email", "SMS", "Push"]


def test_body_is_not_stored():
    """Only template variables are kept, so an OTP is never persisted in clear."""
    field_names = {f.name for f in Notification._meta.get_fields()}
    assert "body" not in field_names
    assert "message" not in field_names
