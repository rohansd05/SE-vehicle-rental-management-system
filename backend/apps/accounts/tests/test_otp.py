"""SE-7 one-time passwords: expiry, attempt limit, resend, hash-only storage (D15)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from freezegun import freeze_time

from apps.accounts.models import OneTimePassword, User
from apps.accounts.tests.helpers import REGISTRATION

pytestmark = pytest.mark.django_db

EMAIL = REGISTRATION["email"]
MOBILE = REGISTRATION["mobile_no"]


@pytest.fixture
def registered(api_client):
    response = api_client.post(reverse("accounts:register"), REGISTRATION, format="json")
    assert response.status_code == 201
    return User.objects.get(email=EMAIL)


def _verify(client, code):
    return client.post(reverse("accounts:verify-otp"), {"email": EMAIL, "code": code})


def _wrong(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


def test_only_a_hash_of_the_code_is_stored(registered, latest_code):
    code = latest_code(MOBILE)
    otp = OneTimePassword.objects.get(user=registered)
    assert otp.code_hash.startswith("bcrypt_sha256$")
    assert code not in otp.code_hash
    for field in OneTimePassword._meta.concrete_fields:
        assert code != str(getattr(otp, field.attname))


def test_code_expires_after_the_otp_lifetime(api_client, registered, latest_code):
    code = latest_code(MOBILE)
    with freeze_time(OneTimePassword.objects.get().expires_at + timedelta(seconds=1)):
        assert _verify(api_client, code).status_code == 400
    registered.refresh_from_db()
    assert not registered.is_active


def test_code_works_just_before_expiry(api_client, registered, latest_code):
    code = latest_code(MOBILE)
    with freeze_time(OneTimePassword.objects.get().expires_at - timedelta(seconds=1)):
        assert _verify(api_client, code).status_code == 200


def test_five_wrong_attempts_kill_the_code(api_client, registered, latest_code):
    code = latest_code(MOBILE)
    for _ in range(5):
        response = _verify(api_client, _wrong(code))
        assert response.status_code == 400
        assert response.json()["detail"] == "The code is invalid or has expired."
    assert OneTimePassword.objects.get().attempt_count == 5
    assert _verify(api_client, code).status_code == 400  # the right code is now refused
    registered.refresh_from_db()
    assert not registered.is_active


def test_a_code_works_only_once(api_client, registered, latest_code):
    code = latest_code(MOBILE)
    assert _verify(api_client, code).status_code == 200
    assert _verify(api_client, code).status_code == 400


def test_resend_invalidates_the_previous_code(api_client, registered, latest_code):
    first = latest_code(MOBILE)
    assert api_client.post(reverse("accounts:resend-otp"), {"email": EMAIL}).status_code == 200
    second = latest_code(MOBILE)
    assert OneTimePassword.objects.filter(user=registered).count() == 2
    if first != second:  # 1-in-a-million chance they collide
        assert _verify(api_client, first).status_code == 400
    assert _verify(api_client, second).status_code == 200


def test_resend_has_a_cooldown(api_client, registered):
    url = reverse("accounts:resend-otp")
    assert api_client.post(url, {"email": EMAIL}).status_code == 200
    assert api_client.post(url, {"email": EMAIL}).status_code == 429


def test_resend_does_not_reveal_whether_an_account_exists(api_client, outbox):
    response = api_client.post(reverse("accounts:resend-otp"), {"email": "nobody@example.com"})
    assert response.status_code == 200
    assert response.json()["detail"].startswith("If an unverified account")
    assert outbox == []


def test_verify_for_unknown_email_is_generic(api_client):
    response = api_client.post(
        reverse("accounts:verify-otp"), {"email": "nobody@example.com", "code": "123456"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "The code is invalid or has expired."


@pytest.mark.parametrize("code", ["12345", "1234567", "abcdef"])
def test_code_must_be_six_digits(api_client, registered, code):
    assert _verify(api_client, code).status_code == 400
