"""End-to-end: register, OTP, verify, sign in, refresh, sign out (SE-7, SE-9)."""

import pytest
from django.urls import reverse

from apps.accounts.models import Customer, Licence, OneTimePassword, User
from apps.accounts.tests.factories import CustomerFactory
from apps.accounts.tests.helpers import REGISTRATION
from apps.core.models import AuditLog
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db

COOKIE = "vrms_refresh"


def _register(client, **overrides):
    return client.post(reverse("accounts:register"), {**REGISTRATION, **overrides}, format="json")


def test_full_flow(api_client, latest_code):
    # Register: an inactive customer, a Not Submitted licence and an SMS code.
    response = _register(api_client)
    assert response.status_code == 201, response.json()
    user = User.objects.get(email="asha@example.com")
    assert not user.is_active
    assert user.role == User.Role.CUSTOMER
    assert Customer.objects.get(user=user).licence.status == Licence.Status.NOT_SUBMITTED

    # Sign-in is refused before verification, with the generic message.
    login = {"email": REGISTRATION["email"], "password": REGISTRATION["password"]}
    refused = api_client.post(reverse("accounts:login"), login, format="json")
    assert refused.status_code == 401
    assert refused.json()["detail"] == "Unable to sign in with the details provided."

    # Verify with the code the mock "sent".
    code = latest_code(REGISTRATION["mobile_no"])
    verify = api_client.post(
        reverse("accounts:verify-otp"), {"email": REGISTRATION["email"], "code": code}
    )
    assert verify.status_code == 200
    user.refresh_from_db()
    assert user.is_active

    # Sign in: the access token in the body, the refresh token only in the cookie (D21).
    tokens = api_client.post(reverse("accounts:login"), login, format="json")
    assert tokens.status_code == 200
    body = tokens.json()
    assert set(body) == {"access", "user"}
    assert body["user"]["email"] == "asha@example.com"
    assert body["user"]["role"] == "CUSTOMER"
    first_refresh = tokens.cookies[COOKIE].value
    assert first_refresh

    # The access token works.
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {body['access']}")
    assert api_client.get(reverse("accounts:me")).json()["email"] == "asha@example.com"
    api_client.credentials()

    # Refresh with the cookie alone rotates it; the old token is blacklisted.
    refreshed = api_client.post(reverse("accounts:refresh"))
    assert refreshed.status_code == 200
    assert set(refreshed.json()) == {"access", "user"}
    second_refresh = refreshed.cookies[COOKIE].value
    assert second_refresh != first_refresh
    api_client.cookies[COOKIE] = first_refresh
    reused = api_client.post(reverse("accounts:refresh"))
    assert reused.status_code == 401
    assert reused.json()["code"] == "session_ended"

    # Sign out blacklists the current cookie and clears it.
    api_client.cookies[COOKIE] = second_refresh
    logout = api_client.post(reverse("accounts:logout"))
    assert logout.status_code == 204
    assert logout.cookies[COOKIE].value == ""
    assert logout.cookies[COOKIE]["max-age"] == 0
    api_client.cookies[COOKIE] = second_refresh
    assert api_client.post(reverse("accounts:refresh")).status_code == 401

    # SE-10: every step is audited and the chain holds.
    actions = set(AuditLog.objects.values_list("action", flat=True))
    assert {"Register", "OTP Issued", "Account Verified", "Login", "Logout"} <= actions
    assert "Login Failed" in actions
    assert AuditLog.objects.verify_chain()


def test_otp_is_sent_through_a_notification_row_without_the_code(api_client, latest_code):
    _register(api_client)
    code = latest_code(REGISTRATION["mobile_no"])
    notification = Notification.objects.get(template="otp")
    assert notification.status == Notification.Status.SENT
    assert code not in str(notification.context)
    assert code not in notification.destination
    assert set(notification.context) == {"purpose", "otp_id"}


def test_duplicate_email_is_rejected(api_client):
    _register(api_client)
    response = _register(api_client, email="ASHA@example.com", mobile_no="+919800011111")
    assert response.status_code == 400
    assert "email" in response.json()


def test_django_password_validators_apply(api_client):
    response = _register(api_client, password="password")
    assert response.status_code == 400
    assert "password" in response.json()


def test_future_date_of_birth_is_rejected(api_client):
    response = _register(api_client, date_of_birth="2999-01-01")
    assert response.status_code == 400


def test_registration_can_only_create_customers(api_client):
    response = _register(api_client, role="ADMINISTRATOR", is_staff=True)
    assert response.status_code == 201
    user = User.objects.get(email="asha@example.com")
    assert user.role == User.Role.CUSTOMER
    assert not user.is_staff


def test_disabled_account_cannot_sign_in_or_refresh(api_client):
    """Fleet.Users: disabling an account ends its sessions and refuses sign-in."""
    customer = CustomerFactory()
    login = {"email": customer.user.email, "password": "Test@12345"}
    tokens = api_client.post(reverse("accounts:login"), login, format="json").json()
    customer.user.is_active = False
    customer.user.save()
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    assert api_client.get(reverse("accounts:me")).status_code == 401
    api_client.credentials()
    assert api_client.post(reverse("accounts:refresh")).status_code == 401  # cookie refused
    assert api_client.post(reverse("accounts:login"), login, format="json").status_code == 401


def test_disabled_verified_customer_cannot_reactivate_by_otp(api_client, latest_code):
    _register(api_client)
    code = latest_code(REGISTRATION["mobile_no"])
    api_client.post(reverse("accounts:verify-otp"), {"email": REGISTRATION["email"], "code": code})
    User.objects.filter(email=REGISTRATION["email"]).update(is_active=False)  # admin disables
    api_client.post(reverse("accounts:resend-otp"), {"email": REGISTRATION["email"]})
    assert OneTimePassword.objects.filter(user__email=REGISTRATION["email"]).count() == 1


def test_logout_works_without_an_access_token(api_client):
    """D21: after 30 idle minutes the access token is long gone, yet sign-out
    must still revoke the refresh token and clear the httpOnly cookie."""
    customer = CustomerFactory()
    login = {"email": customer.user.email, "password": "Test@12345"}
    cookie = api_client.post(reverse("accounts:login"), login, format="json").cookies[COOKIE]
    response = api_client.post(reverse("accounts:logout"))  # no Authorization header
    assert response.status_code == 204
    api_client.cookies[COOKIE] = cookie.value
    assert api_client.post(reverse("accounts:refresh")).status_code == 401


def test_logout_without_a_cookie_still_clears_it(api_client):
    response = api_client.post(reverse("accounts:logout"))
    assert response.status_code == 204
    assert response.cookies[COOKIE].value == ""


def test_login_email_is_case_insensitive(api_client):
    customer = CustomerFactory()
    login = {"email": customer.user.email.upper(), "password": "Test@12345"}
    assert api_client.post(reverse("accounts:login"), login, format="json").status_code == 200
