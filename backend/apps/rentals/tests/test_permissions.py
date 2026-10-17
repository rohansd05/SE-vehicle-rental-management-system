"""SE-4: every rentals endpoint against every role, including anonymous.

"Allowed" means the request got past authentication and the permission
check (any status except 401/403); payloads are minimal, so 400, 404 or 415
are normal answers. "Denied" is 401 for anonymous and 403 for the rest.
Branch scoping (SE-5) is tested in test_api.py.
"""

import pytest
from django.urls import reverse

from apps.accounts.tests.factories import (
    AdministratorFactory,
    BranchManagerFactory,
    BranchStaffFactory,
    CustomerFactory,
    MaintenanceTechnicianFactory,
)
from apps.accounts.tests.helpers import authenticated_client
from apps.bookings.tests.factories import BookingFactory

pytestmark = pytest.mark.django_db

ROLES = ["anonymous", "customer", "staff", "technician", "admin", "manager"]
BRANCH_TEAM = {"staff", "manager"}


def _user(role):
    return {
        "customer": lambda: CustomerFactory().user,
        "staff": lambda: BranchStaffFactory().user,
        "technician": lambda: MaintenanceTechnicianFactory().user,
        "admin": lambda: AdministratorFactory().user,
        "manager": lambda: BranchManagerFactory().user,
        "anonymous": lambda: None,
    }[role]()


def booking_url(name):
    return lambda: reverse(f"rentals:{name}", args=[BookingFactory().pk])


# (name, method, url builder, allowed roles)
ENDPOINTS = [
    ("branch-bookings", "get", lambda: reverse("rentals:branch-bookings"), BRANCH_TEAM),
    ("handover-detail", "get", booking_url("handover-detail"), BRANCH_TEAM),
    # UC 7's actor is Branch Staff; the report's recorded_by is a BranchStaff.
    ("handover-complete", "post", booking_url("handover-complete"), {"staff"}),
]

CASES = [
    pytest.param(method, url, role, role in allowed, id=f"{name}-{role}")
    for name, method, url, allowed in ENDPOINTS
    for role in ROLES
]


@pytest.mark.parametrize(("method", "url", "role", "allowed"), CASES)
def test_endpoint_permission(api_client, method, url, role, allowed):
    user = _user(role)
    client = authenticated_client(user) if user else api_client
    response = getattr(client, method)(url(), {}, format="json")
    if allowed:
        assert response.status_code not in (401, 403), response.content
    else:
        expected = 401 if role == "anonymous" else 403
        assert response.status_code == expected, response.content


def test_every_rentals_route_is_in_the_matrix():
    """A new endpoint must be added to ENDPOINTS (and so get a permission test)."""
    from apps.rentals.urls import urlpatterns

    assert {pattern.name for pattern in urlpatterns} == {name for name, *_ in ENDPOINTS}
