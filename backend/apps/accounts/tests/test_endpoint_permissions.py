"""SE-4: every endpoint, every role, one test each (allowed and denied).

"Allowed" means the request got past authentication and permission checks
(any status except 401/403); the payloads are deliberately minimal, so a
400 is a normal answer. "Denied" means 401 (anonymous) or 403.
"""

import pytest
from django.urls import reverse

from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchManagerFactory,
    BranchStaffFactory,
    CustomerFactory,
    LicenceFactory,
    MaintenanceTechnicianFactory,
)
from apps.accounts.tests.helpers import authenticated_client
from apps.core.files import signed_file_url

pytestmark = pytest.mark.django_db

ROLES = ["anonymous", "customer", "staff", "technician", "admin", "manager"]
EVERY_SIGNED_IN = {"customer", "staff", "technician", "admin", "manager"}
VERIFIERS = {"staff", "admin"}


def _user(role):
    if role == "customer":
        return CustomerFactory().user
    if role == "staff":
        return BranchStaffFactory().user
    if role == "technician":
        return MaintenanceTechnicianFactory().user
    if role == "admin":
        return AdministratorFactory().user
    if role == "manager":
        return BranchManagerFactory().user
    return None


def _client(role, api_client):
    user = _user(role)
    return (authenticated_client(user) if user else api_client), user


def _licence_pk():
    return LicenceFactory(status="Pending Verification").pk


# (name, method, url builder, allowed roles)
ENDPOINTS = [
    ("register", "post", lambda: reverse("accounts:register"), set(ROLES)),
    ("verify-otp", "post", lambda: reverse("accounts:verify-otp"), set(ROLES)),
    ("resend-otp", "post", lambda: reverse("accounts:resend-otp"), set(ROLES)),
    ("login", "post", lambda: reverse("accounts:login"), set(ROLES)),
    ("health", "get", lambda: reverse("core:health"), set(ROLES)),
    ("logout", "post", lambda: reverse("accounts:logout"), set(ROLES)),  # D21
    ("password-change", "post", lambda: reverse("accounts:password-change"), EVERY_SIGNED_IN),
    ("me-get", "get", lambda: reverse("accounts:me"), EVERY_SIGNED_IN),
    ("me-patch", "patch", lambda: reverse("accounts:me"), EVERY_SIGNED_IN),
    ("verify-mobile", "post", lambda: reverse("accounts:verify-mobile"), EVERY_SIGNED_IN),
    ("licence-get", "get", lambda: reverse("accounts:licence"), {"customer"}),
    ("licence-post", "post", lambda: reverse("accounts:licence"), {"customer"}),
    ("licence-pending", "get", lambda: reverse("accounts:licence-pending"), VERIFIERS),
    (
        "licence-approve",
        "post",
        lambda: reverse("accounts:licence-approve", args=[_licence_pk()]),
        VERIFIERS,
    ),
    (
        "licence-reject",
        "post",
        lambda: reverse("accounts:licence-reject", args=[_licence_pk()]),
        VERIFIERS,
    ),
]

CASES = [
    pytest.param(name, method, url, role, role in allowed, id=f"{name}-{role}")
    for name, method, url, allowed in ENDPOINTS
    for role in ROLES
]


@pytest.mark.parametrize(("name", "method", "url", "role", "allowed"), CASES)
def test_endpoint_permission(api_client, name, method, url, role, allowed):
    client, _ = _client(role, api_client)
    response = getattr(client, method)(url(), {}, format="json")
    if allowed:
        assert response.status_code not in (401, 403), response.content
    else:
        expected = {401} if role == "anonymous" else {403}
        assert response.status_code in expected, response.content


@pytest.mark.parametrize("role", ROLES)
def test_signed_file_link_needs_only_the_signature(api_client, role, settings, tmp_path):
    """files/{token}/ is open to anyone holding a valid link (SI-3)."""
    settings.MEDIA_ROOT = tmp_path
    (tmp_path / "licences").mkdir()
    (tmp_path / "licences" / "front-x.png").write_bytes(b"x")
    licence = LicenceFactory(front_image="licences/front-x.png")
    client, _ = _client(role, api_client)
    assert client.get(signed_file_url(licence.front_image)).status_code == 200


def test_inactive_user_is_denied_even_with_a_valid_token():
    user = CustomerFactory().user
    client = authenticated_client(user)
    user.is_active = False
    user.save()
    assert client.get(reverse("accounts:me")).status_code == 401


def test_customer_without_profile_is_denied_licence():
    """IsCustomer needs the role and the Customer profile."""
    user = CustomerFactory().user
    user.customer.delete()
    response = authenticated_client(user).get(reverse("accounts:licence"))
    assert response.status_code == 403


@pytest.mark.parametrize("role", [r for r in ROLES if r != "anonymous"])
def test_refresh_works_for_every_role_with_its_cookie(api_client, role):
    """refresh/ is AllowAny: the cookie, not the role, is the credential (D21)."""
    user = _user(role)
    login = {"email": user.email, "password": "Test@12345"}
    assert api_client.post(reverse("accounts:login"), login, format="json").status_code == 200
    response = api_client.post(reverse("accounts:refresh"))
    assert response.status_code == 200
    assert response.json()["user"]["role"] == user.role


@pytest.mark.parametrize("role", ROLES)
def test_refresh_without_a_cookie_is_401_for_everyone(api_client, role):
    client, _ = _client(role, api_client)
    response = client.post(reverse("accounts:refresh"))
    assert response.status_code == 401
    assert response.json()["code"] == "session_ended"
