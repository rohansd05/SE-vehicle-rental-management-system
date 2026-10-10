"""D21: the refresh token lives only in an httpOnly, SameSite=Strict cookie."""

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.accounts.tests.factories import CustomerFactory

pytestmark = pytest.mark.django_db

COOKIE = "vrms_refresh"


def _sign_in(client):
    user = CustomerFactory().user
    login = {"email": user.email, "password": "Test@12345"}
    return client.post(reverse("accounts:login"), login, format="json")


def test_login_sets_a_hardened_cookie_and_keeps_the_token_out_of_the_body(api_client):
    response = _sign_in(api_client)
    assert "refresh" not in response.json()
    cookie = response.cookies[COOKIE]
    assert cookie["httponly"] is True
    assert cookie["samesite"] == "Strict"
    assert cookie["secure"] is True
    assert cookie["path"] == "/api/v1/auth/"
    assert cookie["max-age"] == 30 * 60  # D19
    assert cookie.value.count(".") == 2  # a JWT


def test_refresh_sets_a_new_hardened_cookie(api_client):
    _sign_in(api_client)
    response = api_client.post(reverse("accounts:refresh"))
    assert "refresh" not in response.json()
    cookie = response.cookies[COOKIE]
    assert (cookie["httponly"], cookie["samesite"], cookie["path"]) == (
        True,
        "Strict",
        "/api/v1/auth/",
    )


@override_settings(AUTH_REFRESH_COOKIE_SECURE=False)
def test_cookie_is_not_secure_only_when_development_says_so(api_client):
    assert _sign_in(api_client).cookies[COOKIE]["secure"] == ""


def test_a_refresh_token_in_the_body_is_ignored(api_client):
    signed_in = _sign_in(api_client)
    token = signed_in.cookies[COOKIE].value
    api_client.cookies.clear()
    response = api_client.post(reverse("accounts:refresh"), {"refresh": token}, format="json")
    assert response.status_code == 401


def test_the_cookie_is_only_sent_to_auth_paths(api_client):
    """The cookie path keeps it away from every non-auth endpoint."""
    cookie = _sign_in(api_client).cookies[COOKIE]
    assert not "/api/v1/me/".startswith(cookie["path"])
    assert "/api/v1/auth/refresh/".startswith(cookie["path"])
