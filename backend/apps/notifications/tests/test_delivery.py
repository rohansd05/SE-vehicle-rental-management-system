"""Queued delivery (SI-2): Celery tasks, templates, and no OTP in clear text."""

import logging

import pytest
from django.test import override_settings

from apps.accounts.models import OneTimePassword
from apps.accounts.services import issue_otp
from apps.accounts.tests.factories import UserFactory
from apps.notifications.models import Notification
from apps.notifications.services import queue_email
from apps.notifications.templates import TEMPLATES, render

pytestmark = pytest.mark.django_db


def test_queue_email_creates_a_row_and_the_task_sends_it(outbox, settings):
    settings.AGENCY_NAME = "Demo Agency"
    user = UserFactory()
    notification = queue_email(
        user, "licence_approved", {"name": user.name, "licence_number": "MH01 1"}
    )
    notification.refresh_from_db()
    assert notification.status == Notification.Status.SENT
    assert notification.attempt_count == 1
    assert notification.provider_message_id.startswith("mock_msg_")
    sent = outbox[-1]
    assert sent.recipient == user.email
    assert sent.subject == "Demo Agency: your driving licence has been verified"


def test_every_template_renders():
    context = {
        "code": "123456",
        "minutes": 10,
        "name": "Asha",
        "attempts": 5,
        "licence_number": "MH01 1",
        "reason": "Blurred",
    }
    for name, version in TEMPLATES:
        subject, body = render(name, version, context)
        assert body


def test_otp_code_never_reaches_the_database_or_the_log(caplog, outbox):
    user = UserFactory()
    with caplog.at_level(logging.INFO):
        otp = issue_otp(user, OneTimePassword.Purpose.REGISTRATION, user.mobile_no)
    code = next(m for m in outbox if m.channel == "sms").body.split(" is your")[0].split()[-1]
    otp.refresh_from_db()
    assert code not in otp.code_hash
    notification = Notification.objects.get(template="otp")
    assert code not in str(notification.context)
    assert code not in caplog.text  # DEBUG is off outside development


@override_settings(DEBUG=True)
def test_mock_logs_the_body_in_development(caplog):
    user = UserFactory()
    with caplog.at_level(logging.INFO, logger="vrms.notifications.mock"):
        issue_otp(user, OneTimePassword.Purpose.REGISTRATION, user.mobile_no)
    assert "is your verification code" in caplog.text
