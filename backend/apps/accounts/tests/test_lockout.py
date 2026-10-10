"""SE-8: five consecutive failed sign-ins lock the account for 15 minutes."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from apps.accounts.tests.factories import CustomerFactory
from apps.core.models import AuditLog
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db

PASSWORD = "Test@12345"


def _login(client, email, password):
    return client.post(
        reverse("accounts:login"), {"email": email, "password": password}, format="json"
    )


@pytest.fixture
def customer():
    return CustomerFactory()


def test_five_failures_lock_the_account_for_fifteen_minutes(api_client, customer, outbox):
    email = customer.user.email
    start = timezone.now()
    with freeze_time(start) as clock:
        for _ in range(4):
            assert _login(api_client, email, "wrong-password").status_code == 401
        locked = _login(api_client, email, "wrong-password")
        assert locked.status_code == 403
        assert locked.json()["code"] == "account_locked"

        # The right password is refused while the lock lasts.
        clock.tick(timedelta(minutes=14, seconds=59))
        assert _login(api_client, email, PASSWORD).status_code == 403

        # After the lock period the account works again.
        clock.move_to(start + timedelta(minutes=15, seconds=1))
        assert _login(api_client, email, PASSWORD).status_code == 200

    # SE-8: the registered address is told, once; SE-10: the lock is audited.
    locked_mails = Notification.objects.filter(recipient=customer.user, template="account_locked")
    assert locked_mails.count() == 1
    assert [m.recipient for m in outbox if m.channel == "email"] == [email]
    assert AuditLog.objects.filter(
        action="Account Locked", entity_id=str(customer.user.pk)
    ).exists()


def test_success_resets_the_count(api_client, customer):
    """Failures must be consecutive: a success in between starts again."""
    email = customer.user.email
    for _ in range(4):
        _login(api_client, email, "wrong-password")
    assert _login(api_client, email, PASSWORD).status_code == 200
    for _ in range(4):
        assert _login(api_client, email, "wrong-password").status_code == 401
    assert _login(api_client, email, PASSWORD).status_code == 200


def test_lock_ignores_email_case(api_client, customer):
    email = customer.user.email
    for variant in [email, email.upper(), email.title(), email, email.upper()]:
        _login(api_client, variant, "wrong-password")
    assert _login(api_client, email, PASSWORD).status_code == 403


def test_unknown_account_gets_the_same_responses(api_client, outbox):
    """SE-8: messages never reveal whether the account exists."""
    first = _login(api_client, "ghost@example.com", "wrong-password")
    assert first.status_code == 401
    assert first.json()["detail"] == "Unable to sign in with the details provided."
    for _ in range(4):
        last = _login(api_client, "ghost@example.com", "wrong-password")
    assert last.status_code == 403
    assert outbox == []


def test_lockout_is_per_account_not_per_ip(api_client, customer):
    for _ in range(5):
        _login(api_client, "someone-else@example.com", "wrong-password")
    assert _login(api_client, customer.user.email, PASSWORD).status_code == 200
