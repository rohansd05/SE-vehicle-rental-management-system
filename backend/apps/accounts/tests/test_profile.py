"""Own profile, mobile change by OTP (SE-7) and password change."""

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.tests.factories import CustomerFactory
from apps.accounts.tests.helpers import authenticated_client
from apps.core.models import AuditLog

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return CustomerFactory().user


def test_get_profile(user):
    data = authenticated_client(user).get(reverse("accounts:me")).json()
    assert data == {
        "id": user.pk,
        "email": user.email,
        "name": user.name,
        "mobile_no": user.mobile_no,
        "address": user.address,
        "role": "CUSTOMER",
    }


def test_patch_name_and_address_applies_at_once(user):
    client = authenticated_client(user)
    response = client.patch(
        reverse("accounts:me"), {"name": "New Name", "address": "1 New Road"}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["mobile_change_pending"] is False
    user.refresh_from_db()
    assert (user.name, user.address) == ("New Name", "1 New Road")
    assert AuditLog.objects.filter(action="Update", entity_id=str(user.pk)).exists()


def test_patch_cannot_change_email_or_role(user):
    client = authenticated_client(user)
    client.patch(
        reverse("accounts:me"), {"email": "x@example.com", "role": "ADMINISTRATOR"}, format="json"
    )
    user.refresh_from_db()
    assert user.role == User.Role.CUSTOMER
    assert user.email != "x@example.com"


def test_mobile_change_waits_for_the_otp(user, latest_code):
    client = authenticated_client(user)
    old_mobile = user.mobile_no
    response = client.patch(reverse("accounts:me"), {"mobile_no": "+919898989898"}, format="json")
    assert response.json()["mobile_change_pending"] is True
    user.refresh_from_db()
    assert user.mobile_no == old_mobile  # unchanged until confirmed

    code = latest_code("+919898989898")  # sent to the new number
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"
    assert client.post(reverse("accounts:verify-mobile"), {"code": wrong}).status_code == 400
    assert client.post(reverse("accounts:verify-mobile"), {"code": code}).status_code == 200
    user.refresh_from_db()
    assert user.mobile_no == "+919898989898"
    assert AuditLog.objects.filter(action="Mobile Changed").exists()


def test_password_change_ends_every_session(api_client, user):
    login = {"email": user.email, "password": "Test@12345"}
    signed_in = api_client.post(reverse("accounts:login"), login, format="json")
    old_cookie = signed_in.cookies["vrms_refresh"].value
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {signed_in.json()['access']}")
    response = api_client.post(
        reverse("accounts:password-change"),
        {"current_password": "Test@12345", "new_password": "N3w!Passw0rd-2026"},
    )
    assert response.status_code == 200
    assert response.cookies["vrms_refresh"].value == ""  # D21: cookie cleared
    api_client.credentials()
    api_client.cookies["vrms_refresh"] = old_cookie
    assert api_client.post(reverse("accounts:refresh")).status_code == 401
    assert api_client.post(reverse("accounts:login"), login, format="json").status_code == 401
    login["password"] = "N3w!Passw0rd-2026"
    assert api_client.post(reverse("accounts:login"), login, format="json").status_code == 200
    entry = AuditLog.objects.get(action="Password Changed")
    assert "N3w!Passw0rd-2026" not in str(entry.after)


def test_password_change_needs_the_current_password(user):
    response = authenticated_client(user).post(
        reverse("accounts:password-change"),
        {"current_password": "wrong", "new_password": "N3w!Passw0rd-2026"},
    )
    assert response.status_code == 400
    assert "current_password" in response.json()


def test_password_change_applies_django_validators(user):
    response = authenticated_client(user).post(
        reverse("accounts:password-change"),
        {"current_password": "Test@12345", "new_password": "12345678"},
    )
    assert response.status_code == 400
    assert "password" in response.json()
