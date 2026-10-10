"""SE-4: every maintenance endpoint against every role, including anonymous.

"Allowed" means the request got past authentication and the permission
check (any status except 401/403); payloads are minimal, so 400, 404 or 409
are normal answers. "Denied" is 401 for anonymous and 403 for the rest.
Record-level scoping (SE-5) is tested in test_api.py.
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
from apps.maintenance.tests.factories import MaintenanceJobFactory

pytestmark = pytest.mark.django_db

ROLES = ["anonymous", "customer", "staff", "technician", "admin", "manager"]
MANAGERS = {"staff", "admin", "manager"}
VIEWERS = MANAGERS | {"technician"}


def _user(role):
    return {
        "customer": lambda: CustomerFactory().user,
        "staff": lambda: BranchStaffFactory().user,
        "technician": lambda: MaintenanceTechnicianFactory().user,
        "admin": lambda: AdministratorFactory().user,
        "manager": lambda: BranchManagerFactory().user,
        "anonymous": lambda: None,
    }[role]()


def _job():
    return MaintenanceJobFactory().pk


def _vehicle():
    return MaintenanceJobFactory().vehicle_id


def job_url(name):
    return lambda: reverse(f"maintenance:{name}", args=[_job()])


# (name, method, url builder, allowed roles)
ENDPOINTS = [
    ("job-list-get", "get", lambda: reverse("maintenance:job-list"), VIEWERS),
    ("job-list-post", "post", lambda: reverse("maintenance:job-list"), MANAGERS),
    ("job-detail", "get", job_url("job-detail"), VIEWERS),
    ("job-schedule", "post", job_url("job-schedule"), MANAGERS),
    ("job-cancel", "post", job_url("job-cancel"), MANAGERS),
    ("job-start", "post", job_url("job-start"), {"technician"}),
    ("job-record", "put", job_url("job-record"), {"technician"}),
    ("job-complete", "post", job_url("job-complete"), {"technician", "admin"}),
    ("job-approve-clearance", "post", job_url("job-approve-clearance"), {"admin"}),
    ("clearance-queue", "get", lambda: reverse("maintenance:clearance-queue"), {"admin"}),
    ("technician-list", "get", lambda: reverse("maintenance:technician-list"), MANAGERS),
    ("vehicle-list", "get", lambda: reverse("maintenance:vehicle-list"), MANAGERS),
    (
        "vehicle-history",
        "get",
        lambda: reverse("maintenance:vehicle-history", args=[_vehicle()]),
        VIEWERS,
    ),
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


def test_every_maintenance_route_is_in_the_matrix():
    """A new endpoint must be added to ENDPOINTS (and so get a permission test)."""
    from apps.maintenance.urls import urlpatterns

    named = {pattern.name for pattern in urlpatterns}
    covered = {name.removesuffix("-get").removesuffix("-post") for name, *_ in ENDPOINTS}
    assert named == covered
